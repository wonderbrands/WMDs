# -*- coding: utf-8 -*-
from odoo import models, fields, api

class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    wmds_picked_qty = fields.Float(string='WMDS Picked Quantity', default=0.0, copy=False)
    picked = fields.Boolean(string='Recogido', default=False, copy=False)

    def write(self, vals):
        suppress_logs = self.env.context.get('wmds_dispatch_in_progress')

        if 'wmds_picked_qty' in vals:
            for record in self:
                old_picked = record.wmds_picked_qty
                new_picked = vals['wmds_picked_qty']
                if old_picked != new_picked and not suppress_logs:
                    remaining = record.quantity - new_picked
                    
                    operator_email = self.env.context.get('wmds_operator_email')
                    action_desc = self.env.context.get('wmds_action_desc')
                    
                    user = False
                    if operator_email:
                        user = self.env['res.users'].sudo().search([('login', '=ilike', operator_email.strip())], limit=1)
                    if not user:
                        user = self.env.user
                        
                    if operator_email and action_desc:
                        increment = self.env.context.get('wmds_increment', 1)
                        message = f"Operador {action_desc} {abs(increment)} unidad(es) de {record.product_id.display_name} desde {record.location_id.display_name} (Cantidad recogida actualizada de {old_picked} a {new_picked}, faltan {remaining})"
                    else:
                        message = f"Producto {record.product_id.display_name}: Cantidad recogida actualizada de {old_picked} a {new_picked}, faltan {remaining}"
                    
                    log_vals = {
                        'user': user.id,
                        'log': message,
                    }
                    if record.picking_id:
                        log_vals['pick'] = record.picking_id.id
                    elif record.batch_id:
                        log_vals['batch_pick'] = record.batch_id.id
                    self.env['wmds.log'].sudo().create(log_vals)

        for record in self:
            changes = []
            if 'location_id' in vals:
                new_loc_id = vals.get('location_id')
                if record.location_id.id != new_loc_id:
                    new_loc = self.env['stock.location'].sudo().browse(new_loc_id)
                    changes.append(f"Origen: {record.location_id.display_name} -> {new_loc.display_name}")
                    if record.wmds_picked_qty > 0:
                        record.sudo().write({'wmds_picked_qty': 0.0})
                        if not suppress_logs:
                            msg_reset = f"Cantidad recolectada reseteada a 0 para {record.product_id.display_name} por cambio de ubicación de origen."
                            self.env['wmds.log'].sudo().create({
                                'pick': record.picking_id.id,
                                'log': msg_reset,
                                'user': self.env.user.id,
                            })

            if 'location_dest_id' in vals:
                new_loc = self.env['stock.location'].sudo().browse(vals['location_dest_id'])
                changes.append(f"Destino: {record.location_dest_id.display_name} -> {new_loc.display_name}")

            if not suppress_logs and changes and record.picking_id and not self.env.context.get('wmds_location_change_by_scan'):
                msg = f"Línea de movimiento modificada ({record.product_id.name}): " + ", ".join(changes)
                self.env['wmds.log'].sudo().create({
                    'pick': record.picking_id.id,
                    'log': msg,
                    'user': self.env.user.id,
                })

        return super(StockMoveLine, self.with_context(wmds_move_line_write_in_progress=True)).write(vals)

class StockMove(models.Model):
    _inherit = 'stock.move'

    wmds_picked_qty = fields.Float(string='Recolectado (WMDS)', compute='_compute_wmds_picked_qty')

    @api.depends('move_line_ids.wmds_picked_qty')
    def _compute_wmds_picked_qty(self):
        for move in self:
            move.wmds_picked_qty = sum(move.move_line_ids.mapped('wmds_picked_qty'))
