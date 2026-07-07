# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase
from odoo.tests import tagged
from odoo.addons.wmds.controllers.import_picks_controller import ImportPicksController

@tagged('post_install', '-at_install')
class TestImportPicksMapping(TransactionCase):

    def test_auto_mapping_exact_format(self):
        # Test headers in the exact requested format
        headers = [
            'OrdenPick', 'Oleada', 'Picker', 'SO', 'PosicionN1',
            'Pasillo', 'Nivel', 'Channel', 'Paqueteria', 'Corte',
            'SKU', 'Titulo', 'Unidades', 'Listo'
        ]
        
        # Exact duplicate of the synonyms and mapping algorithm from import_picks_controller.py
        SYNONYMS = {
            'SO': ['so', 'sale order', 'orden', 'venta', 'pedido', 'sale_order', 'ref', 'reference'],
            'Oleada': ['oleada', 'ola', 'wave', 'grupo', 'lote', 'batch'],
            'Picker': ['picker', 'operador', 'operator', 'usuario', 'surtidor'],
            'PosicionN1': ['posicionn1', 'posicion', 'posicion n1', 'ubicacion', 'ubicación', 'estanteria', 'shelf', 'location', 'ubicación origen'],
            'SKU': ['sku', 'producto', 'product', 'codigo', 'código', 'default_code', 'referencia', 'artículo', 'articulo'],
            'Unidades': ['unidades', 'units', 'cantidad', 'qty', 'count', 'cant', 'unidades a pickear'],
            'OrdenPick': ['ordenpick', 'orden pick', 'secuencia', 'sequence', 'orden_pick', 'order', 'prioridad']
        }
        
        auto_mapping = {}
        
        # 1. First pass: Exact match (case-insensitive) of header with key or any synonym
        for key, syn_list in SYNONYMS.items():
            for idx, h in enumerate(headers):
                h_clean = h.lower().strip()
                if h_clean == key.lower() or h_clean in [s.lower().strip() for s in syn_list]:
                    auto_mapping[key] = idx
                    break
        
        # 2. Second pass: Substring match (only for keys that are not yet mapped, avoiding already mapped columns)
        for key, syn_list in SYNONYMS.items():
            if key not in auto_mapping:
                for idx, h in enumerate(headers):
                    if idx in auto_mapping.values():
                        continue
                    h_clean = h.lower().strip()
                    if any(syn in h_clean for syn in syn_list):
                        auto_mapping[key] = idx
                        break
                        
        # Assertions to ensure each required key maps to its correct index
        self.assertEqual(auto_mapping.get('OrdenPick'), 0)
        self.assertEqual(auto_mapping.get('Oleada'), 1)
        self.assertEqual(auto_mapping.get('Picker'), 2)
        self.assertEqual(auto_mapping.get('SO'), 3)
        self.assertEqual(auto_mapping.get('PosicionN1'), 4)
        self.assertEqual(auto_mapping.get('SKU'), 10)
        self.assertEqual(auto_mapping.get('Unidades'), 12)
        
        # Ensure non-requested columns (Pasillo, Nivel, Channel, Paqueteria, Corte, Titulo, Listo) are NOT mapped to any key
        mapped_indices = list(auto_mapping.values())
        for idx in [5, 6, 7, 8, 9, 11, 13]: # indices of Pasillo, Nivel, Channel, Paqueteria, Corte, Titulo, Listo
            self.assertNotIn(idx, mapped_indices)

    def test_ignore_empty_stock_fields(self):
        controller = ImportPicksController()
        
        # Scenario: a row has SO and Oleada, but PosicionN1, SKU, and Unidades are empty
        row_data = {
            'SO': 'SO001',
            'Oleada': 'Wave 1',
            'Picker': 'Operador 1',
            'PosicionN1': '',
            'SKU': '',
            'Unidades': '',
            'OrdenPick': '1'
        }
        
        # We need mock Odoo environment / request for res.users lookups
        from unittest.mock import MagicMock
        import odoo.addons.wmds.controllers.import_picks_controller as ipc
        
        mock_env = MagicMock()
        # Mock picker user lookup
        mock_user = MagicMock()
        mock_user.id = 42
        mock_user.name = 'Operador 1'
        mock_env['res.users'].sudo().search.return_value = mock_user
        
        # Mock sale.order lookup
        mock_so = MagicMock()
        mock_so.name = 'SO001'
        mock_so.data_ready_to_pick = True
        
        # Mock picking
        mock_pick = MagicMock()
        mock_pick.id = 100
        mock_pick.name = 'WH/OUT/00100'
        mock_pick.state = 'assigned'
        mock_pick.batch_id = False
        
        mock_filtered = MagicMock()
        mock_filtered.__getitem__.return_value = mock_pick
        mock_pick.filtered_domain.return_value = mock_filtered
        
        mock_so.picking_ids = mock_pick
        mock_env['sale.order'].sudo().search.return_value = mock_so
        
        mock_request = MagicMock()
        mock_request.env = mock_env
        
        # Set request mock on the controller module
        original_request = getattr(ipc, 'request', None)
        try:
            ipc.request = mock_request
            res = controller._validate_row_data(row_data, 1, [])
            
            # Since PosicionN1, SKU, and Unidades are empty, they must be ignored completely.
            # No errors or warnings should be generated for them.
            self.assertEqual(res['errors'], [])
            # Also, PosicionN1, SKU, and Unidades remain empty in 'data'
            self.assertEqual(res['data']['PosicionN1'], '')
            self.assertEqual(res['data']['SKU'], '')
            self.assertEqual(res['data']['Unidades'], '')
        finally:
            if original_request is not None:
                ipc.request = original_request
            else:
                try:
                    del ipc.request
                except AttributeError:
                    pass

