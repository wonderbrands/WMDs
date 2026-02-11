# -*- coding: utf-8 -*-
from odoo import models, fields, api
from datetime import datetime
from odoo.exceptions import UserError
import logging
import requests

_logger = logging.getLogger(__name__)


class WMDSLog(models.Model):
    _name = 'wmds.log'
    _description = 'Log compartido WMDS'

    pick = fields.Many2one('stock.picking', 'Pick')
    purchase = fields.Many2one('purchase.order', 'Purchase Order')
    sale = fields.Many2one('sale.order', "Sale order")
    batch_pick = fields.Many2one('stock.picking.batch', 'Lote de picks')

    log = fields.Text('Log')
    date = fields.Datetime('Date', default=fields.Datetime.now) # Default automático
    user = fields.Many2one('res.users', 'User')

