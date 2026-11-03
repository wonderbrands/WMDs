# -*- coding: utf-8 -*-
"""Cancelación de una SO mientras sus paquetes (EI) están en despacho.

Integración opcional con el módulo `wb_so_cancel_guarderia` (no es dependencia):
- Este archivo responde al gancho `sale.order._wb_is_in_dispatch()`.
- El despachador decide por EI si el paquete se embarcó o se retiró.
- Al cerrar el despacho se llama `sale.order._wb_resolve_dispatch_hold(shipped)`.
Si `wb_so_cancel_guarderia` no está instalado, nada de esto se activa.
"""
import logging
from collections import defaultdict

from odoo import _, fields, models

_logger = logging.getLogger(__name__)


class SaleOrderEICancelHold(models.Model):
    _inherit = "sale.order.ei"

    wmds_cancel_decision = fields.Selection([
        ('shipped', 'Embarcada'),
        ('removed', 'Retirada'),
    ], string="Decisión por cancelación", copy=False,
        help="Decisión del despachador sobre esta EI cuando la orden se canceló en pleno despacho.")
    wmds_cancel_product_id = fields.Many2one(
        "product.product", string="Producto embarcado", copy=False,
        help="Producto de esta EI cuando la orden tiene varios productos (1 EI = 1 pieza).")

    def _wmds_process_cancel_holds(self, operator=None):
        """Resuelve las SO canceladas con OUT retenido incluidas en este despacho.

        :return: (tags resueltas, mensajes de error). Las EI de una SO retenida en la
            que falta una decisión NO se resuelven y se reportan como error.
        """
        handled = self.browse()
        errors = []
        for so in self.mapped('so_id'):
            if not so._wmds_is_cancel_held():
                continue
            so_tags = self.filtered(lambda t: t.so_id == so)
            undecided = so_tags.filtered(lambda t: t.wmds_cancel_decision != 'shipped')
            if undecided:
                errors.append(_(
                    "%(so)s: indica si las guías %(eis)s se embarcaron o se retiraron.",
                    so=so.name, eis=", ".join(undecided.mapped('display_name_custom'))))
                continue
            try:
                with self.env.cr.savepoint():
                    resolved = so._wmds_resolve_cancel_hold(operator=operator)
                if resolved:
                    handled |= so_tags
                else:
                    errors.append(_(
                        "%(so)s: no se pudo determinar qué producto llevaban las guías ya entregadas; "
                        "resuélvelo con el botón «Resolver despacho retenido» de la orden.", so=so.name))
            except Exception as e:
                _logger.exception("WMDs: fallo al resolver despacho retenido de %s", so.name)
                errors.append(_("%(so)s: no se pudo resolver el despacho retenido (%(err)s).",
                                so=so.name, err=e))
        return handled, errors


class SaleOrderCancelHold(models.Model):
    _inherit = "sale.order"

    def _wb_is_in_dispatch(self):
        """Gancho de wb_so_cancel_guarderia: la SO está en despacho si alguna de sus EI
        está en una sesión de despacho activa o ya se entregó a la paquetería."""
        parent = getattr(super(), '_wb_is_in_dispatch', None)
        if parent and parent():
            return True
        tags = self.sudo().ei
        if any(tags.mapped('dispatched')):
            return True
        names = tags.mapped('display_name_custom')
        return bool(names) and bool(self.env['wmds.dispatch.session.line'].sudo().search_count([
            ('ei_name', 'in', names),
            ('session_id.state', '=', 'active'),
        ]))

    def _wmds_is_cancel_held(self):
        self.ensure_one()
        return (self.state == 'cancel'
                and hasattr(self, '_wb_held_pickings')
                and bool(self._wb_held_pickings()))

    def _wmds_cancel_hold_products(self):
        """Productos del OUT retenido con las piezas aún sin asignar a una EI embarcada.
        :return: [{'id', 'name', 'remaining'}]"""
        self.ensure_one()
        pending = defaultdict(float)
        names = {}
        for move in self._wb_held_pickings().move_ids.filtered(
                lambda m: m.state not in ('done', 'cancel')):
            product = move.product_id
            names[product.id] = product.display_name
            pending[product.id] += move.product_uom._compute_quantity(
                move.product_uom_qty, product.uom_id, round=False)
        for tag in self.sudo().ei:
            if tag.wmds_cancel_decision == 'shipped' and tag.wmds_cancel_product_id:
                pending[tag.wmds_cancel_product_id.id] -= 1
        return [{'id': pid, 'name': names[pid], 'remaining': qty}
                for pid, qty in pending.items() if pid in names]

    def _wmds_cancel_shipped_quantities(self):
        """{product_id: piezas} embarcadas según las EI (1 EI = 1 pieza): las marcadas
        'Embarcada' + las ya entregadas a la paquetería antes de la cancelación.
        :return: dict, o None si alguna EI no tiene producto y la SO tiene varios."""
        self.ensure_one()
        products = self._wb_held_pickings().move_ids.mapped('product_id')
        shipped = defaultdict(float)
        for tag in self.sudo().ei:
            if not (tag.dispatched or tag.wmds_cancel_decision == 'shipped'):
                continue
            product = tag.wmds_cancel_product_id or (products if len(products) == 1 else False)
            if not product:
                return None
            shipped[product.id] += 1
        return dict(shipped)

    def _wmds_resolve_cancel_hold(self, operator=None):
        """Cierra la retención con lo que dicen las EI. Si no se puede saber qué producto
        se embarcó (EI despachadas antes, SO de varios productos), deja la retención
        para resolverla con el botón de la SO."""
        self.ensure_one()
        if not self._wmds_is_cancel_held():
            return False
        shipped = self._wmds_cancel_shipped_quantities()
        user = operator or self.env.user
        if shipped is None:
            self.env['wmds.log'].sudo().create({
                'sale': self.id, 'user': user.id,
                'log': "Despacho tras cancelación: no se pudo determinar el producto de las guías "
                       "ya entregadas. Resolver con el botón «Resolver despacho retenido» de la orden.",
            })
            return False
        shipped_tags = self.sudo().ei.filtered(
            lambda t: t.wmds_cancel_decision == 'shipped' and not t.dispatched)
        shipped_tags.write({'dispatched': True, 'on_dock': False, 'dock_id': False})
        self._wb_resolve_dispatch_hold(shipped)
        self.env['wmds.log'].sudo().create({
            'sale': self.id, 'user': user.id,
            'log': "Despacho tras cancelación resuelto. Embarcadas: %s." % (
                ", ".join(shipped_tags.mapped('display_name_custom')) or "ninguna nueva"),
        })
        return True

    def _wmds_release_cancel_hold(self, operator=None):
        """La orden ya no se despachará en esta sesión (sesión cancelada/limpiada o todas
        sus EI retiradas): lo no entregado se considera NO embarcado."""
        for so in self:
            if not so._wmds_is_cancel_held():
                continue
            so.sudo().ei.filtered(lambda t: t.wmds_cancel_decision == 'shipped' and not t.dispatched) \
                .write({'wmds_cancel_decision': False, 'wmds_cancel_product_id': False})
            try:
                with self.env.cr.savepoint():
                    so._wmds_resolve_cancel_hold(operator=operator)
            except Exception:
                _logger.exception("WMDs: fallo al liberar despacho retenido de %s", so.name)


class WmdsDispatchSessionCancelHold(models.Model):
    _inherit = 'wmds.dispatch.session'

    def _wmds_release_cancel_holds(self, lines=None):
        """Libera las SO retenidas de estas líneas (antes de cancelar/limpiar la sesión)."""
        lines = lines if lines is not None else self.line_ids
        names = [n for n in set(lines.mapped('so_name')) if n]
        if names:
            self.env['sale.order'].sudo().search([('name', 'in', names)]) \
                ._wmds_release_cancel_hold(operator=self.operator_id[:1])
