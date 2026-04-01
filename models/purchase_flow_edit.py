# -*- coding: utf-8 -*-
from odoo import models, fields, api
from datetime import datetime
from odoo.exceptions import UserError
import logging
import requests

_logger = logging.getLogger(__name__)


class StockWMDSPurchase(models.Model):
    _inherit = 'stock.picking'


    def button_validate(self):
        for picking in self:
            if picking.picking_type_id.name == 'Rackeos':
                po = self.env['purchase.order'].search(
                    [('name', '=', picking.origin)],
                    limit=1
                )

                if not po:
                    raise UserError('No se pudo encontrar la orden de compra asociada a la recepción')

                if not po.check_commertial:
                    for move in picking.move_ids:
                        for line in move.move_line_ids:
                            destiny = line.location_dest_id.complete_name

                            if 'Stock/Almacenaje' in destiny:
                                destiny = destiny.replace('Stock/Almacenaje', 'Cuarentena')
                            elif 'Stock' in destiny:
                                destiny = destiny.replace('Stock', 'Cuarentena')
                            else:
                                raise UserError('No se pudo encontrar el destino de la recepción')

                            location = self.env['stock.location'].search(
                                [('complete_name', '=', destiny)],
                                limit=1
                            )

                            if not location:
                                raise UserError('No se encontró la ubicación de cuarentena')

                            line.location_dest_id = location.id
                            
                        move.location_dest_id = location.id
                
                # Log the change
                self.env['wmds.log'].sudo().create({
                    'pick': picking.id,
                    'log': f"Destino de rackeo cambiado a cuarentena automáticamente por falta de Vo.Bo COMEX. Nueva ubicación: {location.complete_name}",
                    'user': self.env.user.id,
                })

        return super(StockWMDSPurchase, self).button_validate()

class PurchaseWMDS(models.Model):
    _inherit = 'purchase.order'

    wmds_log = fields.One2many('wmds.log', 'purchase', string='WMDS Log')
    check_commertial = fields.Boolean('Vo.Bo Comex', default=False)

    def write(self, vals):
        if 'state' in vals:
            new_state = vals['state']
            
            state_msg_map = {
                'draft': 'Compra restablecida a Borrador',
                'sent': 'Solicitud de Presupuesto Enviada',
                'to approve': 'Compra esperando aprobación',
                'purchase': 'Compra Confirmada',
                'done': 'Compra Bloqueada/Realizada',
                'cancel': 'Compra Cancelada'
            }
            
            msg_state = state_msg_map.get(new_state, f"Estado cambiado a: {new_state}")

            for record in self:
                if record.state != new_state:
                    self.env['wmds.log'].sudo().create({
                        'purchase': record.id,
                        'log': msg_state,
                        'user': self.env.user.id,
                        'date': fields.Datetime.now(),
                    })

        if 'check_commertial' in vals:
            is_comm = vals.get('check_commertial')
            log_msg = 'Vo.Bo de COMEX otorgado' if is_comm else 'COMEX ha retirado Vo.Bo'
            
            for record in self:
                if record.check_commertial != is_comm:
                    self.env['wmds.log'].sudo().create({
                        'purchase': record.id,
                        'log': log_msg,
                        'user': self.env.user.id,
                        'date': fields.Datetime.now(),
                    })
        
        return super(PurchaseWMDS, self).write(vals)