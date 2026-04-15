from odoo import models, fields, api
import json
import qrcode
import base64
from io import BytesIO
import uuid
import random
import logging

_logger = logging.getLogger(__name__)

class ResUsers(models.Model):
    _inherit = 'res.users'

    packer_uuid = fields.Char(
        string='Packer UUID',
        readonly=True,
        copy=False,
        index=True,
        compute='_compute_packer_uuid',
        store=True
    )

    packer_barcode_image = fields.Image(
        string='Packer Barcode Image',
        compute='_compute_packer_barcode_image',
        store=False
    )

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

    def _generate_packer_uuid(self):
        while True:
            new_uuid = "".join([str(random.randint(0, 9)) for _ in range(8)])
            self.env.cr.execute("SELECT id FROM res_users WHERE packer_uuid = %s", (new_uuid,))
            if not self.env.cr.fetchone():
                return new_uuid

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('packer_uuid'):
                vals['packer_uuid'] = self._generate_packer_uuid()
        return super().create(vals_list)

    @api.depends('login')
    def _compute_packer_uuid(self):
        for user in self:
            is_valid = user.packer_uuid and len(str(user.packer_uuid)) == 8 and str(user.packer_uuid).isdigit()
            if not is_valid:
                    user.packer_uuid = self._generate_packer_uuid()
    @api.depends('packer_uuid')
    def _compute_packer_barcode_image(self):
        for user in self:
            if not user.packer_uuid:
                user.packer_barcode_image = False
                continue

            try:
                # Use python-barcode with SVGWriter (generates plain text SVG, no external GUI libs needed)
                import barcode
                from barcode.writer import SVGWriter

                # We use code128 as it's the standard for this uuid
                CODE128 = barcode.get_barcode_class('code128')
                # SVGWriter creates a pure text SVG
                writer = SVGWriter()
                # Remove the text under the barcode as we display it manually in Vue
                writer.set_options({'write_text': False, 'module_height': 15.0})

                bc = CODE128(str(user.packer_uuid), writer=writer)
                buffer = BytesIO()
                bc.write(buffer)

                # Convert to base64 string
                svg_data = base64.b64encode(buffer.getvalue()).decode('utf-8')
                user.packer_barcode_image = svg_data
            except Exception as e:
                _logger.error(f"Error generating manual SVG barcode: {str(e)}")
                user.packer_barcode_image = False

    @api.depends('login')
    def _compute_qr_code(self):
        for user in self:
            if not user.login:
                user.qr_code_structure = False
                user.qr_image = False
                continue

            user.qr_code_structure = json.dumps({
                "email": user.login
            })

            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(user.qr_code_structure)
            qr.make(fit=True)

            img = qr.make_image(fill_color="black", back_color="white")

            buffer = BytesIO()
            img.save(buffer, format='PNG')
            user.qr_image = base64.b64encode(buffer.getvalue()).decode('utf-8')