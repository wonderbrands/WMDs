# -*- coding: utf-8 -*-
from odoo import models, fields, api

class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    wmds_picked_qty = fields.Float(string='WMDS Picked Quantity', default=0.0, copy=False)
    picked = fields.Boolean(string='Recogido', default=False, copy=False)

    def write(self, vals):
        if 'wmds_picked_qty' in vals:
            for record in self:
                old_picked = record.wmds_picked_qty
                new_picked = vals['wmds_picked_qty']
                if old_picked != new_picked:
                    # Calculate missing (using 'quantity' which is the standard field in Odoo 17+)
                    # In Odoo 17+, 'quantity' is the field for the amount to be moved.
                    remaining = record.quantity - new_picked
                    
                    # Log the change in WMDS log
                    message = f"Producto {record.product_id.display_name}: Cantidad recogida actualizada de {old_picked} a {new_picked}, faltan {remaining}"
                    log_vals = {
                        'user': self.env.user.id,
                        'log': message,
                    }
                    if record.picking_id:
                        log_vals['pick'] = record.picking_id.id
                    if record.batch_id:
                        log_vals['batch_pick'] = record.batch_id.id
                    
                    self.env['wmds.log'].sudo().create(log_vals)
        return super(StockMoveLine, self).write(vals)

class StockMove(models.Model):
    _inherit = 'stock.move'

    wmds_picked_qty = fields.Float(string='Recolectado (WMDS)', compute='_compute_wmds_picked_qty')

    @api.depends('move_line_ids.wmds_picked_qty')
    def _compute_wmds_picked_qty(self):
        for move in self:
            move.wmds_picked_qty = sum(move.move_line_ids.mapped('wmds_picked_qty'))
