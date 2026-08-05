# -*- coding: utf-8 -*-
from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class WMDSLog(models.Model):
    _name = 'wmds.log'
    _description = 'Log compartido WMDS'
    _order = 'date desc, id desc'

    pick = fields.Many2one('stock.picking', 'Pick', ondelete='cascade')
    purchase = fields.Many2one('purchase.order', 'Purchase Order', ondelete='cascade')
    sale = fields.Many2one('sale.order', "Sale order", ondelete='cascade')
    batch_pick = fields.Many2one('stock.picking.batch', 'Lote de picks', ondelete='cascade')
    cycle_count = fields.Many2one('scheduled.cycle.count', 'Conteo Cíclico', ondelete='cascade')

    log = fields.Text('Log', required=True)
    date = fields.Datetime('Date', default=fields.Datetime.now, index=True)
    user = fields.Many2one('res.users', 'User')

    @api.model_create_multi
    def create(self, vals_list):
        if isinstance(vals_list, dict):
            vals_list = [vals_list]
        for vals in vals_list:
            if vals.get('log'):
                vals['log'] = vals['log'].replace('\n', ' ').replace('\r', ' ').strip()
        
        # Original log record
        logs = super(WMDSLog, self).create(vals_list)
        
        # Avoid recursion if we are already duplicating
        if self.env.context.get('wmds_log_duplicating'):
            return logs

        # Propagation logic
        for log, vals in zip(logs, vals_list):
            self._propagate_log(log, vals)
        
        return logs

    def _propagate_log(self, log, original_vals):
        """
        Propagates the log to related records to ensure consistency.
        We use a set of (model, id) to avoid duplicate logs in the same record.
        """
        target_records = set()
        
        # 1. Identify all related records
        
        # From Picking
        if log.pick:
            picking = log.pick
            if picking.sale_id:
                target_records.add(('sale', picking.sale_id.id))
            if picking.purchase_id:
                target_records.add(('purchase', picking.purchase_id.id))
            if picking.batch_id:
                target_records.add(('batch_pick', picking.batch_id.id))
            
            # Handle origin based linking if relations are missing
            if not picking.sale_id and not picking.purchase_id and picking.origin:
                if picking.origin.startswith('S'):
                    so = self.env['sale.order'].sudo().search([('name', '=', picking.origin)], limit=1)
                    if so:
                        target_records.add(('sale', so.id))
                elif picking.origin.startswith('P'):
                    po = self.env['purchase.order'].sudo().search([('name', '=', picking.origin)], limit=1)
                    if po:
                        target_records.add(('purchase', po.id))

        # From Batch
        if log.batch_pick:
            batch = log.batch_pick
            for picking in batch.picking_ids:
                if picking.sale_id:
                    target_records.add(('sale', picking.sale_id.id))
                if picking.purchase_id:
                    target_records.add(('purchase', picking.purchase_id.id))

        # From Sale Order
        if log.sale:
            so = log.sale
            # We don't propagate to all pickings to avoid noise, 
            # only to the batch if it exists and we want it there.
            pickings = self.env['stock.picking'].sudo().search([('sale_id', '=', so.id)])
            for pick in pickings:
                if pick.batch_id:
                    target_records.add(('batch_pick', pick.batch_id.id))

        # From Purchase Order
        if log.purchase:
            po = log.purchase
            pickings = self.env['stock.picking'].sudo().search([('purchase_id', '=', po.id)])
            for pick in pickings:
                if pick.batch_id:
                    target_records.add(('batch_pick', pick.batch_id.id))

        # 2. Filter out the original record to avoid self-duplication
        current_model = None
        for field in ['pick', 'purchase', 'sale', 'batch_pick', 'cycle_count']:
            if original_vals.get(field):
                current_model = field
                break
        
        if current_model and (current_model, original_vals[current_model]) in target_records:
            target_records.remove((current_model, original_vals[current_model]))

        # 3. Create duplicate logs
        if target_records:
            new_vals_base = original_vals.copy()
            # Clear all relation fields
            for field in ['pick', 'purchase', 'sale', 'batch_pick', 'cycle_count']:
                new_vals_base.pop(field, None)
            
            for model, res_id in target_records:
                new_vals = new_vals_base.copy()
                new_vals[model] = res_id
                self.with_context(wmds_log_duplicating=True).create(new_vals)

    def write(self, vals):
        if vals.get('log'):
            vals['log'] = vals['log'].replace('\n', ' ').replace('\r', ' ').strip()
        return super(WMDSLog, self).write(vals)
