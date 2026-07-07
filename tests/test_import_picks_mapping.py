# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase
from odoo.tests import tagged
from unittest.mock import MagicMock
import odoo.addons.wmds.controllers.import_picks_controller as ipc
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
            'OrdenPick': ['ordenpick', 'orden pick', 'orden_pick', 'secuencia', 'sequence', 'order', 'prioridad']
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
        mock_env['res.users'].sudo().search.return_value = mock_user
        
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
        mock_env['sale.order'].sudo().search.return_value = mock_so
        
        mock_request = MagicMock()
        mock_request.env = mock_env
        
        original_request = getattr(ipc, 'request', None)
        try:
            ipc.request = mock_request
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
            if original_request is not None:
                ipc.request = original_request
            else:
                try:
                    del ipc.request
                except AttributeError:
                    pass

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
                return mock_so
            elif model == 'res.users':
                return mock_user
            elif model == 'stock.location':
                val = domain[0][2]
                if val == 'W':
                    return loc_w
                elif val == 'X':
                    return loc_x
                elif val == 'Y':
                    return loc_y
                elif val == 'Z':
                    return loc_z
            return MagicMock()
            
        mock_env.user = mock_user
        mock_env['sale.order'].sudo().search = MagicMock(side_effect=lambda d, limit=None: mock_search('sale.order', d, limit))
        mock_env['res.users'].sudo().search = MagicMock(side_effect=lambda d, limit=None: mock_search('res.users', d, limit))
        mock_env['stock.location'].sudo().search = MagicMock(side_effect=lambda d, limit=None: mock_search('stock.location', d, limit))
        
        mock_quant = MagicMock()
        mock_quant.quantity = 5.0
        mock_quant.reserved_quantity = 0.0
        mock_env['stock.quant'].sudo().search.return_value = mock_quant
        
        mock_request = MagicMock()
        mock_request.env = mock_env
        
        original_request = getattr(ipc, 'request', None)
        try:
            ipc.request = mock_request
            raw_rows = [{
                'index': 0,
                'original_row': [],
                'data': row_data,
                'excluded': False,
                'not_in_excel': False
            }]
            
            res = controller._validate_and_match_rows(raw_rows)
            
            self.assertEqual(len(res), 3)
            
            self.assertEqual(res[0]['index'], 0)
            self.assertEqual(res[0]['not_in_excel'], False)
            self.assertEqual(res[0]['data']['PosicionN1'], 'W')
            self.assertEqual(res[0]['odoo_data']['move_line_id'], 1001)
            
            self.assertEqual(res[1]['not_in_excel'], True)
            self.assertEqual(res[1]['data']['PosicionN1'], 'Y')
            self.assertEqual(res[1]['odoo_data']['move_line_id'], 1002)
            self.assertTrue(any(w['code'] == 'not_in_excel' for w in res[1]['warnings']))
            
            self.assertEqual(res[2]['not_in_excel'], True)
            self.assertEqual(res[2]['data']['PosicionN1'], 'Z')
            self.assertEqual(res[2]['odoo_data']['move_line_id'], 1003)
            self.assertTrue(any(w['code'] == 'not_in_excel' for w in res[2]['warnings']))
            
        finally:
            if original_request is not None:
                ipc.request = original_request
            else:
                try:
                    del ipc.request
                except AttributeError:
                    pass
