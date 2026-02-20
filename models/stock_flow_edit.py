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
        
        # En Odoo, esto es una lista de diccionarios con los datos del registro
        picking_records = res.get('records', {}).get('stock.picking', [])
        
        for picking_data in picking_records:
            picking_id = picking_data.get('id')
            if picking_id:
                picking_real = self.env['stock.picking'].browse(picking_id)
                # Inyectamos nuestros valores custom directamente al diccionario
                picking_data['picking_type_id_name'] = picking_real.picking_type_id.name
                if picking_real.operator:
                    # Formateamos el Many2one como [ID, "Nombre"] para que OWL lo entienda
                    picking_data['operator'] = [picking_real.operator.id, picking_real.operator.name]
                else:
                    picking_data['operator'] = False
        
        return res

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