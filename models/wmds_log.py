# -*- coding: utf-8 -*-
from odoo import models, fields, api
from datetime import datetime
from odoo.exceptions import UserError
import logging
import requests

_logger = logging.getLogger(__name__)


class WMDSLog(models.Model):
    _name = 'wmds.log'
    _description = 'Log compartido WMDS'

    pick = fields.Many2one('stock.picking', 'Pick')
    purchase = fields.Many2one('purchase.order', 'Purchase Order')
    sale = fields.Many2one('sale.order', "Sale order")
    batch_pick = fields.Many2one('stock.picking.batch', 'Lote de picks')

    log = fields.Text('Log')
    date = fields.Datetime('Date', default=fields.Datetime.now) # Default automático
    user = fields.Many2one('res.users', 'User')

    @api.model
    def create(self, vals):
        # Using create override to make it transparent
        log = super(WMDSLog, self).create(vals)
        
        if self.env.context.get('wmds_log_duplicating'):
            return log

        new_vals = vals.copy()
        new_vals.pop('pick', None)
        new_vals.pop('purchase', None)
        new_vals.pop('sale', None)
        new_vals.pop('batch_pick', None)

        if log.pick:
            picking = log.pick
            if picking.sale_id:
                new_vals['sale'] = picking.sale_id.id
                self.with_context(wmds_log_duplicating=True).create(new_vals)
            elif picking.purchase_id:
                new_vals['purchase'] = picking.purchase_id.id
                self.with_context(wmds_log_duplicating=True).create(new_vals)
        
        elif log.sale:
            order = log.sale
            for picking in order.picking_ids:
                new_vals_picking = new_vals.copy()
                new_vals_picking['pick'] = picking.id
                self.with_context(wmds_log_duplicating=True).create(new_vals_picking)

        elif log.purchase:
            order = log.purchase
            for picking in order.picking_ids:
                new_vals_picking = new_vals.copy()
                new_vals_picking['pick'] = picking.id
                self.with_context(wmds_log_duplicating=True).create(new_vals_picking)

        elif log.batch_pick:
            batch = log.batch_pick
            for picking in batch.picking_ids:
                new_vals_picking = new_vals.copy()
                new_vals_picking['pick'] = picking.id
                self.with_context(wmds_log_duplicating=True).create(new_vals_picking)

        return log