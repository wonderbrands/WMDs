# -*- coding: utf-8 -*-
"""Endpoint /wmds/v2/features: qué complementos están instalados."""
from unittest.mock import MagicMock, patch

from odoo.tests import tagged
from odoo.tests.common import TransactionCase

import odoo.addons.wmds.controllers.features as features_ctrl

# complemento -> clave que agrega a _wmds_features()
ADDON_FEATURES = {
    'wmds_cancel': 'cancel',
}


@tagged('post_install', '-at_install')
class TestWmdsFeatures(TransactionCase):

    def test_features_match_installed_addons(self):
        features = self.env['wmds.features']._wmds_features()
        for module_name, key in ADDON_FEATURES.items():
            installed = self.env['ir.module.module']._get(module_name).state == 'installed'
            self.assertEqual(features.get(key, False), installed, module_name)

    def test_endpoint_returns_features(self):
        with patch.object(features_ctrl, 'request', MagicMock(env=self.env)):
            res = features_ctrl.WmdsFeaturesController().get_features()
        self.assertEqual(res, {'features': self.env['wmds.features']._wmds_features()})
