from odoo import models, fields, api
import json
import qrcode
import base64
from io import BytesIO

class BinCartStorage(models.Model):
    _name = "bin.storage"
    _description = "Bin Storage"

    name = fields.Char(string="Nombre de BIN", required=True)
    ei = fields.One2many("sale.order.ei", "bin_id", string="Paquetes en BIN")
    moves = fields.One2many("stock.move", "bin_id", string="Productos de full en BIN")
    state = fields.Selection([
        ('available', 'Disponible'),
        ('blocked', 'Bloqueado')
    ], string="Estado", compute="_compute_state", store=True)

    @api.depends('ei', 'moves')
    def _compute_state(self):
        for record in self:
            if record.ei or record.moves:
                record.state = 'blocked'
            else:
                record.state = 'available'

    qr_code_structure = fields.Char(
        string='QR Code',
        compute='_compute_qr_code',
        store=False
    )

    qr_image = fields.Image(
        string='QR Code Image',
        compute='_compute_qr_code',
        store=False
    )

    @api.depends('name')
    def _compute_qr_code(self):
        for record in self:
            record.qr_code_structure = json.dumps({
                "name": record.name
            })

            if not record.name:
                record.qr_image = False
                continue

            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(record.qr_code_structure)
            qr.make(fit=True)

            img = qr.make_image(fill_color="black", back_color="white")

            buffer = BytesIO()
            img.save(buffer, format='PNG')
            qr_base64 = base64.b64encode(buffer.getvalue())

            record.qr_image = qr_base64

class DockStorage(models.Model):
    _name = "dock.storage"
    _description = "Dock Storage"

    name = fields.Char(string="Nombre de DOCK", required=True)
    ei = fields.One2many("sale.order.ei", "dock_id", string="Paquetes en DOCK")
    moves = fields.One2many("stock.move", "dock_id", string="Productos de full en DOCK")
    state = fields.Selection([
        ('available', 'Disponible'),
        ('blocked', 'Bloqueado')
    ], string="Estado", compute="_compute_state", store=True)

    @api.depends('ei', 'moves')
    def _compute_state(self):
        for record in self:
            # Docks are always available for more items
            record.state = 'available'

    qr_code_structure = fields.Char(
        string='QR Code',
        compute='_compute_qr_code',
        store=False
    )

    qr_image = fields.Image(
        string='QR Code Image',
        compute='_compute_qr_code',
        store=False
    )

    @api.depends('name')
    def _compute_qr_code(self):
        for record in self:
            record.qr_code_structure = json.dumps({
                "name": record.name
            })

            if not record.name:
                record.qr_image = False
                continue

            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(record.qr_code_structure)
            qr.make(fit=True)

            img = qr.make_image(fill_color="black", back_color="white")

            buffer = BytesIO()
            img.save(buffer, format='PNG')
            qr_base64 = base64.b64encode(buffer.getvalue())

            record.qr_image = qr_base64    

class BinStockMove(models.Model):
    _inherit = "stock.move"

    on_bin = fields.Boolean(string="En bin", default=False)
    bin_id = fields.Many2one("bin.storage", string="BIN Actual", tracking=True)
    on_dock = fields.Boolean(string="Está en DOCK", default=False, tracking=True)
    dock_id = fields.Many2one("dock.storage", string="DOCK Actual", tracking=True)
    dispatched = fields.Boolean(string="Entregado a paquetería", default=False)
    qty_dispatched = fields.Float(string="Cantidad Despachada", default=0.0, tracking=True)
    qty_remaining = fields.Float(string="Cantidad Pendiente", compute="_compute_qty_remaining", store=True)
    wmds_state = fields.Selection([
        ('in_stock', 'En Almacén'),
        ('on_bin', 'En BIN'),
        ('on_dock', 'En DOCK'),
        ('partially_dispatched', 'Despacho Parcial'),
        ('dispatched', 'Despachado')
    ], string="Estado Logístico WMDS", compute="_compute_wmds_state", store=True)

    @api.depends('on_bin', 'on_dock', 'dispatched', 'qty_dispatched', 'quantity')
    def _compute_wmds_state(self):
        for move in self:
            if move.dispatched:
                move.wmds_state = 'dispatched'
            elif move.qty_dispatched > 0 and move.qty_dispatched < move.quantity:
                move.wmds_state = 'partially_dispatched'
            elif move.on_dock:
                move.wmds_state = 'on_dock'
            elif move.on_bin:
                move.wmds_state = 'on_bin'
            else:
                move.wmds_state = 'in_stock'

    @api.depends('quantity', 'qty_dispatched')
    def _compute_qty_remaining(self):
        for move in self:
            move.qty_remaining = move.quantity - move.qty_dispatched

class SaleOrderEIWMDS(models.Model):
    _inherit = "sale.order.ei"

    on_bin = fields.Boolean(string="En bin", default=False)
    bin_id = fields.Many2one("bin.storage", string="BIN Actual", tracking=True)
    on_dock = fields.Boolean(string="Está en DOCK", default=False, tracking=True)
    dock_id = fields.Many2one("dock.storage", string="DOCK Actual", tracking=True)
    dispatched = fields.Boolean(string="Entregado a paquetería", default=False)

class LogLine(models.Model):
    _name = "log.line"
    _description = "Log Line"

    operator_id = fields.Many2one("res.users", string="Operador")
    qty = fields.Float(string="Cantidad Contada")
    counted_at = fields.Datetime(string="Fecha de Conteo", default=fields.Datetime.now)
    message = fields.Char(string='Mensaje')
    bin_log_id = fields.Many2one("bin.log", string="BIN Log")
    dock_log_id = fields.Many2one("dock.log", string="Dock Log")

class BinLog(models.Model):
    _name = "bin.log"
    _description = "Bin Log"

    bin_id = fields.Many2one("bin.storage", string="BIN")
    line_ids = fields.One2many("log.line", "bin_log_id")

class DockLog(models.Model):
    _name = "dock.log"
    _description = "Dock Log"

    bin_id = fields.Many2one("bin.storage", string="BIN")
    dock_id = fields.Many2one("dock.storage", string="DOCK")
    line_ids = fields.One2many("log.line", "dock_log_id")
