# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase
from odoo.tests import tagged
from unittest.mock import patch, MagicMock

@tagged('post_install', '-at_install')
class TestWmdsCompactacionController(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        warehouse = cls.env['stock.warehouse'].search([], limit=1)
        cls.wh_stock = warehouse.lot_stock_id if warehouse else cls.env.ref('stock.stock_location_stock')

        # Create locations
        cls.loc_a = cls.env['stock.location'].create({
            'name': 'Compact-LocA',
            'location_id': cls.wh_stock.id,
            'usage': 'internal',
            'barcode': 'COMP-LOCA-BAR'
        })
        cls.loc_b = cls.env['stock.location'].create({
            'name': 'Compact-LocB',
            'location_id': cls.wh_stock.id,
            'usage': 'internal',
            'barcode': 'COMP-LOCB-BAR'
        })
        cls.loc_dest = cls.env['stock.location'].create({
            'name': 'Compact-LocDest',
            'location_id': cls.wh_stock.id,
            'usage': 'internal',
            'barcode': 'COMP-LOCDEST-BAR'
        })

        # Create product
        cls.product = cls.env['product.product'].create({
            'name': 'Compact Product',
            'type': 'consu', # using consumable or storable
            'default_code': 'COMP-PROD-SKU',
            'barcode': 'COMP-PROD-BAR'
        })

        # Set stock in loc_a
        cls.env['stock.quant'].create({
            'location_id': cls.loc_a.id,
            'product_id': cls.product.id,
            'quantity': 10.0
        })

    def test_compactacion_flow(self):
        """Test the full compaction flow through the controller."""
        from odoo.addons.wmds.controllers.compactacion import CompactacionController
        controller = CompactacionController()

        mock_request = MagicMock()
        mock_request.env = self.env
        mock_request.user = self.env.user

        with patch('odoo.addons.wmds.controllers.compactacion.request', mock_request):
            # 1. Create Picking
            res_create = controller.create_picking(operator_email=self.env.user.login)
            self.assertEqual(res_create.get('status'), 'ok')
            picking_id = res_create.get('picking_id')
            self.assertTrue(picking_id)

            # 2. Validate Origin Location (COMP-LOCA-BAR)
            res_origin = controller.validate_origin_location(location_barcode='COMP-LOCA-BAR', picking_id=picking_id)
            self.assertEqual(res_origin.get('status'), 'ok')
            self.assertEqual(res_origin.get('location_id'), self.loc_a.id)
            self.assertTrue(len(res_origin.get('products')) > 0)

            # 3. Add lines and reserve
            lines = [{'product_id': self.product.id, 'qty': 5.0}]
            res_add = controller.add_location_lines(picking_id=picking_id, location_src_id=self.loc_a.id, lines=lines)
            self.assertEqual(res_add.get('status'), 'ok')

            # 4. Validate Destination Location
            res_dest = controller.validate_destination_location(location_barcode='COMP-LOCDEST-BAR')
            self.assertEqual(res_dest.get('status'), 'ok')
            self.assertEqual(res_dest.get('location_id'), self.loc_dest.id)

            # 5. Validate picking
            res_val = controller.validate_picking(picking_id=picking_id, location_dest_id=self.loc_dest.id, operator_email=self.env.user.login)
            self.assertEqual(res_val.get('status'), 'ok')
