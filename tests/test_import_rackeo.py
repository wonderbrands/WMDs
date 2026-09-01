# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase
from odoo.tests import tagged
import odoo.addons.wmds.controllers.import_rackeo_controller as irc
from odoo.addons.wmds.scripts.rackeo_import_shell import parse_rackeo_text, process_rackeo_text
from unittest.mock import MagicMock
import base64
import openpyxl
import io

@tagged('post_install', '-at_install')
class TestImportRackeo(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        import time
        t_suffix = str(int(time.time()))[-6:]
        cls.sku_a = f"BIKE-TEST-A-{t_suffix}"
        cls.sku_b = f"BIKE-TEST-B-{t_suffix}"
        cls.barcode_a = f"7599{t_suffix}1"
        cls.barcode_b = f"7599{t_suffix}2"

        warehouse = cls.env['stock.warehouse'].search([], limit=1)

        # Products
        categ = cls.env['product.category'].search([], limit=1)
        tmpl_a = cls.env['product.template'].create({
            'name': 'Bicicleta Test A',
            'default_code': cls.sku_a,
            'barcode': cls.barcode_a,
            'categ_id': categ.id,
            'is_storable': True,
        })
        tmpl_b = cls.env['product.template'].create({
            'name': 'Bicicleta Test B',
            'default_code': cls.sku_b,
            'barcode': cls.barcode_b,
            'categ_id': categ.id,
            'is_storable': True,
        })
        cls.env.flush_all()

        cls.product_a_id = tmpl_a.product_variant_id.id
        cls.product_b_id = tmpl_b.product_variant_id.id

        # Locations
        loc_rec = cls.env['stock.location'].create({
            'name': f'Test Recepcion {t_suffix}',
            'location_id': warehouse.view_location_id.id,
            'usage': 'internal',
        })
        loc_stk = cls.env['stock.location'].create({
            'name': f'Test Stock {t_suffix}',
            'location_id': warehouse.view_location_id.id,
            'usage': 'internal',
        })
        loc_emp = cls.env['stock.location'].create({
            'name': f'LOC-EMP-{t_suffix}',
            'barcode': f'LOC-EMP-{t_suffix}',
            'location_id': loc_stk.id,
            'usage': 'internal',
        })
        loc_n1 = cls.env['stock.location'].create({
            'name': f'LOC-N1-{t_suffix}',
            'barcode': f'LOC-N1-{t_suffix}',
            'location_id': loc_stk.id,
            'usage': 'internal',
        })
        loc_occ = cls.env['stock.location'].create({
            'name': f'LOC-OCC-{t_suffix}',
            'barcode': f'LOC-OCC-{t_suffix}',
            'location_id': loc_stk.id,
            'usage': 'internal',
        })

        cls.loc_recepcion_id = loc_rec.id
        cls.loc_stock_id = loc_stk.id
        cls.loc_empty_dest_id = loc_emp.id
        cls.loc_n1_dest_id = loc_n1.id
        cls.loc_occupied_dest_id = loc_occ.id

        # Stock picking type STOR
        pt = cls.env['stock.picking.type'].search([('sequence_code', '=', 'STOR')], limit=1)
        if not pt:
            pt = cls.env['stock.picking.type'].create({
                'name': 'Storage Test',
                'sequence_code': 'STOR',
                'code': 'internal',
                'warehouse_id': warehouse.id,
                'default_location_src_id': loc_rec.id,
                'default_location_dest_id': loc_stk.id,
            })
        cls.pt_stor_id = pt.id

        # Purchase Order
        partner = cls.env['res.partner'].create({'name': f'Vendor Test {t_suffix}'})
        po_obj = cls.env['purchase.order'].create({
            'partner_id': partner.id,
            'name': f'PO-TEST-RACKEO-{t_suffix}',
        })
        cls.po_id = po_obj.id
        cls.env.flush_all()

    def test_01_parse_rackeo_text(self):
        """Test parsing of tab-separated and messy text input."""
        sample_tsv = f"""PO\tSKU\tUBICACIÓN\tPZS
PO-TEST-RACKEO\t{self.sku_a}\tLOC-EMPTY-01\t16
PO-TEST-RACKEO\t{self.sku_a}\tLOC-SHELF-N1\t16
"""
        rows = parse_rackeo_text(sample_tsv)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]['PO'], 'PO-TEST-RACKEO')
        self.assertEqual(rows[0]['SKU'], self.sku_a)
        self.assertEqual(rows[0]['UBICACION'], 'LOC-EMPTY-01')
        self.assertEqual(rows[0]['PZS'], 16.0)

    def test_02_process_rackeo_shell_script(self):
        """Test full execution of process_rackeo_text shell script."""
        product_a = self.env['product.product'].browse(self.product_a_id)
        po = self.env['purchase.order'].browse(self.po_id)
        pt_stor = self.env['stock.picking.type'].browse(self.pt_stor_id)
        loc_recepcion = self.env['stock.location'].browse(self.loc_recepcion_id)
        loc_stock = self.env['stock.location'].browse(self.loc_stock_id)
        loc_empty_dest = self.env['stock.location'].browse(self.loc_empty_dest_id)
        loc_n1_dest = self.env['stock.location'].browse(self.loc_n1_dest_id)

        # 1. Put stock in reception location
        rec_loc = pt_stor.default_location_src_id or loc_recepcion
        self.env['stock.quant']._update_available_quantity(product_a, rec_loc, 50.0)

        # 2. Create prior open STOR to test unreserving & adjustment
        open_stor = self.env['stock.picking'].create({
            'picking_type_id': pt_stor.id,
            'location_id': rec_loc.id,
            'location_dest_id': loc_stock.id,
            'origin': po.name,
        })
        move_prior = self.env['stock.move'].create({
            'name': 'Prior Move',
            'product_id': product_a.id,
            'product_uom_qty': 50.0,
            'product_uom': product_a.uom_id.id,
            'picking_id': open_stor.id,
            'location_id': rec_loc.id,
            'location_dest_id': loc_stock.id,
        })
        open_stor.action_confirm()
        open_stor.action_assign()
        self.assertEqual(open_stor.state, 'assigned')

        # 3. Execute process_rackeo_text
        text_input = f"""PO\tSKU\tUBICACIÓN\tPZS
{po.name}\t{self.sku_a}\t{loc_empty_dest.barcode}\t20
{po.name}\t{self.sku_a}\t{loc_n1_dest.barcode}\t10
"""
        results = process_rackeo_text(text_input, self.env)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['status'], 'ok')
        self.assertTrue(results[0].get('stor_name'))

        # 4. Verify new STOR is validated
        created_stor = self.env['stock.picking'].browse(results[0]['stor_id'])
        self.assertEqual(created_stor.state, 'done')
        self.assertEqual(len(created_stor.move_line_ids), 2)

        # 5. Verify destination quantities
        q_empty = self.env['stock.quant'].search([('location_id', '=', loc_empty_dest.id), ('product_id', '=', product_a.id)])
        self.assertEqual(sum(q_empty.mapped('quantity')), 20.0)

        q_n1 = self.env['stock.quant'].search([('location_id', '=', loc_n1_dest.id), ('product_id', '=', product_a.id)])
        self.assertEqual(sum(q_n1.mapped('quantity')), 10.0)

        # 6. Verify prior STOR was adjusted from 50 to 20 (50 - 30)
        self.assertEqual(move_prior.product_uom_qty, 20.0)

    def test_03_controller_validation_and_process(self):
        """Test controller validation and process routes."""
        product_a = self.env['product.product'].browse(self.product_a_id)
        product_b = self.env['product.product'].browse(self.product_b_id)
        po = self.env['purchase.order'].browse(self.po_id)
        pt_stor = self.env['stock.picking.type'].browse(self.pt_stor_id)
        loc_recepcion = self.env['stock.location'].browse(self.loc_recepcion_id)
        loc_empty_dest = self.env['stock.location'].browse(self.loc_empty_dest_id)
        loc_n1_dest = self.env['stock.location'].browse(self.loc_n1_dest_id)
        loc_occupied_dest = self.env['stock.location'].browse(self.loc_occupied_dest_id)

        rec_loc = pt_stor.default_location_src_id or loc_recepcion
        self.env['stock.quant']._update_available_quantity(product_b, rec_loc, 30.0)

        # Occupy loc_occupied_dest with product_a (non-N1 location)
        self.env['stock.quant']._update_available_quantity(product_a, loc_occupied_dest, 5.0)

        controller = irc.ImportRackeoController()
        original_request = irc.request
        mock_request = MagicMock()
        mock_request.env = self.env
        irc.request = mock_request

        try:
            # Test 1: Validate rows with occupancy error and insufficient reservoir error
            raw_rows = [
                {
                    'index': 0,
                    'original_row': [po.name, self.sku_b, loc_occupied_dest.barcode, '10'],
                    'data': {'PO': po.name, 'SKU': self.sku_b, 'UBICACION': loc_occupied_dest.barcode, 'PZS': '10'},
                    'excluded': False
                },
                {
                    'index': 1,
                    'original_row': [po.name, self.sku_b, loc_empty_dest.barcode, '50'], # Exceeds 30 in stock
                    'data': {'PO': po.name, 'SKU': self.sku_b, 'UBICACION': loc_empty_dest.barcode, 'PZS': '50'},
                    'excluded': False
                }
            ]

            val_res = controller.validate_rows(rows=raw_rows)
            rows_res = val_res.get('rows', [])
            self.assertEqual(len(rows_res), 2)

            # Row 0 should have occupied location error
            self.assertTrue(any(e['code'] == 'not_empty' for e in rows_res[0]['errors']))

            # Row 1 should have insufficient reservoir error
            self.assertTrue(any(e['code'] == 'no_reservoir' for e in rows_res[1]['errors']))

            # Test 2: Process valid row
            valid_raw_rows = [
                {
                    'index': 0,
                    'original_row': [po.name, self.sku_b, loc_n1_dest.barcode, '15'],
                    'data': {'PO': po.name, 'SKU': self.sku_b, 'UBICACION': loc_n1_dest.barcode, 'PZS': '15'},
                    'excluded': False
                }
            ]
            process_res = controller.process_rackeo(rows=valid_raw_rows)
            self.assertEqual(process_res.get('status'), 'ok')
            self.assertTrue(process_res.get('created_stors'))
            self.assertTrue(process_res.get('xlsx_file'))

            # Verify generated feedback Excel contains columns and STOR name
            xlsx_bytes = base64.b64decode(process_res['xlsx_file'])
            wb = openpyxl.load_workbook(io.BytesIO(xlsx_bytes))
            sheet = wb.active
            headers = [cell.value for cell in sheet[1]]
            self.assertIn('STOR', headers)
            self.assertIn('Estado', headers)

        finally:
            irc.request = original_request
