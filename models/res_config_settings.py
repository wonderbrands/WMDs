# -*- coding: utf-8 -*-
"""Ajustes de WMDs: un interruptor por complemento.

Odoo instala el módulo `X` al guardar con `module_X` marcado y lo desinstala al
desmarcarlo (ver `res.config.settings.execute`). Si el módulo no está en el
addons_path, el interruptor no hace nada.
"""
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    module_wmds_cancel = fields.Boolean(
        string="Cancelaciones",
        help="Reubica a Guardería el stock de pedidos cancelados y retiene el OUT "
             "cuando la cancelación llega en pleno despacho.")
