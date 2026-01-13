from odoo import models, fields, api
import json
import qrcode
import base64
from io import BytesIO


class ResUsers(models.Model):
    _inherit = 'res.users'

    qr_code_structure = fields.Char(
        'QR Code',
        compute='_compute_qr_code',
        store=True
    )

    qr_image = fields.Image(
        'QR Code Image',
        compute='_compute_qr_code',
        store=True
    )

    @api.depends('login')
    def _compute_qr_code(self):
        for user in self:
            # JSON structure
            user.qr_code_structure = json.dumps({
                "email": user.login
            })

            if not user.login:
                user.qr_image = False
                continue

            # Generate QR
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(user.login)
            qr.make(fit=True)

            img = qr.make_image(fill_color="black", back_color="white")

            # Convert PIL image to base64
            buffer = BytesIO()
            img.save(buffer, format='PNG')
            qr_base64 = base64.b64encode(buffer.getvalue())

            user.qr_image = qr_base64
