# -*- coding: utf-8 -*-
"""Página de Ajustes de WMDs: interruptores de complementos."""
from unittest.mock import patch

from odoo.tests import tagged
from odoo.tests.common import TransactionCase

ADDON_FIELDS = {
    'module_wmds_cancel': 'wmds_cancel',
}


@tagged('post_install', '-at_install')
class TestWmdsSettings(TransactionCase):

    def test_settings_view_shows_addon_toggles(self):
        arch = self.env['res.config.settings'].get_views([(False, 'form')])['views']['form']['arch']
        self.assertIn('name="wmds"', arch)
        for field in ADDON_FIELDS:
            self.assertIn(f'name="{field}"', arch)

    def test_toggle_reflects_module_state(self):
        settings = self.env['res.config.settings'].create({})
        for field, module_name in ADDON_FIELDS.items():
            module = self.env['ir.module.module']._get(module_name)
            self.assertTrue(module, f"{module_name} debe estar en el addons_path")
            installed = module.state in ('installed', 'to install', 'to upgrade')
            self.assertEqual(settings[field], installed)

    def test_save_without_changes_does_not_touch_modules(self):
        IrModule = type(self.env['ir.module.module'])
        with patch.object(IrModule, 'button_immediate_install', return_value=False) as install, \
                patch.object(IrModule, 'button_immediate_uninstall', return_value=False) as uninstall:
            self.env['res.config.settings'].create({}).execute()
        install.assert_not_called()
        uninstall.assert_not_called()

    def test_toggle_on_installs_addon(self):
        field, module_name = next(iter(ADDON_FIELDS.items()))
        module = self.env['ir.module.module']._get(module_name)
        if module.state == 'installed':
            self.skipTest(f"{module_name} ya está instalado")
        IrModule = type(self.env['ir.module.module'])
        with patch.object(IrModule, 'button_immediate_install', return_value=False) as install:
            self.env['res.config.settings'].create({field: True}).execute()
        install.assert_called_once()
