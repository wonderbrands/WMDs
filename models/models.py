# -*- coding: utf-8 -*-
from odoo import models, fields, api

class WMDSStockStatus(models.Model):
    _name = 'wmds.stock.status'

    name = fields.Char('Name', required=True)
    value = fields.Char('Value', required=True)

class WMDSLog(models.Model):
    _name = 'wmds.log'

    pick = fields.Many2one('stock.picking', 'Pick')
    log = fields.Text('Log')
    date = fields.Datetime('Date')
    user = fields.Many2one('res.users', 'User')

class StockWMDS(models.Model):
    _inherit = 'stock.picking'

    operator = fields.Many2one('res.users', 'Operator')
    wmds_status = fields.Many2one('wmds.stock.status', 'WMDS Status')
    wmds_log = fields.One2many('wmds.log', 'pick', 'WMDS Log')

    @api.model
    def create(self, vals):
        res = super(StockWMDS, self).create(vals)
        not_assigned = self.env['wmds.stock.status'].search([('value', '=', 'not_assigned')], limit=1)
        if not not_assigned:
            return res
        if not res.operator:
            res.wmds_status = not_assigned
        return res