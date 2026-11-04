# -*- coding: utf-8 -*-
import logging

from odoo import models
from odoo.exceptions import UserError
from odoo.service.model import PG_CONCURRENCY_EXCEPTIONS_TO_RETRY

_logger = logging.getLogger(__name__)


class BinDockOperations(models.Model):
    """Operaciones de traslado a BIN y de BIN a DOCK.

    Se ejecutan de forma síncrona dentro de la petición del operador: antes, los
    traslados de más de 10 elementos se encolaban en wmds.queued_tasks y quedaban
    detrás de los despachos largos, dejando el BIN inutilizable mientras tanto.

    Las escrituras y los logs se hacen en bloque para que el tiempo de respuesta no
    crezca con consultas por paquete. Los errores de negocio se lanzan como
    UserError; los de concurrencia de PostgreSQL se propagan sin capturar para que
    Odoo reintente la petición completa.
    """
    _inherit = "bin.storage"

    # ------------------------------------------------------------------
    # Utilidades
    # ------------------------------------------------------------------

    def _wmds_operator(self, operator_login):
        return self.env["res.users"].sudo().search([('login', '=', operator_login)], limit=1)

    def _wmds_bin_contents(self):
        """Devuelve (EI, moves) que siguen en este BIN."""
        self.ensure_one()
        domain = [('bin_id', '=', self.id), ('on_bin', '=', True)]
        return (
            self.env["sale.order.ei"].sudo().search(domain),
            self.env["stock.move"].sudo().search(domain),
        )

    def _wmds_pick_by_sale(self, sale_ids):
        """Último picking PICK (asignado o hecho) por pedido, en una sola consulta."""
        pick_by_sale = {}
        if not sale_ids:
            return pick_by_sale
        pickings = self.env['stock.picking'].sudo().search([
            ('sale_id', 'in', list(sale_ids)),
            ('state', 'in', ['assigned', 'done']),
            ('picking_type_id.name', 'ilike', 'Pick')
        ], order='date_done desc')
        for picking in pickings:
            pick_by_sale.setdefault(picking.sale_id.id, picking)
        return pick_by_sale

    def _wmds_ei_log_vals(self, tags, messages, user_id):
        """Valores de wmds.log por EI: en su PICK si existe, si no en el pedido."""
        pick_by_sale = self._wmds_pick_by_sale({t.so_id.id for t in tags if t.so_id})
        vals_list = []
        for tag in tags:
            if not tag.so_id:
                continue
            picking = pick_by_sale.get(tag.so_id.id)
            target = {"pick": picking.id} if picking else {"sale": tag.so_id.id}
            vals_list.append(dict(target, log=messages[tag.id], user=user_id))
        return vals_list

    # ------------------------------------------------------------------
    # Traslado a BIN
    # ------------------------------------------------------------------

    def _wmds_move_to_bin(self, operator_login, orders=None, batch_id=None, pick_id=None, carrier_id=None):
        """Coloca en este BIN un lote/traslado de fulfillment o una lista de guías EI.

        Si llegan batch_id o pick_id se procesan los moves de fulfillment y se
        ignora ``orders`` (mismo comportamiento que el controlador original).
        """
        self.ensure_one()
        if self.state == 'blocked':
            raise UserError(f"El BIN {self.name} está bloqueado. No se pueden ingresar más productos.")

        operator = self._wmds_operator(operator_login)
        current_ei, current_moves = self._wmds_bin_contents()

        if batch_id or pick_id:
            if current_ei:
                raise UserError('El BIN ya contiene pedidos. No se pueden mezclar con fulfillment.')
            result = self._wmds_move_full_to_bin(operator, batch_id, pick_id, carrier_id)
        elif orders:
            if current_moves:
                raise UserError('El BIN ya contiene productos de fulfillment. No se pueden mezclar con pedidos.')
            result = self._wmds_move_orders_to_bin(operator, orders, carrier_id)
        else:
            result = {}

        return dict(result, ok=True)

    def _wmds_bin_log(self):
        self.ensure_one()
        bin_log = self.env["bin.log"].sudo().search([('bin_id', '=', self.id)], limit=1)
        return bin_log or self.env["bin.log"].sudo().create({'bin_id': self.id})

    def _wmds_move_full_to_bin(self, operator, batch_id, pick_id, carrier_id):
        if batch_id:
            batch = self.env['stock.picking.batch'].sudo().browse(batch_id)
            pickings = batch.picking_ids
            log_target = {"batch_pick": batch.id}
            log_label = f"Lote {batch.name}"
            batch_origins = list(filter(None, set(pickings.mapped('origin'))))
            origin = batch_origins[0] if batch_origins else False
        else:
            picking = self.env['stock.picking'].sudo().browse(pick_id)
            pickings = picking
            log_target = {"pick": picking.id}
            log_label = f"Traslado {picking.name}"
            origin = picking.origin

        if origin:
            # Regla: Ningún otro BIN puede tener este mismo documento origen asignado
            other_bin = self.sudo().search([
                ('origin_doc', '=', origin),
                ('id', '!=', self.id)
            ], limit=1)
            if other_bin:
                raise UserError(f"El documento origen '{origin}' ya está asignado al BIN '{other_bin.name}'. No puede haber más de un BIN para el mismo origen.")

            # Regla: Este BIN solo puede admitir un documento origen
            if self.origin_doc and self.origin_doc != origin:
                raise UserError(f"El BIN {self.name} ya está asignado al origen '{self.origin_doc}'. No se pueden ingresar productos del origen '{origin}'.")

        bin_vals = {}
        if carrier_id:
            bin_vals['carrier_id'] = int(carrier_id)
        if origin and not self.origin_doc:
            bin_vals['origin_doc'] = origin
        if bin_vals:
            self.write(bin_vals)

        operator_name = operator.name if operator else "Desconocido"
        bin_log = self._wmds_bin_log()

        moves = pickings.mapped('move_ids').filtered(lambda m: m.state == 'done' and not m.dispatched)
        moves.write({
            'on_bin': True,
            'bin_id': self.id,
            'on_dock': False,
            'dock_id': False,
            'dispatched': False
        })
        self.env["log.line"].sudo().create([{
            "operator_id": operator.id or False,
            "qty": move.quantity,
            "message": f"El operador {operator_name} puso el producto {move.product_id.display_name} (de la orden {move.picking_id.name}) en el bin {self.name}",
            "bin_log_id": bin_log.id
        } for move in moves])

        self._wmds_close_wholesale_pack(pickings)

        self.env["wmds.log"].sudo().create(dict(
            log_target,
            log=f"{log_label} movido a BIN {self.name} por {operator_name}",
            user=operator.id or False,
        ))

        return {"count": len(moves), "origin": origin or "", "bin": self.name}

    def _wmds_close_wholesale_pack(self, pickings):
        """Valida automáticamente los PACK pendientes de pedidos de mayoreo."""
        for sale in pickings.sale_id.filtered('data_is_wholesale_sale'):
            pack_pickings = self.env['stock.picking'].sudo().search([
                ('sale_id', '=', sale.id),
                ('picking_type_id.name', 'ilike', 'Pack'),
                ('state', 'not in', ['done', 'cancel'])
            ])
            for pack_pick in pack_pickings:
                try:
                    # Savepoint: un fallo de un PACK no debe dejar abortada la transacción
                    # del traslado; los errores de concurrencia sí se propagan para que
                    # Odoo reintente la petición completa.
                    with self.env.cr.savepoint():
                        pack_pick.action_assign()
                        for move in pack_pick.move_ids:
                            if move.state not in ('done', 'cancel'):
                                move.write({
                                    'quantity': move.product_uom_qty,
                                    'picked': True
                                })
                        res = pack_pick.button_validate()
                        if isinstance(res, dict) and res.get('res_model') == 'stock.backorder.confirmation':
                            wizard = self.env['stock.backorder.confirmation'].with_context(res['context']).sudo().create({
                                'pick_ids': [(4, pack_pick.id)]
                            })
                            wizard.process()
                    _logger.info(f"Auto-validated wholesale PACK picking {pack_pick.name} for SO {sale.name}")
                except PG_CONCURRENCY_EXCEPTIONS_TO_RETRY:
                    raise
                except Exception as pe:
                    _logger.error(f"Error auto-validating wholesale PACK picking {pack_pick.name}: {pe}")

    def _wmds_find_or_create_ei(self, orders):
        """Devuelve {guía: EI} para las guías dadas, creando las EI que falten."""
        EI = self.env["sale.order.ei"].sudo()
        tags = EI.search([('display_name_custom', 'in', orders)])
        tag_by_name = {t.display_name_custom: t for t in tags}

        missing = [name for name in orders if name not in tag_by_name and name.count('/') == 1]
        if missing:
            sales = self.env['sale.order'].sudo().search([
                ('name', 'in', list({name.split('/')[0] for name in missing}))
            ])
            sale_by_name = {so.name: so for so in sales}
            for name in missing:
                so_name, seq_str = name.split('/')
                so = sale_by_name.get(so_name)
                if not so:
                    continue
                try:
                    seq = int(seq_str)
                except ValueError:
                    continue
                if 0 < seq <= so.ei_total:
                    tag_by_name[name] = EI.create({
                        'so_id': so.id,
                        'sequence_number': seq
                    })
                    _logger.info(f"Etiqueta {name} creada")
        return tag_by_name

    def _wmds_move_orders_to_bin(self, operator, orders, carrier_id):
        if carrier_id:
            self.write({'carrier_id': int(carrier_id)})

        operator_name = operator.name if operator else "Desconocido"
        bin_log = self._wmds_bin_log()

        tag_by_name = self._wmds_find_or_create_ei(orders)
        for name in orders:
            if name not in tag_by_name:
                _logger.warning(f"No se pudo encontrar ni crear ei_tag para {name}")

        tags = self.env["sale.order.ei"].sudo().concat(*tag_by_name.values())
        tags.write({
            'on_bin': True,
            'bin_id': self.id,
            'on_dock': False,
            'dock_id': False,
            'dispatched': False
        })

        messages = {
            tag.id: f"El operador {operator_name} puso el paquete {name} en el bin {self.name}"
            for name, tag in tag_by_name.items()
        }
        self.env["log.line"].sudo().create([{
            "operator_id": operator.id or False,
            "qty": 1,
            "message": messages[tag.id],
            "bin_log_id": bin_log.id
        } for tag in tags])
        self.env["wmds.log"].sudo().create(self._wmds_ei_log_vals(tags, messages, operator.id or False))
        return {}

    # ------------------------------------------------------------------
    # Traslado de BIN a DOCK
    # ------------------------------------------------------------------

    def _wmds_move_to_dock(self, dock, operator_login, selected_packages=None):
        """Mueve el contenido (o la selección) de este BIN al DOCK y libera el BIN si queda vacío.

        ``selected_packages`` es una lista de {name, is_full, move_id}; vacía mueve todo.
        """
        self.ensure_one()
        if self.state != 'blocked':
            raise UserError(f"El BIN {self.name} debe estar bloqueado para poder ser trasladado a DOCK.")

        ei_domain = [('bin_id', '=', self.id), ('on_bin', '=', True)]
        move_domain = [('bin_id', '=', self.id), ('on_bin', '=', True)]

        if selected_packages:
            ei_names = [p['name'] for p in selected_packages if not p.get('is_full')]
            move_ids = [p['move_id'] for p in selected_packages if p.get('is_full')]
            ei_domain.append(('display_name_custom', 'in', ei_names) if ei_names else ('id', '=', 0))
            move_domain.append(('id', 'in', move_ids) if move_ids else ('id', '=', 0))

        ei_tags = self.env["sale.order.ei"].sudo().search(ei_domain)
        moves = self.env["stock.move"].sudo().search(move_domain)

        # Validar mezcla en el DOCK: solo si se va a mover algo de ese tipo
        dock_domain = [('dock_id', '=', dock.id), ('on_dock', '=', True)]
        if ei_tags and self.env["stock.move"].sudo().search_count(dock_domain):
            raise UserError('El DOCK ya contiene productos de fulfillment. No se pueden mezclar con pedidos.')
        if moves and self.env["sale.order.ei"].sudo().search_count(dock_domain):
            raise UserError('El DOCK ya contiene pedidos. No se pueden mezclar con fulfillment.')

        operator = self._wmds_operator(operator_login)
        operator_name = operator.name if operator else "Desconocido"
        user_id = operator.id or False

        dock_log = self.env["dock.log"].sudo().search([
            ('dock_id', '=', dock.id),
            ('bin_id', '=', self.id)
        ], limit=1) or self.env["dock.log"].sudo().create({
            'dock_id': dock.id,
            'bin_id': self.id
        })

        dock_vals = {
            'on_bin': False,
            'bin_id': False,
            'on_dock': True,
            'dock_id': dock.id,
        }

        # Mover EI Tags
        ei_tags.write(dock_vals)
        ei_messages = {
            tag.id: f"El operador {operator_name} movió el paquete {tag.display_name_custom} del {self.name} al DOCK {dock.name}"
            for tag in ei_tags
        }
        log_lines = [{
            "operator_id": user_id,
            "qty": 1,
            "message": ei_messages[tag.id],
            "dock_log_id": dock_log.id
        } for tag in ei_tags]
        wmds_logs = self._wmds_ei_log_vals(ei_tags, ei_messages, user_id)

        # Mover Stock Moves
        moves.write(dock_vals)
        log_lines += [{
            "operator_id": user_id,
            "qty": move.quantity,
            "message": f"El operador {operator_name} movió el producto {move.product_id.display_name} del {self.name} al DOCK {dock.name}",
            "dock_log_id": dock_log.id
        } for move in moves]

        # Log en Pickings y Batches de Full
        pickings = moves.picking_id
        wmds_logs += [{
            "batch_pick": batch.id,
            "log": f"Lote {batch.name} movido a DOCK {dock.name} por {operator_name}",
            "user": user_id,
        } for batch in pickings.batch_id]
        wmds_logs += [{
            "pick": picking.id,
            "log": f"Traslado {picking.name} movido a DOCK {dock.name} por {operator_name}",
            "user": user_id,
        } for picking in pickings.filtered(lambda p: not p.batch_id)]

        self.env["log.line"].sudo().create(log_lines)
        self.env["wmds.log"].sudo().create(wmds_logs)

        # Verificar si el BIN quedó vacío para liberarlo
        remaining_ei, remaining_moves = self._wmds_bin_contents()
        if not remaining_ei and not remaining_moves:
            self.write({
                'state': 'available',
                'carrier_id': False,
                'origin_doc': False,
            })

        return {"ok": True, "moved_packages": len(ei_tags) + len(moves)}
