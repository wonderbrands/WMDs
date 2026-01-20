# -*- coding: utf-8 -*-
from odoo import models, fields, api
from datetime import datetime
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class WMDSStockStatus(models.Model):
    _name = 'wmds.stock.status'
    _description = 'Estados WMDS'

    name = fields.Char('Name', required=True)
    value = fields.Char('Value', required=True)

class WMDSLog(models.Model):
    _name = 'wmds.log'
    _description = 'Log compartido WMDS'

    pick = fields.Many2one('stock.picking', 'Pick')
    purchase = fields.Many2one('purchase.order', 'Purchase Order')

    log = fields.Text('Log')
    date = fields.Datetime('Date', default=fields.Datetime.now) # Default automático
    user = fields.Many2one('res.users', 'User')

###################################################
# Herencia de STOCK PICKING
###################################################
class StockWMDS(models.Model):
    _inherit = 'stock.picking'

    operator = fields.Many2one('res.users', 'Operator')
    wmds_status = fields.Many2one('wmds.stock.status', 'WMDS Status')
    
    wmds_log = fields.One2many('wmds.log', 'pick', string='WMDS Log')

    @api.model
    def create(self, vals):
        res = super(StockWMDS, self).create(vals)
        if not res.operator:
            not_assigned = self.env['wmds.stock.status'].search([('value', '=', 'not_assigned')], limit=1)
            if not_assigned:
                res.wmds_status = not_assigned.id
        return res

    def button_validate(self):
        _logger.debug("===============================")
        _logger.debug("Validando picking %s", self.name)
        _logger.debug(f"documento origen: {self.origin}")
        _logger.debug(f"tipo de operacion: {self.picking_type_id.name}")
        _logger.debug(f"origen: {self.location_id.full_name}")
        _logger.debug(f"destino: {self.location_dest_id.full_name}")
        #the destiny will change if it is a storage operation
        if self.picking_type_id.name == 'Storage':
            #get the asociated po
            po = self.env['purchase.order'].search([('name', '=', self.origin)])
            if po:
                #does it have the validation of the commercial team?
                if not po.check_commertial:
                    #change the destiny, from stock to bloqueado
                    destiny = self.location_dest_id.full_name     
                    destiny = destiny.replace('Stock', 'Bloqueado')
                    self.location_dest_id = self.env['stock.location'].search([('name', '=', destiny)], limit=1).id
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

    @api.model
    def create(self, vals):
        log_message = ''
        is_commercial = vals.get('check_commertial', False)
        
        if is_commercial:
            log_message = 'Confirmado por comercial, entra directo a stock'
        else:
            log_message = 'Enviado a WMDS'

        vals['wmds_log'] = [
            (0, 0, {
                'log': log_message,
                'user': self.env.user.id,
                'date': fields.Datetime.now(),
            })
        ]
        res = super(PurchaseWMDS, self).create(vals)
        return res

    @api.onchange('check_commertial')
    def _onchange_check_commertial(self):
        if self.check_commertial:
            log_message = 'Confirmado por comercial, entra directo a stock'
        else:
            log_message = 'Enviado a WMDS'

        if self.wmds_log and self.wmds_log[-1].log == log_message:
            return

        new_log = (0, 0, {
            'log': log_message,
            'user': self.env.user.id, 
            'date': fields.Datetime.now(),
        })
        
        self.wmds_log = [new_log]