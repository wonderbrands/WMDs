# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class ScheduledCycleCount(models.Model):
    _name = "scheduled.cycle.count"
    _description = "Conteo Cíclico Programado"

    name = fields.Char(string="Código", required=True, readonly=True, copy=False, default=lambda self: _('Nuevo'))
    notes = fields.Char(string="Referencia")
    state = fields.Selection([
        ("created", "Borrador"),
        ("in_progress", "En Progreso"),
        ("finalized", "Finalizado"),
        ("cancelled", "Cancelado")
    ], default='created', string="Estado")
    selected_location_ids = fields.One2many("cycle.count.selected.location", "cycle_count_id", string="Ubicaciones Planificadas")
    wave_ids = fields.One2many("cycle.count.wave", "cycle_count_id", string="Olas de Conteo")

    @api.model
    def create(self, vals):
        if vals.get('name', _('Nuevo')) == _('Nuevo'):
            vals['name'] = self.env['ir.sequence'].next_by_code('scheduled.cycle.count') or _('Nuevo')
        return super(ScheduledCycleCount, self).create(vals)

class CycleCountSelectedLocation(models.Model):
    _name = "cycle.count.selected.location"
    _description = "Ubicación Planificada"
    cycle_count_id = fields.Many2one("scheduled.cycle.count", ondelete="cascade")
    location_id = fields.Many2one("stock.location", string="Ubicación", required=True)

class CycleCountWave(models.Model):
    _name = "cycle.count.wave"
    _description = "Ola de Conteo Cíclico"
    name = fields.Char(string="Referencia de Ola", required=True)
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
    wave_id = fields.Many2one("cycle.count.wave", ondelete="cascade")
    product_id = fields.Many2one("product.product", string="Producto")
    qty = fields.Float(string="Cantidad")
    stock_location_id = fields.Many2one("stock.location", string="Ubicación")
    counted_by_id = fields.Many2one("res.users")
    counted_at = fields.Datetime(default=fields.Datetime.now)
    description = fields.Text()