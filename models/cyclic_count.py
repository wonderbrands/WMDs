from odoo import models, fields, api, _

class ScheduledCycleCount(models.Model):
    _name = "scheduled.cycle.count"
    _description = "Conteo Cíclico Programado"
    _order = "id desc"

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
            last_rec = self.search([], order='id desc', limit=1)
            last_id = last_rec.id if last_rec else 0
            vals['name'] = "CC%s" % (str(last_id + 1).zfill(6))
        return super(ScheduledCycleCount, self).create(vals)

class CycleCountSelectedLocation(models.Model):
    _name = "cycle.count.selected.location"
    cycle_count_id = fields.Many2one("scheduled.cycle.count", ondelete="cascade")
    location_id = fields.Many2one("stock.location", string="Ubicación", required=True)
    quarantine_location_id = fields.Many2one("stock.location", string="Ubicación Cuarentena")

class CycleCountWave(models.Model):
    _name = "cycle.count.wave"
    _description = "Ola de Conteo Cíclico"

    name = fields.Char(string="Referencia de Ola", compute="_compute_name", store=True, default="/")
    cycle_count_id = fields.Many2one("scheduled.cycle.count", string="Ciclo Padre", ondelete="cascade")
    operator_id = fields.Many2one("res.users", string="Operador Responsable")
    line_ids = fields.One2many("cycle.count.line", "wave_id", string="Líneas de la Ola")
    state = fields.Selection([
        ("draft", "Borrador"),
        ("ongoing", "En Proceso"),
        ("done", "Completada"),
        ("cancelled", "Cancelada")
    ], default='draft', string="Estado de Ola")

    @api.depends('cycle_count_id', 'cycle_count_id.name')
    def _compute_name(self):
        for wave in self:
            if wave.cycle_count_id and wave.cycle_count_id.name != 'Nuevo':
                all_waves = wave.cycle_count_id.wave_ids.sorted('id')
                try:
                    index = list(all_waves.ids).index(wave.id) + 1
                except (ValueError, TypeError):
                    index = len(all_waves) or 1
                wave.name = "%s-WAVE%s" % (wave.cycle_count_id.name, str(index).zfill(4))
            else:
                wave.name = "WAVE-TEMP"

class CycleCountLine(models.Model):
    _name = "cycle.count.line"
    wave_id = fields.Many2one("cycle.count.wave", ondelete="cascade")
    product_id = fields.Many2one("product.product", string="Producto")
    qty = fields.Float(string="Cantidad")
    stock_location_id = fields.Many2one("stock.location", string="Ubicación")
    counted_by_id = fields.Many2one("res.users")
    counted_at = fields.Datetime(default=fields.Datetime.now)
    description = fields.Text()