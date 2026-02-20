# -*- coding: utf-8 -*-
from odoo import models, fields, api
from datetime import datetime
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
        
        if not res.get('records'):
            res['records'] = {}
        if 'stock.picking' not in res['records']:
            res['records']['stock.picking'] = []

        for field in ['operator', 'picking_type_id_name']:
            if field not in res['records']['stock.picking']:
                res['records']['stock.picking'].append(field)

        models_data = res.get('models', {})
        picking_models = models_data.get('stock.picking', [])
        
        for picking_data in picking_models:
            picking_real = self.browse(picking_data.get('id'))
            if picking_real.exists():
                picking_data['picking_type_id_name'] = picking_real.picking_type_id.name
            
        return res


class BatchWMDS(models.Model):
    _inherit = 'stock.picking.batch'

    operator = fields.Many2one('res.users', 'Operator')
    wmds_log = fields.One2many('wmds.log', 'batch_pick', string='WMDS Log')

    def _get_stock_barcode_data(self):
        res = super()._get_stock_barcode_data()
        
        records_data = res.get('records', {})
        if 'stock.picking' in records_data:
            for field in ['operator', 'picking_type_id_name']:
                if field not in records_data['stock.picking']:
                    records_data['stock.picking'].append(field)
        
        models_data = res.get('models', {})
        picking_models = models_data.get('stock.picking', [])
        
        for picking_data in picking_models:
            picking_real = self.env['stock.picking'].browse(picking_data.get('id'))
            if picking_real.exists():
                picking_data['picking_type_id_name'] = picking_real.picking_type_id.name
                
        return res