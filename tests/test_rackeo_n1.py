# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase
from odoo.tests import tagged
from odoo.exceptions import UserError
import odoo.addons.wmds.controllers.barcode_controller as bc
from unittest.mock import MagicMock

@tagged('post_install', '-at_install')
class TestRackeoN1(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create products
        cls.product_1 = cls.env['product.product'].create({
            'name': 'Product SKU 1',
            'type': 'consu',
            'is_storable': True,
        })
        cls.product_2 = cls.env['product.product'].create({
            'name': 'Product SKU 2',
            'type': 'consu',
            'is_storable': True,
        })

        # Create locations
        warehouse = cls.env['stock.warehouse'].search([], limit=1)
        cls.loc_src = cls.env['stock.location'].create({
            'name': 'Source Location',
            'location_id': warehouse.lot_stock_id.id,
            'usage': 'internal',
        })

        cls.loc_normal = cls.env['stock.location'].create({
            'name': 'Posicion Normal',
            'location_id': warehouse.lot_stock_id.id,
            'usage': 'internal',
        })

        cls.loc_n1 = cls.env['stock.location'].create({
            'name': 'S-P01-F2-N1',
            'location_id': warehouse.lot_stock_id.id,
            'usage': 'internal',
        })

        # Create Rackeo picking type
        cls.picking_type_rackeo = cls.env['stock.picking.type'].create({
            'name': 'Rackeo',
            'code': 'internal',
            'sequence_code': 'RACK_TEST_N1',
            'warehouse_id': warehouse.id,
        })

    def test_rackeo_normal_location(self):
        """Test rackeo to normal destination location (must be empty)."""
        # Create picking and move
        picking = self.env['stock.picking'].create({
            'picking_type_id': self.picking_type_rackeo.id,
            'location_id': self.loc_src.id,
            'location_dest_id': self.loc_normal.id,
        })
        move = self.env['stock.move'].create({
            'name': 'Move 1',
            'product_id': self.product_1.id,
            'product_uom_qty': 1.0,
            'product_uom': self.product_1.uom_id.id,
            'picking_id': picking.id,
            'location_id': self.loc_src.id,
            'location_dest_id': self.loc_normal.id,
            'quantity': 1.0,
        })
        picking.action_confirm()
        picking.action_assign()
        
        # Scenario 1: Destination location is empty -> validate succeeds
        picking.button_validate()
        self.assertEqual(picking.state, 'done')

    def test_rackeo_normal_location_not_empty(self):
        """Test rackeo to normal destination location fails if not empty."""
        # Create quant in normal destination location
        self.env['stock.quant'].create({
            'product_id': self.product_2.id,
            'location_id': self.loc_normal.id,
            'quantity': 5.0,
            'company_id': self.env.company.id,
        })

        picking = self.env['stock.picking'].create({
            'picking_type_id': self.picking_type_rackeo.id,
            'location_id': self.loc_src.id,
            'location_dest_id': self.loc_normal.id,
        })
        move = self.env['stock.move'].create({
            'name': 'Move 2',
            'product_id': self.product_1.id,
            'product_uom_qty': 1.0,
            'product_uom': self.product_1.uom_id.id,
            'picking_id': picking.id,
            'location_id': self.loc_src.id,
            'location_dest_id': self.loc_normal.id,
            'quantity': 1.0,
        })
        picking.action_confirm()
        picking.action_assign()

        # Validate should fail since destination has product 2 and it's normal location
        with self.assertRaises(UserError) as err:
            picking.button_validate()
        self.assertIn("No se puede rackear en la ubicación", err.exception.args[0])

        # Test controller barcode scan empty check on normal location
        controller = bc.BarcodeController()
        move_line = move.move_line_ids[0]
        # Scanned normal location barcode or name
        self.loc_normal.barcode = 'LOCNORMAL'
        
        original_request = bc.request
        mock_request = MagicMock()
        mock_request.env = self.env
        bc.request = mock_request
        try:
            res = controller.process_dest_location_scan(
                line_id=str(move_line.id),
                barcode='LOCNORMAL',
                operator_email='test@test.com',
                check_empty=True
            )
            self.assertEqual(res.get('status'), 'error')
            self.assertIn("ya contiene productos", res.get('message'))
        finally:
            bc.request = original_request

    def test_rackeo_n1_location_empty(self):
        """Test rackeo to N1 location when empty."""
        picking = self.env['stock.picking'].create({
            'picking_type_id': self.picking_type_rackeo.id,
            'location_id': self.loc_src.id,
            'location_dest_id': self.loc_n1.id,
        })
        move = self.env['stock.move'].create({
            'name': 'Move 3',
            'product_id': self.product_1.id,
            'product_uom_qty': 1.0,
            'product_uom': self.product_1.uom_id.id,
            'picking_id': picking.id,
            'location_id': self.loc_src.id,
            'location_dest_id': self.loc_n1.id,
            'quantity': 1.0,
        })
        picking.action_confirm()
        picking.action_assign()

        # Validate empty N1 location -> succeeds
        picking.button_validate()
        self.assertEqual(picking.state, 'done')

    def test_rackeo_n1_location_same_sku(self):
        """Test rackeo to N1 location containing the same SKU succeeds."""
        # Create quant of product_1 in N1 location
        self.env['stock.quant'].create({
            'product_id': self.product_1.id,
            'location_id': self.loc_n1.id,
            'quantity': 2.0,
            'company_id': self.env.company.id,
        })

        picking = self.env['stock.picking'].create({
            'picking_type_id': self.picking_type_rackeo.id,
            'location_id': self.loc_src.id,
            'location_dest_id': self.loc_n1.id,
        })
        move = self.env['stock.move'].create({
            'name': 'Move 4',
            'product_id': self.product_1.id,
            'product_uom_qty': 1.0,
            'product_uom': self.product_1.uom_id.id,
            'picking_id': picking.id,
            'location_id': self.loc_src.id,
            'location_dest_id': self.loc_n1.id,
            'quantity': 1.0,
        })
        picking.action_confirm()
        picking.action_assign()

        # Validate same SKU in N1 location -> succeeds
        picking.button_validate()
        self.assertEqual(picking.state, 'done')

        # Test controller same SKU scan
        controller = bc.BarcodeController()
        # Recreate similar scenario (move with product_1)
        picking2 = self.env['stock.picking'].create({
            'picking_type_id': self.picking_type_rackeo.id,
            'location_id': self.loc_src.id,
            'location_dest_id': self.loc_n1.id,
        })
        move2 = self.env['stock.move'].create({
            'name': 'Move 5',
            'product_id': self.product_1.id,
            'product_uom_qty': 1.0,
            'product_uom': self.product_1.uom_id.id,
            'picking_id': picking2.id,
            'location_id': self.loc_src.id,
            'location_dest_id': self.loc_n1.id,
            'quantity': 1.0,
        })
        picking2.action_confirm()
        picking2.action_assign()
        move_line2 = move2.move_line_ids[0]
        self.loc_n1.barcode = 'LOCN1'
        
        original_request = bc.request
        mock_request = MagicMock()
        mock_request.env = self.env
        bc.request = mock_request
        try:
            res = controller.process_dest_location_scan(
                line_id=str(move_line2.id),
                barcode='LOCN1',
                operator_email='test@test.com',
                check_empty=True
            )
            self.assertEqual(res.get('status'), 'ok')
        finally:
            bc.request = original_request

    def test_rackeo_n1_location_different_sku(self):
        """Test rackeo to N1 location containing a different SKU fails."""
        # Create quant of product_2 in N1 location
        self.env['stock.quant'].create({
            'product_id': self.product_2.id,
            'location_id': self.loc_n1.id,
            'quantity': 2.0,
            'company_id': self.env.company.id,
        })

        picking = self.env['stock.picking'].create({
            'picking_type_id': self.picking_type_rackeo.id,
            'location_id': self.loc_src.id,
            'location_dest_id': self.loc_n1.id,
        })
        move = self.env['stock.move'].create({
            'name': 'Move 6',
            'product_id': self.product_1.id,
            'product_uom_qty': 1.0,
            'product_uom': self.product_1.uom_id.id,
            'picking_id': picking.id,
            'location_id': self.loc_src.id,
            'location_dest_id': self.loc_n1.id,
            'quantity': 1.0,
        })
        picking.action_confirm()
        picking.action_assign()

        # Validate different SKU in N1 location -> fails
        with self.assertRaises(UserError) as err:
            picking.button_validate()
        self.assertEqual("El SKU a rackear debe ser el mismo que ya contiene la ubicación.", err.exception.args[0])

        # Test controller different SKU scan
        controller = bc.BarcodeController()
        move_line = move.move_line_ids[0]
        self.loc_n1.barcode = 'LOCN1'
        
        original_request = bc.request
        mock_request = MagicMock()
        mock_request.env = self.env
        bc.request = mock_request
        try:
            res = controller.process_dest_location_scan(
                line_id=str(move_line.id),
                barcode='LOCN1',
                operator_email='test@test.com',
                check_empty=True
            )
            self.assertEqual(res.get('status'), 'error')
            self.assertEqual("El SKU a rackear debe ser el mismo que ya contiene la ubicación.", res.get('message'))
        finally:
            bc.request = original_request
