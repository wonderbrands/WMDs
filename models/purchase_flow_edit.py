# -*- coding: utf-8 -*-
from odoo import models, fields, api
from datetime import datetime
from odoo.exceptions import UserError
import logging
import requests

_logger = logging.getLogger(__name__)


class StockWMDSPurchase(models.Model):
    _inherit = 'stock.picking'

    comex_source_po_id = fields.Many2one(
        'purchase.order', string='PO Origen COMEX',
        readonly=True, copy=False,
    )

    def button_validate(self):
        # We now handle quarantine by blocking the target locations themselves in wb_tech_location_blocking
        return super(StockWMDSPurchase, self).button_validate()


class PurchaseWMDS(models.Model):
    _inherit = 'purchase.order'

    wmds_log = fields.One2many('wmds.log', 'purchase', string='WMDS Log')
    check_commertial = fields.Boolean('Vo.Bo Comex', default=False, copy=False)
    comex_release_date = fields.Datetime(
        'Fecha VoBo COMEX', readonly=True, copy=False,
    )
    quarantine_transfer_ids = fields.One2many(
        'stock.picking', 'comex_source_po_id',
        string='Traslados Liberación COMEX',
    )
    quarantine_transfer_count = fields.Integer(
        compute='_compute_quarantine_transfer_count',
    )

    @api.depends('quarantine_transfer_ids')
    def _compute_quarantine_transfer_count(self):
        for po in self:
            po.quarantine_transfer_count = len(po.quarantine_transfer_ids)

    def action_view_quarantine_transfers(self):
        self.ensure_one()
        action = self.env.ref('stock.action_picking_tree_all').read()[0]
        action['domain'] = [('id', 'in', self.quarantine_transfer_ids.ids)]
        return action

    def action_comex_approve(self):
        """
        Botón VoBo COMEX. Un solo click:
        1. Activa check_commertial
        2. Busca y desbloquea ubicaciones bloqueadas bajo este PO
        3. Recarga la vista
        """
        self.ensure_one()

        if self.check_commertial:
            raise UserError(
                'El VoBo COMEX ya fue otorgado para esta orden.'
            )

        # Activar VoBo
        self.write({
            'check_commertial': True,
            'comex_release_date': fields.Datetime.now(),
        })

        # Find and unblock locations blocked by this PO
        blocked_locs = self.env['stock.location'].search([
            ('block_reason', 'like', self.name),
            ('block_reason_type', '=', 'cuarentena'),
            ('original_parent_id', '!=', False)
        ])

        for loc in blocked_locs:
            loc._do_unblock(comment=f"Desbloqueo automático por aprobación de Vo.Bo. COMEX (PO: {self.name}).")

        # Create log
        self.env['wmds.log'].sudo().create({
            'purchase': self.id,
            'log': f"COMEX: Aprobación Vo.Bo. COMEX. Ubicaciones liberadas: {', '.join(blocked_locs.mapped('complete_name')) or 'Ninguna'}",
            'user': self.env.user.id,
            'date': fields.Datetime.now(),
        })

        # Recargar el formulario
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def _get_quarantine_from_rackeos(self):
        logging.info(f'\n\n DENTRO DE: _get_quarantine_from_rackeos \n\n')

        """
        Busca stock en cuarentena puesto por Rackeos de ESTA PO.
        Asegurando capturar todo el disponible sumando los quants.
        """
        self.ensure_one()

        rackeos = self.env['stock.picking'].search([
            ('origin', '=', self.name),
            ('picking_type_id.name', '=', 'Rackeo'),
            ('state', '=', 'done'),
        ])
        logging.info(f'\n\n rackeos: {rackeos} \n\n')
        if not rackeos:
            return []

        move_lines = self.env['stock.move.line'].search([
            ('picking_id', 'in', rackeos.ids),
            ('state', '=', 'done'),
        ])

        cuarentena_lines = move_lines.filtered(
            lambda ml: 'Cuarentena' in (ml.location_dest_id.complete_name or '')
        )

        if not cuarentena_lines:
            return []

        # Agrupar por (STOR picking, producto, ubicación, lote)
        # Es CRÍTICO incluir el picking_id en la clave para que cada STOR
        # genere su propio traslado de liberación y no se fusionen.
        grouped = {}
        for ml in cuarentena_lines:
            key = (
                ml.picking_id.id,                          # ← STOR picking
                ml.product_id.id,
                ml.location_dest_id.id,
                ml.lot_id.id if ml.lot_id else False,
            )
            if key not in grouped:
                grouped[key] = {
                    'stor_picking_id': ml.picking_id.id,
                    'stor_picking_name': ml.picking_id.name,  # e.g. WH/STOR/02662
                    'product_id': ml.product_id.id,
                    'product_name': ml.product_id.display_name,
                    'qty': 0.0,
                    'lot_id': ml.lot_id.id if ml.lot_id else False,
                    'location_id': ml.location_dest_id.id,
                    'location_name': ml.location_dest_id.complete_name,
                    'uom_id': ml.product_uom_id.id,
                }
            grouped[key]['qty'] += ml.quantity

        result = []
        for key, data in grouped.items():
            _stor_picking_id, product_id, location_id, lot_id = key

            domain = [
                ('product_id', '=', product_id),
                ('location_id', '=', location_id),
                ('quantity', '>', 0),
            ]
            if lot_id:
                domain.append(('lot_id', '=', lot_id))

            # CORRECCIÓN: Evitamos limit=1 para sumar quants en caso de estar divididos por empaques
            quants = self.env['stock.quant'].search(domain)
            if not quants:
                continue

            available = sum(quants.mapped('quantity')) - sum(quants.mapped('reserved_quantity'))
            qty = min(data['qty'], available)

            if qty <= 0:
                continue

            loc_name = data['location_name']
            if 'Cuarentena' not in loc_name:
                continue

            # ────────────────────────────────────────────────────────
            # Las ubicaciones N1 no tienen equivalente en Stock/Almacenaje;
            # su destino correcto es Stock/A_Pickable.
            if 'N1' in loc_name:
                storage_name = loc_name.replace('Cuarentena', 'Stock/A_Pickable')
            else:
                storage_name = loc_name.replace('Cuarentena', 'Stock/Almacenaje')
            # ─────────────────────────────────────────────────────────────────

            storage_loc = self.env['stock.location'].search([
                ('complete_name', '=', storage_name),
                ('usage', '=', 'internal'),
            ], limit=1)

            if not storage_loc:
                continue

            data['qty'] = qty
            data['storage_location_id'] = storage_loc.id
            result.append(data)

        logging.info(f'\n\n RESULTADO: {result} \n\n')
        return result

    def _create_release_pickings(self, lines):
        """
        Crea picking(s) interno(s) Cuarentena → Almacenaje/Pickeable,
        asigna cantidades y lotes exactos, y los VALIDA automáticamente.
        """
        self.ensure_one()

        warehouse = self.picking_type_id.warehouse_id
        if not warehouse:
            warehouse = self.env['stock.warehouse'].search([], limit=1)

        pick_type = self.env['stock.picking.type'].search([
            ('warehouse_id', '=', warehouse.id),
            ('name', '=', 'Traslados internos'),
        ], limit=1)

        if not pick_type:
            raise UserError(
                'No se encontró tipo de operación interna '
                'para el almacén %s.' % warehouse.name
            )

        groups = {}
        for line in lines:
            # La clave incluye el nombre del STOR para garantizar un traslado
            # de liberación por cada picking de rackeo origen.
            key = (line['stor_picking_name'], line['location_id'], line['storage_location_id'])
            groups.setdefault(key, []).append(line)

        pickings = self.env['stock.picking']

        for (stor_picking_name, src_id, dest_id), group_lines in groups.items():

            # Origin: "PO00076:WH/STOR/02662" — nombre de la PO + nombre del STOR
            picking_origin = '%s:%s' % (self.name, stor_picking_name)

            moves = []
            for line in group_lines:
                # Definimos explícitamente el stock.move.line para forzar Odoo
                # a mover esta cantidad y este lote específicos, bypassando reservas genéricas.
                move_line_vals = {
                    'product_id': line['product_id'],
                    'location_id': src_id,
                    'location_dest_id': dest_id,
                    'quantity': line['qty'],  # Cantidad Hecha
                    'product_uom_id': line['uom_id'],
                }
                
                # Asignar lote si el producto utiliza trazabilidad
                if line.get('lot_id'):
                    move_line_vals['lot_id'] = line['lot_id']

                moves.append((0, 0, {
                    'name': 'COMEX: %s' % line['product_name'],
                    'product_id': line['product_id'],
                    'product_uom_qty': line['qty'],
                    'product_uom': line['uom_id'],
                    'location_id': src_id,
                    'location_dest_id': dest_id,
                    'move_line_ids': [(0, 0, move_line_vals)],
                }))

            picking = self.env['stock.picking'].create({
                'picking_type_id': pick_type.id,
                'location_id': src_id,
                'location_dest_id': dest_id,
                'origin': picking_origin,
                'comex_source_po_id': self.id,
                'move_ids': moves,
            })
            
            # Confirmar y VALIDAR el movimiento inmediatamente para que el
            # stock se mueva físicamente y no quede bloqueando futuras transferencias.
            picking.action_confirm()
            picking.button_validate()
            
            pickings |= picking

        return pickings 
   
    def write(self, vals):
        if 'state' in vals:
            new_state = vals['state']

            state_msg_map = {
                'draft': 'Compra restablecida a Borrador',
                'sent': 'Solicitud de Presupuesto Enviada',
                'to approve': 'Compra esperando aprobación',
                'purchase': 'Compra Confirmada',
                'done': 'Compra Bloqueada/Realizada',
                'cancel': 'Compra Cancelada'
            }

            msg_state = state_msg_map.get(
                new_state,
                f"Estado cambiado a: {new_state}"
            )

            for record in self:
                if record.state != new_state:
                    self.env['wmds.log'].sudo().create({
                        'purchase': record.id,
                        'log': msg_state,
                        'user': self.env.user.id,
                        'date': fields.Datetime.now(),
                    })
                    # Force propagation to picking and batches if canceled
                    if new_state == 'cancel':
                        pickings = self.env['stock.picking'].sudo().search([('purchase_id', '=', record.id)])
                        for pick in pickings:
                            self.env['wmds.log'].sudo().create({
                                'pick': pick.id,
                                'log': f"Orden de compra {record.name} cancelada - {msg_state}",
                                'user': self.env.user.id,
                            })

        if 'check_commertial' in vals:
            is_comm = vals.get('check_commertial')
            log_msg = (
                'Vo.Bo de COMEX otorgado' if is_comm
                else 'COMEX ha retirado Vo.Bo'
            )

            for record in self:
                if record.check_commertial != is_comm:
                    self.env['wmds.log'].sudo().create({
                        'purchase': record.id,
                        'log': log_msg,
                        'user': self.env.user.id,
                        'date': fields.Datetime.now(),
                    })

        return super(PurchaseWMDS, self).write(vals)