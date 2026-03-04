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
            if attachment.res_model == 'sale.order.attachment':
                self._hook_attachment_so_custom(attachment)
        return attachments

    def _hook_attachment_so_custom(self, attachment):
        so_attach_record = self.env['sale.order.attachment'].sudo().browse(attachment.res_id)
        
        if so_attach_record and so_attach_record.so_id:
            so = so_attach_record.so_id
            mimetype = attachment.mimetype
            es_valido = False
            tipo_str = "Formato Inválido"

            if mimetype == 'application/pdf':
                tipo_str = "PDF"
                es_valido = True
            elif mimetype == 'text/plain' or (attachment.name and ('.zpl' in attachment.name.lower())):
                tipo_str = "TXT/ZPL"
                es_valido = True

            msg = f"Se ha adjuntado un archivo de tipo {tipo_str} en la sección de anexos"
            
            if not es_valido:
                msg += f" (Archivo: {attachment.name} no reconocido como formato de guía)"

            self.env['wmds.log'].sudo().create({
                'sale': so.id,
                'log': msg,
                'user': self.env.user.id,
                'date': fields.Datetime.now(),
            })