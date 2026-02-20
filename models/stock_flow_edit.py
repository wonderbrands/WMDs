# -*- coding: utf-8 -*-
from odoo import models, fields, api
from datetime import datetime
from odoo.exceptions import UserError
import logging
import requests

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
        
        for field in ['operator', 'picking_type_id_name']:
            if field not in res['records']['stock.picking']:
                res['records']['stock.picking'].append(field)

        for picking_data in res['models']['stock.picking']:
            picking_real = self.browse(picking_data.get('id'))
            picking_data['picking_type_id_name'] = picking_real.picking_type_id.name
            
        return res


class BatchWMDS(models.Model):
    _inherit = 'stock.picking.batch'

    operator = fields.Many2one('res.users', 'Operator')
    wmds_log = fields.One2many('wmds.log', 'batch_pick', string='WMDS Log')

    def _get_stock_barcode_data(self):
        res = super()._get_stock_barcode_data()
        if 'stock.picking' in res['records']:
            for field in ['operator', 'picking_type_id_name']:
                if field not in res['records']['stock.picking']:
                    res['records']['stock.picking'].append(field)
        
        if 'stock.picking' in res['models']:
            for picking_data in res['models']['stock.picking']:
                picking_real = self.env['stock.picking'].browse(picking_data.get('id'))
                picking_data['picking_type_id_name'] = picking_real.picking_type_id.name
                
        return res