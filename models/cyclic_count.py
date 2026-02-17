# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

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
    wave_ids = fields.One2many("cycle.count.wave", "cycle_count_id", string="Olas de Conteo")


class CycleCountWave(models.Model):
    _name = "cycle.count.wave"
    _description = "Ola de Conteo Cíclico"

    name = fields.Char(string="Referencia de Ola", required=True, default=lambda self: _('Nueva Ola'))
    cycle_count_id = fields.Many2one("scheduled.cycle.count", string="Ciclo Padre", ondelete="cascade")
    operator_id = fields.Many2one("res.users", string="Operador Responsable")
    line_ids = fields.One2many("cycle.count.line", "wave_id", string="Líneas de la Ola")
    
    state = fields.Selection([
        ("draft", "Borrador"),
        ("ongoing", "En Proceso"),
        ("done", "Completada")
    ], default='draft', string="Estado de Ola")


class CycleCountLine(models.Model):
    _name = "cycle.count.line"
    _description = "Línea de Conteo Cíclico"

    wave_id = fields.Many2one("cycle.count.wave", string="Ola de Conteo", ondelete="cascade")
    product_id = fields.Many2one("product.product", string="Producto")
    qty = fields.Float(string="Cantidad Contada")
    stock_location_id = fields.Many2one("stock.location", string="Ubicación")
    counted_by_id = fields.Many2one("res.users", string="Contado por")
    counted_at = fields.Datetime(string="Fecha de Conteo", default=fields.Datetime.now)
    description = fields.Text(string="Notas")