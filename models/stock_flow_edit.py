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

    @api.model
    def create(self, vals):
        res = super(StockWMDS, self).create(vals)
        if not res.operator:
            not_assigned = self.env['wmds.stock.status'].search([('value', '=', 'not_assigned')], limit=1)
            if not_assigned:
                res.wmds_status = not_assigned.id
        return res

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

        report = self.env.ref('wb_printer_IoT.report_zpl_backup', raise_if_not_found=False)
        if not report:
            raise UserError("No se encontró el reporte wb_printer_IoT.action_report_custom_2x1.")
            
        return report.report_action(sale_order)

class BatchWMDS(models.Model):
    _inherit = 'stock.picking.batch'

    operator = fields.Many2one('res.users', 'Operator')
    wmds_log = fields.One2many('wmds.log', 'batch_pick', string='WMDS Log')

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