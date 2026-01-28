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
        #the destiny will change if it is a storage operation
        if self.picking_type_id.name == 'Storage':
            #get the asociated po
            po = self.env['purchase.order'].search([('name', '=', self.origin)])
            if po:
                #does it have the validation of the commercial team?
                if not po.check_commertial:
                    #change the destiny, from stock to bloqueado
                    destiny = self.location_dest_id.complete_name
                    #check if it has stock/almacenaje
                    if 'Stock/Almacenaje' in destiny:
                        destiny = destiny.replace('Stock/Almacenaje', 'Cuarentena')
                    elif 'Stock' in destiny:
                        destiny = destiny.replace('Stock', 'Cuarentena')
                    else:
                        raise UserError('No se pudo encontrar el destino de la recepcion')
                    self.location_dest_id = self.env['stock.location'].search([('complete_name', '=', destiny)], limit=1).id
            else:
                raise UserError('No se pudo encontrar la orden de compra asociada a la recepcion')                

            
        return super(StockWMDS, self).button_validate()

################################################
# Herencia de PURCHASE
################################################
class PurchaseWMDS(models.Model):
    _inherit = 'purchase.order'

    wmds_log = fields.One2many('wmds.log', 'purchase', string='WMDS Log')
    
    check_commertial = fields.Boolean('Vo.Bo Comex', default=False)

    def write(self, vals):
        if 'check_commertial' in vals:
            is_comm = vals.get('check_commertial')
            log_msg = 'Vo.Bo de COMEX otorgado' if is_comm else 'COMEX ha retirado Vo.Bo'
            
            for record in self:
                if record.check_commertial != is_comm:
                    record.sudo().write({
                        'wmds_log': [(0, 0, {
                            'log': log_msg,
                            'user': self.env.user.id,
                            'date': fields.Datetime.now(),
                        })]
                    })
        
        return super(PurchaseWMDS, self).write(vals)
