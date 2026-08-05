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

    def test_remove_picking_from_batch_resets_reservations(self):
        """Test that removing a picking from a batch unlinks its move lines and resets wmds_picked_qty."""
        import odoo.addons.wmds.controllers.batch_pickings as bp

        # Create batch
        batch = self.env['stock.picking.batch'].create({
            'name': 'Test Batch 001',
        })

        # Create picking and move
        picking = self.env['stock.picking'].create({
            'picking_type_id': self.picking_type_rackeo.id,
            'location_id': self.loc_src.id,
            'location_dest_id': self.loc_normal.id,
            'batch_id': batch.id,
        })
        move = self.env['stock.move'].create({
            'name': 'Move Test Batch',
            'product_id': self.product_1.id,
            'product_uom_qty': 10.0,
            'product_uom': self.product_1.uom_id.id,
            'picking_id': picking.id,
            'location_id': self.loc_src.id,
            'location_dest_id': self.loc_normal.id,
            'quantity': 10.0,
        })
        picking.action_confirm()
        picking.action_assign()

        # Set wmds_picked_qty on the move line to simulate partial pick progress
        self.assertTrue(picking.move_line_ids)
        move_line = picking.move_line_ids[0]
        move_line.wmds_picked_qty = 4.0
        
        # Verify initial state
        self.assertEqual(picking.batch_id.id, batch.id)
        self.assertEqual(move.wmds_picked_qty, 4.0)

        # Call controller method to remove from batch
        controller = bp.BatchPickController()
        original_request = bp.request
        mock_request = MagicMock()
        mock_request.env = self.env
        mock_request.env.user = self.env.user
        bp.request = mock_request
        try:
            res = controller.remove_picking_from_batch(
                picking_id=picking.id,
                batch_id=batch.id,
                reason="Testing removal"
            )
            self.assertEqual(res.get('status'), 'ok')
        finally:
            bp.request = original_request

        # Verify final state
        self.assertFalse(picking.batch_id)
        self.assertFalse(picking.move_line_ids)
        self.assertEqual(move.wmds_picked_qty, 0.0)

    def test_return_picking_bypass_forbidden_locations(self):
        """Test that return pickings/moves bypass the forbidden locations check."""
        # 1. Create a forbidden destination location
        parent_loc = self.env['stock.location'].create({
            'name': 'Stock',
            'usage': 'view',
        })
        forbidden_loc = self.env['stock.location'].create({
            'name': 'Almacenaje',
            'location_id': parent_loc.id,
            'usage': 'internal',
        })
        self.assertEqual(forbidden_loc.complete_name, 'Stock/Almacenaje')

        # 2. Test that a normal (non-return) picking to a forbidden location fails
        picking_fail = self.env['stock.picking'].create({
            'picking_type_id': self.picking_type_rackeo.id,
            'location_id': self.loc_src.id,
            'location_dest_id': forbidden_loc.id,
        })
        move_fail = self.env['stock.move'].create({
            'name': 'Move Fail',
            'product_id': self.product_1.id,
            'product_uom_qty': 1.0,
            'product_uom': self.product_1.uom_id.id,
            'picking_id': picking_fail.id,
            'location_id': self.loc_src.id,
            'location_dest_id': forbidden_loc.id,
            'quantity': 1.0,
        })
        picking_fail.action_confirm()
        
        # This assign/validate should raise UserError because location is forbidden
        with self.assertRaises(UserError):
            picking_fail.button_validate()

        # 3. Test that a return picking/move to the same forbidden location succeeds
        orig_picking = self.env['stock.picking'].create({
            'picking_type_id': self.picking_type_rackeo.id,
            'location_id': self.loc_src.id,
            'location_dest_id': self.loc_normal.id,
        })
        orig_move = self.env['stock.move'].create({
            'name': 'Original Move',
            'product_id': self.product_1.id,
            'product_uom_qty': 1.0,
            'product_uom': self.product_1.uom_id.id,
            'picking_id': orig_picking.id,
            'location_id': self.loc_src.id,
            'location_dest_id': self.loc_normal.id,
            'quantity': 1.0,
        })
        orig_picking.action_confirm()
        orig_picking.button_validate()

        return_picking = self.env['stock.picking'].create({
            'picking_type_id': self.picking_type_rackeo.id,
            'location_id': self.loc_normal.id,
            'location_dest_id': forbidden_loc.id,
        })
        return_move = self.env['stock.move'].create({
            'name': 'Return Move',
            'product_id': self.product_1.id,
            'product_uom_qty': 1.0,
            'product_uom': self.product_1.uom_id.id,
            'picking_id': return_picking.id,
            'location_id': self.loc_normal.id,
            'location_dest_id': forbidden_loc.id,
            'origin_returned_move_id': orig_move.id,
            'quantity': 1.0,
        })
        return_picking.action_confirm()
        # This validate should succeed because it is a return and bypasses the check
        return_picking.button_validate()
        self.assertEqual(return_picking.state, 'done')

