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
        _logger.debug("===============================")
        _logger.debug("Validando picking %s", self.name)
        _logger.debug(f"documento origen: {self.origin}")
        _logger.debug(f"tipo de operacion: {self.picking_type_id.name}")
        _logger.debug(f"origen: {self.location_id.complete_name}")
        _logger.debug(f"destino: {self.location_dest_id.complete_name}")
        if self.picking_type_id.name == 'Storage':
            po = self.env['purchase.order'].search([('name', '=', self.origin)])
            if po:
                if not po.check_commertial:
                    destiny = self.location_dest_id.complete_name
                    if 'Stock/Almacenaje' in destiny:
                        destiny = destiny.replace('Stock/Almacenaje', 'Cuarentena')
                    elif 'Stock' in destiny:
                        destiny = destiny.replace('Stock', 'Cuarentena')
                    else:
                        raise UserError('No se pudo encontrar el destino de la recepcion')
                    self.location_dest_id = self.env['stock.location'].search([('complete_name', '=', destiny)], limit=1).id
            else:
                raise UserError('No se pudo encontrar la orden de compra asociada a la recepcion')                

            
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