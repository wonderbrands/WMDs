# -*- coding: utf-8 -*-
"""Funcionalidades de complementos WMDs instaladas, para el front."""
from odoo import http
from odoo.http import request


class WmdsFeaturesController(http.Controller):

    @http.route('/wmds/v2/features', type='json', auth='user', methods=['POST'], csrf=True)
    def get_features(self, **kw):
        return {'features': request.env['wmds.features']._wmds_features()}
