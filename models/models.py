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
                    destiny = destiny.replace('Stock', 'Bloqueado')
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

    @api.model
    def create(self, vals):
        if 'check_commertial' in vals:
            is_comm = vals.get('check_commertial')
            log_msg = 'Confirmado por comercial, entra directo a stock' if is_comm else 'No confirmado por comercial, entra a ubicación espejo "Bloqueado"'
            
            log_entry = (0, 0, {
                'log': log_msg,
                'user': self.env.user.id,
                'date': fields.Datetime.now(),
            })
            vals['wmds_log'] = [log_entry]
            
        return super(PurchaseWMDS, self.sudo()).create(vals)

    def write(self, vals):
        if 'check_commertial' in vals:
            is_comm = vals.get('check_commertial')
            log_msg = 'Confirmado por comercial, entra directo a stock' if is_comm else 'No confirmado por comercial, entra a ubicación espejo "Bloqueado"'
            
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