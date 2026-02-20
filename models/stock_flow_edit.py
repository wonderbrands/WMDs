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
        if 'operator' not in res['records']['stock.picking']:
            res['records']['stock.picking'].append('operator')
        return res


class BatchWMDS(models.Model):
    _inherit = 'stock.picking.batch'

    operator = fields.Many2one('res.users', 'Operator')
    wmds_log = fields.One2many('wmds.log', 'batch_pick', string='WMDS Log')

    def _get_stock_barcode_data(self):
        res = super()._get_stock_barcode_data()
        if 'stock.picking' in res['records'] and 'operator' not in res['records']['stock.picking']:
            res['records']['stock.picking'].append('operator')
            
        res['records']['stock.picking.batch'].append('operator')
        
        return res