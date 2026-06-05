# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError
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
    bin_id = fields.Many2one('bin.storage', string='BIN')
    wmds_status = fields.Many2one('wmds.stock.status', 'WMDS Status')
    wmds_log = fields.One2many('wmds.log', 'pick', string='WMDS Log')
    picking_type_id_name = fields.Char(related='picking_type_id.name', string='Operation Type Name', store=False)

    def button_validate(self):
        # 1. Enforce that destination locations for Rackeo pickings must be empty before validation
        for picking in self:
            if picking.picking_type_id.name in ('Rackeo', 'Rackeos'):
                active_moves = picking.move_ids.filtered(
                    lambda m: getattr(m, 'quantity', getattr(m, 'quantity_done', 0.0)) > 0
                )
                dest_locations = active_moves.mapped('location_dest_id')
                for loc in dest_locations:
                    if loc.usage == 'internal':
                        is_n1 = loc.name and loc.name.upper().endswith('N1')
                        quants = self.env['stock.quant'].search([
                            ('location_id', '=', loc.id),
                            ('quantity', '>', 0)
                        ])
                        if quants:
                            if is_n1:
                                existing_product_ids = quants.mapped('product_id.id')
                                moves_for_loc = active_moves.filtered(lambda m: m.location_dest_id.id == loc.id)
                                for move in moves_for_loc:
                                    if move.product_id.id not in existing_product_ids:
                                        raise UserError(f"El SKU a rackear debe ser el mismo que ya contiene la ubicación.")
                            else:
                                raise UserError(f"No se puede rackear en la ubicación '{loc.complete_name}' porque no está vacía.")
        return super(StockWMDS, self).button_validate()

    @api.model
    def create(self, vals):
        res = super(StockWMDS, self).create(vals)

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

        if 'bin_id' in vals:
            for record in self:
                new_bin_id = vals.get('bin_id')
                if new_bin_id:
                    bin_record = self.env['bin.storage'].sudo().browse(new_bin_id)
                    # Propagate to moves
                    record.move_ids.write({
                        'bin_id': new_bin_id,
                        'on_bin': True
                    })
                    self.env['wmds.log'].sudo().create({
                        'pick': record.id,
                        'log': f"BIN asignado manualmente: {bin_record.name}",
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
    bin_id = fields.Many2one('bin.storage', string='BIN')
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
                # si todas las ventas son de tipo mayoreo, es de tipo wholesale
                so_wholesales = len(record.picking_ids.filtered(lambda p: p.sale_id.data_is_wholesale_sale))
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

        if 'bin_id' in vals:
            for record in self:
                new_bin_id = vals.get('bin_id')
                if new_bin_id:
                    bin_record = self.env['bin.storage'].sudo().browse(new_bin_id)
                    # Propagate to pickings and moves
                    record.picking_ids.write({'bin_id': new_bin_id})
                    record.picking_ids.mapped('move_ids').write({
                        'bin_id': new_bin_id,
                        'on_bin': True
                    })
                    self.env['wmds.log'].sudo().create({
                        'batch_pick': record.id,
                        'log': f"BIN asignado manualmente al lote: {bin_record.name}",
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
class StockMoveWMDS(models.Model):
    _inherit = 'stock.move'

    def write(self, vals):
        for move in self:
            changes = []
            if 'location_id' in vals:
                new_loc = self.env['stock.location'].sudo().browse(vals['location_id'])
                changes.append(f"Origen: {move.location_id.display_name} -> {new_loc.display_name}")
            if 'location_dest_id' in vals:
                new_loc = self.env['stock.location'].sudo().browse(vals['location_dest_id'])
                changes.append(f"Destino: {move.location_dest_id.display_name} -> {new_loc.display_name}")
            
            if changes and move.picking_id:
                msg = f"Movimiento modificado ({move.product_id.name}): " + ", ".join(changes)
                self.env['wmds.log'].sudo().create({
                    'pick': move.picking_id.id,
                    'log': msg,
                    'user': self.env.user.id,
                })
        return super(StockMoveWMDS, self).write(vals)

class StockMoveLineWMDS(models.Model):
    _inherit = 'stock.move.line'

    _FORBIDDEN_LOCATIONS = {"WH/Stock/A_Pickable"}
    #_FORBIDDEN_LOCATIONS = []

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._check_forbidden_locations(vals)
        return super(StockMoveLineWMDS, self).create(vals_list)

    def write(self, vals):
        self._check_forbidden_locations(vals)
        return super(StockMoveLineWMDS, self).write(vals)

    def _check_forbidden_locations(self, vals):
        loc_id = vals.get('location_id')
        dest_id = vals.get('location_dest_id')
        quant_id = vals.get('quant_id')

        if loc_id:
            loc = self.env['stock.location'].sudo().browse(loc_id)
            if loc.complete_name and loc.complete_name.strip() in self._FORBIDDEN_LOCATIONS:
                raise UserError(f"Error al guardar: La ubicación '{loc.complete_name}' es una ubicación padre y no puede ser usada como origen en una línea de movimiento.")

        if dest_id:
            dest = self.env['stock.location'].sudo().browse(dest_id)
            if dest.complete_name and dest.complete_name.strip() in self._FORBIDDEN_LOCATIONS:
                raise UserError(f"Error al guardar: La ubicación '{dest.complete_name}' es una ubicación padre y no puede ser usada como destino en una línea de movimiento.")

        if quant_id:
            quant = self.env['stock.quant'].sudo().browse(quant_id)
            if quant.location_id and quant.location_id.complete_name and quant.location_id.complete_name.strip() in self._FORBIDDEN_LOCATIONS:
                raise UserError(f"Error al guardar: El stock seleccionado pertenece a la ubicación padre '{quant.location_id.complete_name}', lo cual no está permitido.")