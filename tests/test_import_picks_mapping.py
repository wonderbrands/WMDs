# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase
from odoo.tests import tagged
from unittest.mock import MagicMock
import sys
from odoo.addons.wmds.controllers.import_picks_controller import ImportPicksController

@tagged('post_install', '-at_install')
class TestImportPicksMapping(TransactionCase):

    def test_auto_mapping_exact_format(self):
        headers = [
            'orden_pick', 'oleada', 'picker', 'picker_id', 'SO', 'posicion_N1',
            'posicion_N1_id', 'pasillo', 'nivel', 'channel', 'paqueteria',
            'corte', 'SKU', 'titulo', 'unidades', 'listo', 'aging'
        ]
        
        SYNONYMS = {
            'SO': ['so', 'sale order', 'orden', 'venta', 'pedido', 'sale_order', 'ref', 'reference'],
            'Oleada': ['oleada', 'ola', 'wave', 'grupo', 'lote', 'batch'],
            'Picker': ['picker', 'operador', 'operator', 'usuario', 'surtidor'],
            'picker_id': ['picker_id', 'picker id', 'id picker', 'id_picker', 'id operador', 'id_operador', 'id usuario', 'id_usuario'],
            'PosicionN1': ['posicionn1', 'posicion', 'posicion n1', 'posicion_n1', 'ubicacion', 'ubicación', 'estanteria', 'shelf', 'location', 'ubicación origen'],
            'posicion_N1_id': ['posicion_n1_id', 'posicion n1 id', 'id posicion n1', 'id_posicion_n1', 'id ubicacion', 'id_ubicacion', 'id ubicación', 'id_ubicación'],
            'SKU': ['sku', 'producto', 'product', 'codigo', 'código', 'default_code', 'referencia', 'artículo', 'articulo'],
            'Unidades': ['unidades', 'units', 'cantidad', 'qty', 'count', 'cant', 'unidades a pickear'],
            'OrdenPick': ['ordenpick', 'orden pick', 'secuencia', 'sequence', 'orden_pick', 'order', 'prioridad']
        }
        
        auto_mapping = {}
        
        # 1. First pass: Exact match
        for key, syn_list in SYNONYMS.items():
            for idx, h in enumerate(headers):
                h_clean = h.lower().strip()
                if h_clean == key.lower() or h_clean in [s.lower().strip() for s in syn_list]:
                    auto_mapping[key] = idx
                    break
        
        # 2. Second pass: Substring match fallback
        for key, syn_list in SYNONYMS.items():
            if key not in auto_mapping:
                for idx, h in enumerate(headers):
                    if idx in auto_mapping.values():
                        continue
                    h_clean = h.lower().strip()
                    if any(syn in h_clean for syn in syn_list):
                        auto_mapping[key] = idx
                        break
                        
        self.assertEqual(auto_mapping.get('OrdenPick'), 0)
        self.assertEqual(auto_mapping.get('Oleada'), 1)
        self.assertEqual(auto_mapping.get('Picker'), 2)
        self.assertEqual(auto_mapping.get('picker_id'), 3)
        self.assertEqual(auto_mapping.get('SO'), 4)
        self.assertEqual(auto_mapping.get('PosicionN1'), 5)
        self.assertEqual(auto_mapping.get('posicion_N1_id'), 6)
        self.assertEqual(auto_mapping.get('SKU'), 12)
        self.assertEqual(auto_mapping.get('Unidades'), 14)
        
        mapped_indices = list(auto_mapping.values())
        for idx in [7, 8, 9, 10, 11, 13, 15, 16]:
            self.assertNotIn(idx, mapped_indices)

    def test_ignore_empty_stock_fields(self):
        controller = ImportPicksController()
        
        row_data = {
            'SO': 'SO001',
            'Oleada': 'Wave 1',
            'Picker': 'Operador 1',
            'picker_id': '',
            'PosicionN1': '',
            'posicion_N1_id': '',
            'SKU': '',
            'Unidades': '',
            'OrdenPick': '1'
        }
        
        mock_env = MagicMock()
        model_mocks = {}
        def get_model_mock(name):
            if name not in model_mocks:
                model_mocks[name] = MagicMock()
            return model_mocks[name]
        mock_env.__getitem__.side_effect = get_model_mock
        
        mock_user = MagicMock()
        mock_user.id = 42
        mock_user.name = 'Operador 1'
        mock_env['res.users'].sudo().search.return_value = [mock_user]
        
        mock_so = MagicMock()
        mock_so.name = 'SO001'
        mock_so.data_ready_to_pick = True
        
        mock_pick = MagicMock()
        mock_pick.id = 100
        mock_pick.name = 'WH/OUT/00100'
        mock_pick.state = 'assigned'
        mock_pick.batch_id = False
        mock_pick.move_line_ids = []
        
        mock_filtered = MagicMock()
        mock_filtered.__getitem__.return_value = mock_pick
        mock_pick.filtered_domain.return_value = mock_filtered
        
        mock_so.picking_ids = mock_pick
        mock_env['sale.order'].sudo().search.return_value = [mock_so]
        
        # Access active module dynamically
        ipc_module = sys.modules['odoo.addons.wmds.controllers.import_picks_controller']
        original_env = getattr(ipc_module.request, 'env', None)
        try:
            ipc_module.request.env = mock_env
            
            raw_rows = [{
                'index': 1,
                'original_row': [],
                'data': row_data,
                'excluded': False,
                'not_in_excel': False
            }]
            res = controller._validate_and_match_rows(raw_rows)
            
            self.assertEqual(len(res), 1)
            self.assertEqual(res[0]['errors'], [])
            self.assertEqual(res[0]['data']['PosicionN1'], '')
            self.assertEqual(res[0]['data']['SKU'], '')
            self.assertEqual(res[0]['data']['Unidades'], '')
        finally:
            if original_env is not None:
                ipc_module.request.env = original_env

    def test_multiple_lines_matching_and_virtual_rows(self):
        controller = ImportPicksController()
        
        row_data = {
            'SO': 'SO001',
            'Oleada': 'Wave 1',
            'Picker': 'Operador 1',
            'picker_id': '',
            'PosicionN1': 'W',
            'posicion_N1_id': '',
            'SKU': 'A',
            'Unidades': '1',
            'OrdenPick': '1'
        }
        
        mock_env = MagicMock()
        model_mocks = {}
        def get_model_mock(name):
            if name not in model_mocks:
                model_mocks[name] = MagicMock()
            return model_mocks[name]
        mock_env.__getitem__.side_effect = get_model_mock
        
        mock_user = MagicMock()
        mock_user.id = 42
        mock_user.name = 'Operador 1'
        
        mock_so = MagicMock()
        mock_so.name = 'SO001'
        mock_so.data_ready_to_pick = True
        
        prod_a = MagicMock()
        prod_a.id = 1
        prod_a.default_code = 'A'
        prod_a.barcode = 'A'
        
        prod_b = MagicMock()
        prod_b.id = 2
        prod_b.default_code = 'B'
        prod_b.barcode = 'B'
        
        loc_x = MagicMock()
        loc_x.id = 10
        loc_x.barcode = 'X'
        loc_x.name = 'X'
        
        loc_y = MagicMock()
        loc_y.id = 11
        loc_y.barcode = 'Y'
        loc_y.name = 'Y'
        
        loc_z = MagicMock()
        loc_z.id = 12
        loc_z.barcode = 'Z'
        loc_z.name = 'Z'
        
        loc_w = MagicMock()
        loc_w.id = 13
        loc_w.barcode = 'W'
        loc_w.name = 'W'
        loc_w.complete_name = 'W'
        loc_w.is_location_blocked.return_value = False
        
        ml1 = MagicMock()
        ml1.id = 1001
        ml1.product_id = prod_a
        ml1.location_id = loc_x
        ml1.quantity = 1.0
        
        ml2 = MagicMock()
        ml2.id = 1002
        ml2.product_id = prod_a
        ml2.location_id = loc_y
        ml2.quantity = 1.0
        
        ml3 = MagicMock()
        ml3.id = 1003
        ml3.product_id = prod_b
        ml3.location_id = loc_z
        ml3.quantity = 1.0
        
        mock_pick = MagicMock()
        mock_pick.id = 100
        mock_pick.name = 'WH/OUT/00100'
        mock_pick.state = 'assigned'
        mock_pick.batch_id = False
        mock_pick.move_line_ids = [ml1, ml2, ml3]
        
        mock_filtered = MagicMock()
        mock_filtered.__getitem__.return_value = mock_pick
        mock_pick.filtered_domain.return_value = mock_filtered
        
        mock_so.picking_ids = mock_pick
        
        def mock_search(model, domain, limit=None):
            if model == 'sale.order':
                return [mock_so]
            elif model == 'res.users':
                return [mock_user]
            elif model == 'stock.location':
                domain_str = str(domain)
                res_locs = []
                if 'W' in domain_str or '13' in domain_str:
                    res_locs.append(loc_w)
                if 'X' in domain_str or '10' in domain_str:
                    res_locs.append(loc_x)
                if 'Y' in domain_str or '11' in domain_str:
                    res_locs.append(loc_y)
                if 'Z' in domain_str or '12' in domain_str:
                    res_locs.append(loc_z)
                return res_locs
            elif model == 'product.product':
                return [prod_a, prod_b]
            return []
            
        mock_env.user = mock_user
        mock_env['sale.order'].sudo().search = MagicMock(side_effect=lambda d, limit=None: mock_search('sale.order', d, limit))
        mock_env['res.users'].sudo().search = MagicMock(side_effect=lambda d, limit=None: mock_search('res.users', d, limit))
        mock_env['stock.location'].sudo().search = MagicMock(side_effect=lambda d, limit=None: mock_search('stock.location', d, limit))
        mock_env['product.product'].sudo().search = MagicMock(side_effect=lambda d, limit=None: mock_search('product.product', d, limit))
        
        def mock_quant_search(domain):
            quants = []
            
            q_aw = MagicMock()
            q_aw.location_id.id = 13
            q_aw.product_id.id = 1
            q_aw.quantity = 5.0
            q_aw.reserved_quantity = 0.0
            quants.append(q_aw)
            
            q_ax = MagicMock()
            q_ax.location_id.id = 10
            q_ax.product_id.id = 1
            q_ax.quantity = 5.0
            q_ax.reserved_quantity = 0.0
            quants.append(q_ax)

            q_ay = MagicMock()
            q_ay.location_id.id = 11
            q_ay.product_id.id = 1
            q_ay.quantity = 5.0
            q_ay.reserved_quantity = 0.0
            quants.append(q_ay)

            q_bz = MagicMock()
            q_bz.location_id.id = 12
            q_bz.product_id.id = 2
            q_bz.quantity = 5.0
            q_bz.reserved_quantity = 0.0
            quants.append(q_bz)

            return quants
            
        mock_env['stock.quant'].sudo().search = MagicMock(side_effect=mock_quant_search)
        
        # Access active module dynamically
        ipc_module = sys.modules['odoo.addons.wmds.controllers.import_picks_controller']
        original_env = getattr(ipc_module.request, 'env', None)
        try:
            ipc_module.request.env = mock_env
            
            raw_rows = [{
                'index': 0,
                'original_row': [],
                'data': row_data,
                'excluded': False,
                'not_in_excel': False
            }]
            
            res = controller._validate_and_match_rows(raw_rows)
            
            # Under the new quantity-match rollback rules:
            # Since suggested quantity was 1.0 but Odoo has 2.0:
            # - Excel row 0 is reverted to Odoo's first reservation (loc X, qty 1.0) with a qty_mismatch warning.
            # - Odoo's second reservation ml2 (loc Y, qty 1.0) is added as a virtual row with a qty_mismatch warning.
            # - Odoo's third reservation ml3 for SKU B (loc Z, qty 1.0) has no Excel suggestions, so it's added as a virtual row with a not_in_excel warning.
            self.assertEqual(len(res), 3)
            
            self.assertEqual(res[0]['index'], 0)
            self.assertEqual(res[0]['not_in_excel'], False)
            self.assertEqual(res[0]['data']['PosicionN1'], 'X') # Reverted to X!
            self.assertEqual(float(res[0]['data']['Unidades']), 1.0)
            self.assertTrue(any(w['code'] == 'qty_mismatch' for w in res[0]['warnings']))
            
            self.assertEqual(res[1]['not_in_excel'], True)
            self.assertEqual(res[1]['data']['PosicionN1'], 'Y') # Virtual row ml2 at Y
            self.assertEqual(float(res[1]['data']['Unidades']), 1.0)
            self.assertTrue(any(w['code'] == 'qty_mismatch' for w in res[1]['warnings']))
            
            self.assertEqual(res[2]['not_in_excel'], True)
            self.assertEqual(res[2]['data']['PosicionN1'], 'Z')
            self.assertEqual(res[2]['odoo_data']['move_line_id'], 1003)
            self.assertTrue(any(w['code'] == 'not_in_excel' for w in res[2]['warnings']))
            
        finally:
            if original_env is not None:
                ipc_module.request.env = original_env

    def test_quantity_mismatch_rollback(self):
        controller = ImportPicksController()
        
        # Odoo has 2 units reserved for product A (1 unit at X, 1 unit at Y)
        # Excel suggests 3 units for product A at location W
        row_data = {
            'SO': 'SO001',
            'Oleada': 'Wave 1',
            'Picker': 'Operador 1',
            'picker_id': '',
            'PosicionN1': 'W',
            'posicion_N1_id': '',
            'SKU': 'A',
            'Unidades': '3',
            'OrdenPick': '1'
        }
        
        mock_env = MagicMock()
        model_mocks = {}
        def get_model_mock(name):
            if name not in model_mocks:
                model_mocks[name] = MagicMock()
            return model_mocks[name]
        mock_env.__getitem__.side_effect = get_model_mock
        
        mock_user = MagicMock()
        mock_user.id = 42
        mock_user.name = 'Operador 1'
        
        mock_so = MagicMock()
        mock_so.name = 'SO001'
        mock_so.data_ready_to_pick = True
        
        prod_a = MagicMock()
        prod_a.id = 1
        prod_a.default_code = 'A'
        prod_a.barcode = 'A'
        
        loc_x = MagicMock()
        loc_x.id = 10
        loc_x.barcode = 'X'
        loc_x.name = 'X'
        
        loc_y = MagicMock()
        loc_y.id = 11
        loc_y.barcode = 'Y'
        loc_y.name = 'Y'
        
        loc_w = MagicMock()
        loc_w.id = 13
        loc_w.barcode = 'W'
        loc_w.name = 'W'
        
        ml1 = MagicMock()
        ml1.id = 1001
        ml1.product_id = prod_a
        ml1.location_id = loc_x
        ml1.quantity = 1.0
        
        ml2 = MagicMock()
        ml2.id = 1002
        ml2.product_id = prod_a
        ml2.location_id = loc_y
        ml2.quantity = 1.0
        
        mock_pick = MagicMock()
        mock_pick.id = 100
        mock_pick.name = 'WH/OUT/00100'
        mock_pick.state = 'assigned'
        mock_pick.batch_id = False
        mock_pick.move_line_ids = [ml1, ml2]
        
        mock_filtered = MagicMock()
        mock_filtered.__getitem__.return_value = mock_pick
        mock_pick.filtered_domain.return_value = mock_filtered
        mock_so.picking_ids = mock_pick
        
        def mock_search(model, domain, limit=None):
            if model == 'sale.order':
                return [mock_so]
            elif model == 'res.users':
                return [mock_user]
            elif model == 'stock.location':
                domain_str = str(domain)
                res_locs = []
                if 'W' in domain_str or '13' in domain_str:
                    res_locs.append(loc_w)
                if 'X' in domain_str or '10' in domain_str:
                    res_locs.append(loc_x)
                if 'Y' in domain_str or '11' in domain_str:
                    res_locs.append(loc_y)
                return res_locs
            elif model == 'product.product':
                return [prod_a]
            return []
            
        mock_env.user = mock_user
        mock_env['sale.order'].sudo().search = MagicMock(side_effect=lambda d, limit=None: mock_search('sale.order', d, limit))
        mock_env['res.users'].sudo().search = MagicMock(side_effect=lambda d, limit=None: mock_search('res.users', d, limit))
        mock_env['stock.location'].sudo().search = MagicMock(side_effect=lambda d, limit=None: mock_search('stock.location', d, limit))
        mock_env['product.product'].sudo().search = MagicMock(side_effect=lambda d, limit=None: mock_search('product.product', d, limit))
        
        def mock_quant_search(domain):
            quants = []
            q_aw = MagicMock()
            q_aw.location_id.id = 13
            q_aw.product_id.id = 1
            q_aw.quantity = 5.0
            q_aw.reserved_quantity = 0.0
            quants.append(q_aw)
            
            q_ax = MagicMock()
            q_ax.location_id.id = 10
            q_ax.product_id.id = 1
            q_ax.quantity = 5.0
            q_ax.reserved_quantity = 0.0
            quants.append(q_ax)

            q_ay = MagicMock()
            q_ay.location_id.id = 11
            q_ay.product_id.id = 1
            q_ay.quantity = 5.0
            q_ay.reserved_quantity = 0.0
            quants.append(q_ay)
            return quants
            
        mock_env['stock.quant'].sudo().search = MagicMock(side_effect=mock_quant_search)
        
        # Access active module dynamically
        ipc_module = sys.modules['odoo.addons.wmds.controllers.import_picks_controller']
        original_env = getattr(ipc_module.request, 'env', None)
        try:
            ipc_module.request.env = mock_env
            
            raw_rows = [{
                'index': 0,
                'original_row': [],
                'data': row_data,
                'excluded': False,
                'not_in_excel': False
            }]
            
            res = controller._validate_and_match_rows(raw_rows)
            
            # Since suggested quantity was 3.0 but Odoo only has 2.0:
            # - The first Excel row is reverted to Odoo's first reservation (1 unit at loc X).
            # - The second reservation (1 unit at loc Y) is generated as a virtual row.
            self.assertEqual(len(res), 2)
            
            # Excel row 0 reverted to X, qty 1.0, and has warning
            self.assertEqual(res[0]['index'], 0)
            self.assertEqual(res[0]['not_in_excel'], False)
            self.assertEqual(res[0]['data']['PosicionN1'], 'X')
            self.assertEqual(float(res[0]['data']['Unidades']), 1.0)
            self.assertTrue(any(w['code'] == 'qty_mismatch' for w in res[0]['warnings']))
            
            # Virtual row from Odoo (loc Y, qty 1.0) is added with warning
            self.assertEqual(res[1]['not_in_excel'], True)
            self.assertEqual(res[1]['data']['PosicionN1'], 'Y')
            self.assertEqual(float(res[1]['data']['Unidades']), 1.0)
            self.assertTrue(any(w['code'] == 'qty_mismatch' for w in res[1]['warnings']))
            
        finally:
            if original_env is not None:
                ipc_module.request.env = original_env

