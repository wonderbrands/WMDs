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
    cycle_count = fields.Many2one('scheduled.cycle.count', 'Conteo Cíclico')

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
            
            # Record log into Sale/Purchase Orders
            if picking.sale_id:
                new_vals_sale = new_vals.copy()
                new_vals_sale['sale'] = picking.sale_id.id
                self.with_context(wmds_log_duplicating=True).create(new_vals_sale)
            elif picking.purchase_id:
                new_vals_purchase = new_vals.copy()
                new_vals_purchase['purchase'] = picking.purchase_id.id
                self.with_context(wmds_log_duplicating=True).create(new_vals_purchase)
            elif picking.origin:
                if picking.origin.startswith('S'):
                    so = self.env['sale.order'].search([('name', '=', picking.origin)], limit=1)
                    if so:
                        new_vals_sale = new_vals.copy()
                        new_vals_sale['sale'] = so.id
                        self.with_context(wmds_log_duplicating=True).create(new_vals_sale)
                elif picking.origin.startswith('P'):
                    po = self.env['purchase.order'].search([('name', '=', picking.origin)], limit=1)
                    if po:
                        new_vals_purchase = new_vals.copy()
                        new_vals_purchase['purchase'] = po.id
                        self.with_context(wmds_log_duplicating=True).create(new_vals_purchase)
            
            # Record log into Batch Picking
            if picking.batch_id:
                new_vals_batch = new_vals.copy()
                new_vals_batch['batch_pick'] = picking.batch_id.id
                self.with_context(wmds_log_duplicating=True).create(new_vals_batch)

        elif log.batch_pick:
            batch = log.batch_pick
            for picking in batch.picking_ids:
                new_vals_picking = new_vals.copy()
                new_vals_picking['pick'] = picking.id
                self.with_context(wmds_log_duplicating=True).create(new_vals_picking)

        return log