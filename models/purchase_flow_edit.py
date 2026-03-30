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
        for picking in self:
            if picking.picking_type_id.name == 'Rackeos':
                # Limpiar el origin por si viene de un traslado COMEX
                clean_origin = (picking.origin or '').replace('COMEX: ', '')

                po = self.env['purchase.order'].search(
                    [('name', '=', clean_origin)],
                    limit=1
                )

                if not po:
                    raise UserError(
                        'No se pudo encontrar la orden de compra '
                        'asociada a la recepción'
                    )

                #Caché para evitar múltiples consultas SQL
                location_cache = {}

                #Diccionarios para agrupar los registros por destino
                lines_by_dest = {}
                moves_by_dest = {}

                for move in picking.move_ids:
                    #Evaluar nivel MOVE
                    move_dest = move.location_dest_id.complete_name or ''
                    new_move_dest = move_dest

                    if not po.check_commertial:
                        if 'Stock/Almacenaje' in move_dest:
                            new_move_dest = move_dest.replace('Stock/Almacenaje', 'Cuarentena')
                        elif 'Stock' in move_dest:
                            new_move_dest = move_dest.replace('Stock', 'Cuarentena')
                    else:
                        if 'Cuarentena' in move_dest:
                            new_move_dest = move_dest.replace('Cuarentena', 'Stock/Almacenaje')

                    if new_move_dest != move_dest:
                        moves_by_dest.setdefault(new_move_dest, self.env['stock.move'])
                        moves_by_dest[new_move_dest] |= move

                    #Evaluar nivel LINE
                    for line in move.move_line_ids:
                        line_dest = line.location_dest_id.complete_name or ''
                        new_line_dest = line_dest

                        if not po.check_commertial:
                            if 'Stock/Almacenaje' in line_dest:
                                new_line_dest = line_dest.replace('Stock/Almacenaje', 'Cuarentena')
                            elif 'Stock' in line_dest:
                                new_line_dest = line_dest.replace('Stock', 'Cuarentena')
                        else:
                            if 'Cuarentena' in line_dest:
                                new_line_dest = line_dest.replace('Cuarentena', 'Stock/Almacenaje')

                        if new_line_dest != line_dest:
                            lines_by_dest.setdefault(new_line_dest, self.env['stock.move.line'])
                            lines_by_dest[new_line_dest] |= line

                #Buscar las ubicaciones necesarias (1 sola query por nombre único)
                all_new_dests = set(moves_by_dest.keys()) | set(lines_by_dest.keys())
                for dest_name in all_new_dests:
                    loc = self.env['stock.location'].search([('complete_name', '=', dest_name)], limit=1)
                    if not loc:
                        raise UserError(f'No se encontró la ubicación de destino: {dest_name}')
                    location_cache[dest_name] = loc.id

                #Aplicar las actualizaciones en bloque (Batch Write)
                for dest_name, lines in lines_by_dest.items():
                    lines.write({'location_dest_id': location_cache[dest_name]})

                for dest_name, moves in moves_by_dest.items():
                    moves.write({'location_dest_id': location_cache[dest_name]})

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
        self.ensure_one()

        if self.check_commertial:
            raise UserError(
                'El VoBo COMEX ya fue otorgado para esta orden.'
            )

        lines = self._get_quarantine_from_rackeos()

        self.write({
            'check_commertial': True,
            'comex_release_date': fields.Datetime.now(),
        })

        if lines:
            pickings = self._create_release_pickings(lines)
            pick_names = ', '.join(pickings.mapped('name'))
            total = sum(l['qty'] for l in lines)

            self.env['wmds.log'].sudo().create({
                'purchase': self.id,
                'log': (
                    'COMEX: Traslado automático Cuarentena → Almacenaje. '
                    'Pickings: %s. Total: %s uds.' % (pick_names, total)
                ),
                'user': self.env.user.id,
                'date': fields.Datetime.now(),
            })

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def _get_quarantine_from_rackeos(self):
        self.ensure_one()

        rackeos = self.env['stock.picking'].search([
            ('origin', '=', self.name),
            ('picking_type_id.name', '=', 'Rackeos'),
            ('state', '=', 'done'),
        ])

        if not rackeos:
            return []

        move_lines = self.env['stock.move.line'].search([
            ('picking_id', 'in', rackeos.ids),
            ('state', '=', 'done'),
        ])

        cuarentena_lines = move_lines.filtered(
            lambda ml: 'Cuarentena' in (
                ml.location_dest_id.complete_name or ''
            )
        )

        if not cuarentena_lines:
            return []

        grouped = {}
        for ml in cuarentena_lines:
            key = (
                ml.product_id.id,
                ml.location_dest_id.id,
                ml.lot_id.id if ml.lot_id else False,
            )
            if key not in grouped:
                grouped[key] = {
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
            product_id, location_id, lot_id = key

            domain = [
                ('product_id', '=', product_id),
                ('location_id', '=', location_id),
                ('quantity', '>', 0),
            ]
            if lot_id:
                domain.append(('lot_id', '=', lot_id))

            quants = self.env['stock.quant'].search(domain)
            if not quants:
                continue

            available = (
                sum(quants.mapped('quantity'))
                - sum(quants.mapped('reserved_quantity'))
            )
            qty = min(data['qty'], available)

            if qty <= 0:
                continue

            loc_name = data['location_name']
            if 'Cuarentena' not in loc_name:
                continue

            storage_name = loc_name.replace(
                'Cuarentena', 'Stock/Almacenaje'
            )
            storage_loc = self.env['stock.location'].search([
                ('complete_name', '=', storage_name),
                ('usage', '=', 'internal'),
            ], limit=1)

            if not storage_loc:
                continue

            data['qty'] = qty
            data['storage_location_id'] = storage_loc.id
            result.append(data)

        return result

    def _create_release_pickings(self, lines):
        """
        Crea picking(s) Cuarentena → Almacenaje.

        NO llama button_validate() porque:
        1. button_validate dispara nuestro override de Rackeos
           que intenta buscar la PO y redirigir ubicaciones
        2. button_validate dispara cálculo de valoración de
           inventario (quantity_svl) que genera una query SQL
           enorme dentro de la misma transacción → memory exhausted

        En su lugar: confirma, reserva, asigna cantidades y
        usa _action_done() que es el método interno de Odoo
        para completar moves sin pasar por la UI.
        """
        self.ensure_one()

        warehouse = self.picking_type_id.warehouse_id
        if not warehouse:
            warehouse = self.env['stock.warehouse'].search([], limit=1)

        pick_type = self.env['stock.picking.type'].search([
            ('warehouse_id', '=', warehouse.id),
            ('code', '=', 'internal'),
        ], limit=1)

        if not pick_type:
            raise UserError(
                'No se encontró tipo de operación interna '
                'para el almacén %s.' % warehouse.name
            )

        groups = {}
        for line in lines:
            key = (line['location_id'], line['storage_location_id'])
            groups.setdefault(key, []).append(line)

        pickings = self.env['stock.picking']

        for (src_id, dest_id), group_lines in groups.items():
            moves = []
            for line in group_lines:
                moves.append((0, 0, {
                    'name': 'COMEX: %s' % line['product_name'],
                    'product_id': line['product_id'],
                    'product_uom_qty': line['qty'],
                    'product_uom': line['uom_id'],
                    'location_id': src_id,
                    'location_dest_id': dest_id,
                }))

            picking = self.env['stock.picking'].create({
                'picking_type_id': pick_type.id,
                'location_id': src_id,
                'location_dest_id': dest_id,
                'origin': 'COMEX: %s' % self.name,
                'comex_source_po_id': self.id,
                'move_ids': moves,
            })

            # Confirmar y reservar
            picking.action_confirm()
            picking.action_assign()

            # Asignar cantidades hechas y lotes en las move_lines
            for move in picking.move_ids:
                # Buscar la línea original para obtener el lote
                original = next(
                    (l for l in group_lines
                     if l['product_id'] == move.product_id.id),
                    None
                )
                move.quantity = move.product_uom_qty
                if original and original.get('lot_id'):
                    for ml in move.move_line_ids:
                        ml.lot_id = original['lot_id']

            # Validar con _action_done (interno, sin UI, sin
            # pasar por nuestro override de button_validate)
            picking.with_context(
                skip_backorder=True,
                cancel_backorder=True,
            )._action_done()

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