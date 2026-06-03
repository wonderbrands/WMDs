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

    @api.model
    def create(self, vals):
        if vals.get('log'):
            vals['log'] = vals['log'].replace('\n', ' ').replace('\r', ' ').strip()
        
        # Resolve correct operator/user
        current_user_id = vals.get('user')
        resolved_user_id = None

        # Check if there is an active HTTP request and get the actual logged-in user
        from odoo.http import request
        try:
            if request and request.env and request.env.user:
                public_user = self.env.ref('base.public_user', raise_if_not_found=False)
                if not public_user or request.env.user.id != public_user.id:
                    resolved_user_id = request.env.user.id
        except Exception:
            pass

        # If not resolved from request, check if the passed user is a real user (not superuser/system)
        root_user = self.env.ref('base.user_root', raise_if_not_found=False)
        admin_user = self.env.ref('base.user_admin', raise_if_not_found=False)
        system_ids = [u.id for u in [root_user, admin_user] if u]

        if not resolved_user_id:
            if current_user_id and current_user_id not in system_ids:
                resolved_user_id = current_user_id

        # If still not resolved (or resolved as system user), try to fallback to the linked record's operator
        if not resolved_user_id or resolved_user_id in system_ids:
            if vals.get('pick'):
                pick = self.env['stock.picking'].sudo().browse(vals['pick'])
                if pick.exists() and pick.operator:
                    resolved_user_id = pick.operator.id
            elif vals.get('batch_pick'):
                batch = self.env['stock.picking.batch'].sudo().browse(vals['batch_pick'])
                if batch.exists() and batch.operator:
                    resolved_user_id = batch.operator.id

        # Last fallback
        if not resolved_user_id:
            resolved_user_id = current_user_id or self.env.user.id

        vals['user'] = resolved_user_id

        # Original log record
        log = super(WMDSLog, self).create(vals)
        
        # Avoid recursion if we are already duplicating or if propagation is disabled
        if self.env.context.get('wmds_log_duplicating') or self.env.context.get('wmds_log_no_propagate'):
            return log

        # Propagation logic
        self._propagate_log(log, vals)
        
        return log

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
                # Check if an identical log already exists on this target record
                existing = self.sudo().search([
                    (model, '=', res_id),
                    ('log', '=', log.log),
                ], limit=1)
                if existing:
                    continue
                
                new_vals = new_vals_base.copy()
                new_vals[model] = res_id
                self.with_context(wmds_log_duplicating=True).create(new_vals)

    def write(self, vals):
        if vals.get('log'):
            vals['log'] = vals['log'].replace('\n', ' ').replace('\r', ' ').strip()
        return super(WMDSLog, self).write(vals)
