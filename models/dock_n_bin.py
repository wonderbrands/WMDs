from odoo import models, fields, api
import json
import qrcode
import base64
from io import BytesIO

class BinStockMove(models.Model):
    _inherit = "stock.move"

    on_bin = fields.Boolean(string="En bin", default=False)
    bin_id = fields.Many2one("bin.storage", string="BIN Actual", tracking=True)
    on_dock = fields.Boolean(string="Está en DOCK", default=False, tracking=True)
    dock_id = fields.Many2one("dock.storage", string="DOCK Actual", tracking=True)
    dispatched = fields.Boolean(string="Entregado a paquetería", default=False)

class BinCartStorage(models.Model):
    _name = "bin.storage"

    name = fields.Char(string="Nombre de BIN", required=True)
    ei = fields.One2many("sale.order.ei", "bin_id", string="Paquetes en BIN")
    moves = fields.One2many("stock.move", "bin_id", string="Productos de full en BIN")

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

    name = fields.Char(string="Nombre de DOCK", required=True)
    ei = fields.One2many("sale.order.ei", "dock_id", string="Paquetes en DOCK")
    moves = fields.One2many("stock.move", "dock_id", string="Productos de full en DOCK")

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