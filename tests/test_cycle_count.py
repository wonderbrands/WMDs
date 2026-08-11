# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase
from odoo.tests import tagged
from unittest.mock import patch, MagicMock

@tagged('post_install', '-at_install')
class TestWmdsCycleCountController(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Find WH/Stock or equivalent parent
        warehouse = cls.env['stock.warehouse'].search([], limit=1)
        cls.wh_stock = warehouse.lot_stock_id if warehouse else cls.env.ref('stock.stock_location_stock')

        cls.almacenaje = cls.env['stock.location'].create({
            'name': 'Almacenaje',
            'location_id': cls.wh_stock.id,
            'usage': 'internal'
        })

    def test_get_locations_by_range_success(self):
        """Test cycle count get_locations_by_range controller method."""
        loc_a = self.env['stock.location'].create({
            'name': 'A-P01-F1-N1',
            'location_id': self.almacenaje.id,
            'usage': 'internal'
        })
        loc_b = self.env['stock.location'].create({
            'name': 'B-P01-F1-N1',
            'location_id': self.almacenaje.id,
            'usage': 'internal'
        })

        from odoo.addons.wmds.controllers.cycle_count import CycleCount
        controller = CycleCount()

        mock_request = MagicMock()
        mock_request.env = self.env

        # Query aisle A to A
        with patch('odoo.addons.wmds.controllers.cycle_count.request', mock_request):
            res = controller.get_locations_by_range(
                aisle_from='A', aisle_to='A',
                position_from=1, position_to=99,
                level_from=1, level_to=5,
                front_from=1, front_to=2
            )

        self.assertTrue(res.get('ok'))
        loc_ids = [l['id'] for l in res.get('locations', [])]
        self.assertIn(loc_a.id, loc_ids)
        self.assertNotIn(loc_b.id, loc_ids)
