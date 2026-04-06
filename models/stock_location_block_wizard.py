# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError

class StockLocationBlockWizard(models.TransientModel):
    _name = 'stock.location.block.wizard'
    _description = 'Wizard para bloquear ubicación'

    location_id = fields.Many2one('stock.location', string='Ubicación', required=True)
    block_reason = fields.Char(string='Motivo de Bloqueo', required=True)

    def action_block(self):
        self.ensure_one()
        
        # Check for active reservations
        reservations = self.env['stock.move.line'].sudo().search([
            ('location_id', '=', self.location_id.id),
            ('state', 'not in', ['done', 'cancel']),
            ('quantity', '>', 0)
        ], limit=1)
        
        if reservations:
            raise UserError(f"No se puede bloquear la ubicación {self.location_id.complete_name}, tiene una reserva en el movimiento {reservations.picking_id.name or reservations.move_id.reference}. Termine el traslado o anule la reserva.")

        blocked_parent = self.env.ref('wmds.location_blocked').sudo()
        
        # Save original parent and block the location
        vals = {
            'location_id': blocked_parent.id,
            'block_reason': self.block_reason
        }
        
        if not self.location_id.original_parent_id:
            vals['original_parent_id'] = self.location_id.location_id.id
            
        self.location_id.sudo().write(vals)
        return {'type': 'ir.actions.act_window_close'}
