# -*- coding: utf-8 -*-
from odoo import models, fields

class BlockReason(models.Model):
    _name = 'block.reason'
    _description = 'Motivos de Bloqueo de Ubicación'

    name = fields.Char('Motivo', required=True)
