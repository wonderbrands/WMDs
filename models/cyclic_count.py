# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import re

class ScheduledCycleCount(models.Model):
    _name = "scheduled.cycle.count"
    _description = "Conteo Cíclico Programado"

    name = fields.Char(string="Referencia", required=True, default=lambda self: _('Nuevo'))
    state = fields.Selection([
        ("created", "Borrador"),
        ("in_progress", "En Progreso"),
        ("finalized", "Finalizado"),
        ("cancelled", "Cancelado")
    ], default='created', string="Estado")

    selection_criteria = fields.Json(string="Criterios de Selección")
    
    operator_id = fields.Many2one("res.users", string="Operador")
    line_ids = fields.One2many("cycle.count.line", "cycle_count_id", string="Líneas de Conteo")


class CycleCountLine(models.Model):
    _name = "cycle.count.line"
    _description = "Línea de Conteo Cíclico"

    product_id = fields.Many2one("product.product", string="Producto")
    qty = fields.Float(string="Cantidad Contada")
    stock_location_id = fields.Many2one("stock.location", string="Ubicación")
    counted_by_id = fields.Many2one("res.users", string="Contado por")
    counted_at = fields.Datetime(string="Fecha de Conteo", default=fields.Datetime.now)
    description = fields.Text(string="Notas")

    cycle_count_id = fields.Many2one("scheduled.cycle.count", string="Ciclo de Conteo")