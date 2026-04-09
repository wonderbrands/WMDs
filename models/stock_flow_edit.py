# -*- coding: utf-8 -*-
from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)

class WMDSStockStatus(models.Model):
    _name = 'wmds.stock.status'
    _description = 'Estados WMDS'

    name = fields.Char('Name', required=True)
    value = fields.Char('Value', required=True)


class StockLocationWMDS(models.Model):
    _inherit = 'stock.location'

    block_reason = fields.Char(string='Motivo de Bloqueo', db_column='block_reason_text')
    original_parent_id = fields.Many2one('stock.location', string='Ubicación padre original')

    def action_open_block_wizard(self):
        self.ensure_one()
        return {
            'name': 'Bloquear Ubicación',
            'type': 'ir.actions.act_window',
            'res_model': 'stock.location.block.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_location_id': self.id,
            }
        }

    def action_unblock(self):
        self.ensure_one()
        vals = {
            'block_reason': False,
        }
        if self.original_parent_id:
            vals['location_id'] = self.original_parent_id.id
            vals['original_parent_id'] = False
        
        self.sudo().write(vals)
        return True

class StockWMDS(models.Model):
    _inherit = 'stock.picking'

    operator = fields.Many2one('res.users', 'Operator')
    wmds_status = fields.Many2one('wmds.stock.status', 'WMDS Status')
    wmds_log = fields.One2many('wmds.log', 'pick', string='WMDS Log')
    marketplace_location = fields.Many2one("stock.location", string="Ubicación del marketplace")
    picking_type_id_name = fields.Char(related='picking_type_id.name', string='Operation Type Name', store=False)

    @api.model
    def create(self, vals):
        # Propagate marketplace_location to DFUL if created from PFUL
        if 'picking_type_id' in vals:
            picking_type = self.env['stock.picking.type'].browse(vals['picking_type_id'])
            if picking_type.name and 'Resurtido a Ful: Despacho' in picking_type.name:
                # Look for related PFUL pickings via Moves, Sale Order, or Origin
                sale_id = vals.get('sale_id')
                origin = vals.get('origin')
                pful_pick = self.env['stock.picking']

                # 1. Try finding via moves in vals (most direct link)
                if 'move_ids' in vals:
                    orig_move_ids = []
                    for move_cmd in vals['move_ids']:
                        if move_cmd[0] in (0, 1) and isinstance(move_cmd[2], dict) and 'move_orig_ids' in move_cmd[2]:
                            for orig_cmd in move_cmd[2]['move_orig_ids']:
                                if orig_cmd[0] == 4:
                                    orig_move_ids.append(orig_cmd[1])
                                elif orig_cmd[0] == 6:
                                    orig_move_ids.extend(orig_cmd[2])
                    
                    if orig_move_ids:
                        # Find PFUL pickings that contain these origin moves
                        pful_pick = self.env['stock.move'].sudo().browse(orig_move_ids).mapped('picking_id').filtered(
                            lambda p: 'Resurtido a Ful: Pick' in (p.picking_type_id.name or '') and p.marketplace_location
                        )

                # 2. If not found via moves, try sale_id or origin
                if not pful_pick:
                    domain = [
                        ('picking_type_id.name', 'ilike', 'Resurtido a Ful: Pick'),
                        ('marketplace_location', '!=', False)
                    ]
                    if sale_id:
                        domain.append(('sale_id', '=', sale_id))
                        pful_pick = self.env['stock.picking'].search(domain, order='id asc', limit=1)
                    elif origin:
                        domain.append(('origin', '=', origin))
                        pful_pick = self.env['stock.picking'].search(domain, order='id asc', limit=1)

                if pful_pick:
                    # If multiple found (e.g. via moves), take the first one as requested
                    pful_pick = pful_pick[0]
                    vals['marketplace_location'] = pful_pick.marketplace_location.id
                    vals['location_dest_id'] = pful_pick.marketplace_location.id
                    # If moves are in vals, update their destination location too
                    if 'move_ids' in vals:
                        for move in vals['move_ids']:
                            if move[0] in (0, 1) and isinstance(move[2], dict):
                                move[2]['location_dest_id'] = pful_pick.marketplace_location.id

        res = super(StockWMDS, self).create(vals)
        # Log propagation if it happened
        if res.marketplace_location and res.picking_type_id.name and 'Resurtido a Ful: Despacho' in res.picking_type_id.name:
            self.env['wmds.log'].sudo().create({
                'pick': res.id,
                'log': f"Ubicación de destino del marketplace asignada automáticamente: {res.marketplace_location.complete_name}",
                'user': self.env.user.id,
            })

        # For existing moves not in vals['move_ids'] (if any, though unlikely for create)
        if res.marketplace_location and res.picking_type_id.name and 'Resurtido a Ful: Despacho' in res.picking_type_id.name:
            res.move_ids.write({'location_dest_id': res.marketplace_location.id})

        if not res.operator:
            not_assigned = self.env['wmds.stock.status'].search([('value', '=', 'not_assigned')], limit=1)
            if not_assigned:
                res.wmds_status = not_assigned.id
        else:
            # Log initial assignment if operator is provided in create
            self.env['wmds.log'].sudo().create({
                'pick': res.id,
                'log': f"Operador asignado: {res.operator.name}",
                'user': self.env.user.id,
            })
        return res

    def write(self, vals):
        if 'operator' in vals:
            for record in self:
                old_operator = record.operator
                new_operator_id = vals.get('operator')
                
                if new_operator_id:
                    new_operator = self.env['res.users'].sudo().browse(new_operator_id)
                    if old_operator:
                        if old_operator.id != new_operator.id:
                            msg = f"Operador reasignado: de {old_operator.name} a {new_operator.name}"
                        else:
                            continue # No change
                    else:
                        msg = f"Operador asignado: {new_operator.name}"
                else:
                    if old_operator:
                        msg = f"Operador desasignado: era {old_operator.name}"
                    else:
                        continue # No change
                
                self.env['wmds.log'].sudo().create({
                    'pick': record.id,
                    'log': msg,
                    'user': self.env.user.id,
                })

        return super(StockWMDS, self).write(vals)

    def _get_stock_barcode_data(self):
        res = super()._get_stock_barcode_data()

        picking_records = res.get('records', {}).get('stock.picking', [])

        if picking_records:
            picking_ids = [p['id'] for p in picking_records if p.get('id')]
            # Use search_read to only fetch needed fields and avoid hitting non-existent columns
            picking_info = self.env['stock.picking'].sudo().search_read(
                [('id', 'in', picking_ids)],
                ['picking_type_id', 'operator']
            )
            picking_info_map = {p['id']: p for p in picking_info}

            for picking_data in picking_records:
                p_id = picking_data.get('id')
                if p_id in picking_info_map:
                    info = picking_info_map[p_id]
                    picking_data['picking_type_id_name'] = info['picking_type_id'][1] if info.get('picking_type_id') else False
                    if info.get('operator'):
                        picking_data['operator'] = [info['operator'][0], info['operator'][1]]
                    else:
                        picking_data['operator'] = False

        return res


    def action_imprimir_guia(self):
        self.ensure_one()
        sale_order = self.sale_id        
        if not sale_order:
            raise UserError("No se encontró un Pedido de Venta asociado a esta transferencia.")

        report = self.env.ref('wb_printer_IoT.action_report_print_attachment_4x8', raise_if_not_found=False)
        if not report:
            raise UserError("No se encontró el reporte wb_printer_IoT.action_report_print_attachment_4x6.")
            
        return report.report_action(sale_order)

    def action_print_tag(self):
        self.ensure_one()
        
        sale_order = self.sale_id
        if not sale_order:
            raise UserError("No se encontró un Pedido de Venta asociado a esta transferencia.")

        report = self.env.ref('wb_printer_IoT.action_report_zpl_backup', raise_if_not_found=False)
        if not report:
            raise UserError("No se encontró el reporte wb_printer_IoT.action_report_custom_2x1.")
            
        return report.report_action(sale_order)

class BatchWMDS(models.Model):
    _inherit = 'stock.picking.batch'

    operator = fields.Many2one('res.users', 'Operator')
    wmds_log = fields.One2many('wmds.log', 'batch_pick', string='WMDS Log')
    pick_type = fields.Selection(selection = [
        ('sale', 'Pedido'), 
        ('full', 'Full'),
        ('mix', "Mixto"),
        ('wholesale', 'Mayoreo')
    ],
        compute='_establish_pick_type',
        store=True)


    @api.depends("picking_ids")
    def _establish_pick_type(self):
        for record in self:
            total_operations = len(record.picking_ids)
            if total_operations == 0:
                record.pick_type = "mix"
                continue

            # si todos los traslados son de tipo pick, el batch es de tipo sale o mayoreo
            total_picks = len(record.picking_ids.filtered(lambda pick: pick.picking_type_id.name == "Pick"))
            if total_picks == total_operations:
                #si todas las ventas son de tipo mayoreo, es de tipo wholesale
                so_strings = record.picking_ids.mapped(lambda pick: pick.origin)
                so_s = [self.env['sale.order'].search([('name', '=', so)]) for so in so_strings]
                so_wholesales = len(list(so_s.filter(lambda so: so.data_is_wholesale_sale)))
                if so_wholesales == total_operations:
                    record.pick_type = "wholesale"
                    continue
                record.pick_type = "sale"
                continue

            # si todos son de tipo full, es de tipo full
            total_full = len(record.picking_ids.filtered(lambda pick: pick.picking_type_id.name in ["Resurtido a Ful: Pick"]))
            if total_full == total_operations:
                record.pick_type = "full"
                continue

            # si no concuerdan, son mixtos
            record.pick_type = "mix"

    def _get_stock_barcode_data(self):
        res = super()._get_stock_barcode_data()
        batch_records = res.get('records', {}).get('stock.picking.batch', [])
        for batch_data in batch_records:
            batch_id = batch_data.get('id')
            if batch_id:
                batch_real = self.env['stock.picking.batch'].browse(batch_id)
                batch_data['pick_type'] = batch_real.pick_type
        return res
            

    def action_exclude_unstarted_pickings(self):
        self.ensure_one()
        pickings_to_remove = self.env['stock.picking']
        for pick in self.picking_ids:
            # Solo removemos si está COMPLETAMENTE sin tocar (todo qty_done == 0)
            has_started = any(ml.quantity > 0 or ml.qty_done > 0 for ml in pick.move_line_ids)
            if not has_started:
                pickings_to_remove |= pick
        
        if pickings_to_remove:
            batch_name = self.name
            for pick in pickings_to_remove:
                msg = f"Se excluyó el pick {pick.name} del plan de pickeo {batch_name} al no poder escanear todos los productos, queda libre para agregar a otro plan"
                self.env['wmds.log'].sudo().create({
                    'pick': pick.id,
                    'batch_pick': self.id,
                    'log': msg,
                    'user': self.env.user.id,
                })
            pickings_to_remove.write({'batch_id': False})
        return True

    @api.model
    def create(self, vals):
        res = super(BatchWMDS, self).create(vals)
        if res.operator:
            self.env['wmds.log'].sudo().create({
                'batch_pick': res.id,
                'log': f"Operador asignado al lote: {res.operator.name}",
                'user': self.env.user.id,
            })
        return res

    def write(self, vals):
        if 'operator' in vals:
            for record in self:
                old_operator = record.operator
                new_operator_id = vals.get('operator')
                
                if new_operator_id:
                    new_operator = self.env['res.users'].sudo().browse(new_operator_id)
                    if old_operator:
                        if old_operator.id != new_operator.id:
                            msg = f"Operador del lote reasignado: de {old_operator.name} a {new_operator.name}"
                        else:
                            continue
                    else:
                        msg = f"Operador asignado al lote: {new_operator.name}"
                else:
                    if old_operator:
                        msg = f"Operador del lote desasignado: era {old_operator.name}"
                    else:
                        continue
                
                self.env['wmds.log'].sudo().create({
                    'batch_pick': record.id,
                    'log': msg,
                    'user': self.env.user.id,
                })

        return super(BatchWMDS, self).write(vals)

    def _get_stock_barcode_data(self):
        res = super()._get_stock_barcode_data()
        
        batch_records = res.get('records', {}).get('stock.picking.batch', [])
        for batch_data in batch_records:
            batch_id = batch_data.get('id')
            if batch_id:
                batch_real = self.env['stock.picking.batch'].browse(batch_id)
                batch_data['pick_type'] = batch_real.pick_type
                if batch_real.operator:
                    batch_data['operator'] = [batch_real.operator.id, batch_real.operator.name]
                else:
                    batch_data['operator'] = False

        picking_records = res.get('records', {}).get('stock.picking', [])
        
        for picking_data in picking_records:
            picking_id = picking_data.get('id')
            if picking_id:
                picking_real = self.env['stock.picking'].browse(picking_id)
                picking_data['picking_type_id_name'] = picking_real.picking_type_id.name
                if picking_real.operator:
                    picking_data['operator'] = [picking_real.operator.id, picking_real.operator.name]
                else:
                    picking_data['operator'] = False
                    
        return res