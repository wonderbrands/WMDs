# -*- coding: utf-8 -*-
from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)

class SOWMDS(models.Model):
    _inherit = 'sale.order'

    wmds_log = fields.One2many('wmds.log', 'sale', string='WMDS Log')

    @api.model
    def create(self, vals):
        res = super(SOWMDS, self).create(vals)
        if vals.get('carrier_selection_relational'):
            carrier_name = res.carrier_selection_relational.name
            self.env['wmds.log'].sudo().create({
                'sale': res.id,
                'log': f"Se ha asignado el carrier {carrier_name} a la orden (Creación)",
                'user': self.env.user.id,
                'date': fields.Datetime.now(),
            })
        return res

    def write(self, vals):

        if 'state' in vals:
            new_state = vals['state']
            
            state_map = {
                'draft': 'Cotización (Borrador)',
                'sent': 'Cotización Enviada',
                'sale': 'Orden de Venta (Confirmado)',
                'done': 'Bloqueado / Realizado',
                'cancel': 'Cancelado'
            }
            
            msg_state = state_map.get(new_state, f"Estado cambiado a: {new_state}")

            for record in self:
                if record.state != new_state:
                    self.env['wmds.log'].sudo().create({
                        'sale': record.id,
                        'log': msg_state,
                        'user': self.env.user.id,
                        'date': fields.Datetime.now(),
                    })


        res = super(SOWMDS, self).write(vals)

        if 'carrier_selection_relational' in vals:
            for record in self:
                carrier = record.carrier_selection_relational
                if carrier:
                    msg = f"Se ha asignado el carrier {carrier.name} a la orden"
                else:
                    msg = "Se ha desasignado el carrier de la orden"

                self.env['wmds.log'].sudo().create({
                    'sale': record.id,
                    'log': msg,
                    'user': self.env.user.id,
                    'date': fields.Datetime.now(),
                })
        
        return res


class IrAttachment(models.Model):
    _inherit = 'ir.attachment'

    @api.model_create_multi
    def create(self, vals_list):
        attachments = super(IrAttachment, self).create(vals_list)
        for attachment in attachments:
            if attachment.res_model == 'stock.picking':
                self._hook_attachment_pick(attachment)
        return attachments

    def _hook_attachment_pick(self, attachment):
        picking = self.env['stock.picking'].sudo().browse(attachment.res_id)
        
        is_pick = False
        if picking.picking_type_id.name == 'Pick':
            is_pick = True

        if is_pick:
            mimetype = attachment.mimetype
            es_valido = False
            tipo_str = "Formato Inválido"

            if mimetype == 'application/pdf':
                tipo_str = "PDF"
                es_valido = True
            elif mimetype == 'text/plain':
                tipo_str = "TXT/ZPL"
                es_valido = True

            so = picking.sale_id
            if not so and picking.origin:
                 so = self.env['sale.order'].sudo().search([("name", "=", picking.origin)], limit=1)

            if so:
                msg = f"Se ha adjuntado una guía de tipo {tipo_str} en el Pick {picking.name}"
                
                if not es_valido:
                    msg += f" (Archivo: {attachment.name} no valido como guía)"

                self.env['wmds.log'].sudo().create({
                    'sale': so.id,
                    'log': msg,
                    'user': self.env.user.id,
                    'date': fields.Datetime.now(),
                })