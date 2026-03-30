# -*- coding: utf-8 -*-
from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)

class WMDSStockStatus(models.Model):
    _name = 'wmds.stock.status'
    _description = 'Estados WMDS'

    name = fields.Char('Name', required=True)
    value = fields.Char('Value', required=True)

class StockWMDS(models.Model):
    _inherit = 'stock.picking'

    operator = fields.Many2one('res.users', 'Operator')
    wmds_status = fields.Many2one('wmds.stock.status', 'WMDS Status')
    wmds_log = fields.One2many('wmds.log', 'pick', string='WMDS Log')
    marketplace_location = fields.Many2one("stock.location", string="Ubicación del marketplace")
    picking_type_id_name = fields.Char(related='picking_type_id.name', string='Operation Type Name', store=True)

    @api.model
    def create(self, vals):
        # Propagate marketplace_location to DFUL if created from PFUL
        if 'picking_type_id' in vals:
            picking_type = self.env['stock.picking.type'].browse(vals['picking_type_id'])
            if picking_type.name and 'Resurtido a Ful: Despacho' in picking_type.name:
                # Look for a related PFUL picking via Sale Order or Origin
                sale_id = vals.get('sale_id')
                origin = vals.get('origin')
                domain = [
                    ('picking_type_id.name', '=', 'Resurtido a Ful: Pick'),
                    ('marketplace_location', '!=', False)
                ]
                if sale_id:
                    domain.append(('sale_id', '=', sale_id))
                elif origin:
                    domain.append(('origin', '=', origin))
                else:
                    domain = [] # Can't link if both are missing
                
                if domain:
                    pful_pick = self.env['stock.picking'].search(domain, limit=1)
                    if pful_pick:
                        vals['marketplace_location'] = pful_pick.marketplace_location.id
                        vals['location_dest_id'] = pful_pick.marketplace_location.id
                        # If moves are in vals, update their destination location too
                        if 'move_ids' in vals:
                            for move in vals['move_ids']:
                                if move[0] in (0, 1): # Create or Update
                                    move[2]['location_dest_id'] = pful_pick.marketplace_location.id

        res = super(StockWMDS, self).create(vals)
        # For existing moves not in vals['move_ids'] (if any, though unlikely for create)
        if res.marketplace_location and res.picking_type_id_name == 'Resurtido a Ful: Despacho':
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
        ('mix', "Mixto")
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

            # si todos los traslados son de tipo pick, el batch es de tipo sale
            total_picks = len(record.picking_ids.filtered(lambda pick: pick.picking_type_id.name == "Pick"))
            if total_picks == total_operations:
                record.pick_type = "sale"
                continue

            # si todos son de tipo full, es de tipo full
            total_full = len(record.picking_ids.filtered(lambda pick: pick.picking_type_id.name in ["Resurtido a Ful: Pick"]))
            if total_full == total_operations:
                record.pick_type = "full"
                continue

            # si no concuerdan, son mixtos
            record.pick_type = "mix"
            

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