# -*- coding: utf-8 -*-
import json
import csv
import io
import base64
import xlsxwriter
import polars as pl
from odoo import http
from odoo.http import request

class ImportPicksController(http.Controller):

    def _safe_int(self, val, default=9999):
        if not val:
            return default
        try:
            return int(float(str(val).strip()))
        except ValueError:
            return default

    def _validate_row_data(self, row_data, index, original_row):
        raw_rows = [{
            'index': index,
            'original_row': original_row,
            'data': row_data,
            'excluded': False,
            'not_in_excel': False
        }]
        res = self._validate_and_match_rows(raw_rows)
        return res[0] if res else {}

    def _validate_picker_in_row(self, val_row, user_maps=None):
        picker_name = val_row['data'].get('Picker')
        picker_id = val_row['data'].get('picker_id')
        picker_user = None
        
        if user_maps:
            user_map_by_id, user_map_by_name, user_map_by_login = user_maps
            if picker_id:
                try:
                    pid_int = int(float(picker_id))
                    picker_user = user_map_by_id.get(pid_int)
                except Exception:
                    pass
            if not picker_user and picker_name:
                pn_clean = picker_name.strip().lower()
                picker_user = user_map_by_name.get(pn_clean) or user_map_by_login.get(pn_clean)
        else:
            if picker_id:
                try:
                    picker_user = request.env['res.users'].sudo().browse(int(float(picker_id)))
                    if not picker_user.exists():
                        picker_user = None
                except Exception:
                    pass
                    
            if not picker_user and picker_name:
                picker_user = request.env['res.users'].sudo().search([('name', '=', picker_name)], limit=1)
                if not picker_user:
                    picker_user = request.env['res.users'].sudo().search([('login', '=', picker_name)], limit=1)
                
        if picker_user:
            val_row['picker_id'] = picker_user.id
            val_row['data']['Picker'] = picker_user.name
            val_row['data']['picker_id'] = str(picker_user.id)
        elif picker_name or picker_id:
            val_row['errors'].append({'field': 'Picker', 'code': 'not_found', 'message': f'El operador "{picker_name or picker_id}" no existe.'})

    def _validate_location_and_stock(self, val_row, stock_cache, ml=None, prod=None, pick_odoo=None, loc_maps=None):
        suggested_loc_name = val_row['data'].get('PosicionN1')
        suggested_loc_id = val_row['data'].get('posicion_N1_id')
        unidades_str = val_row['data'].get('Unidades')
        
        original_loc_name = val_row['odoo_data']['location_name'] if val_row.get('odoo_data') else ""
        original_loc_id = val_row['odoo_data']['location_id'] if val_row.get('odoo_data') else None
        
        product_record = ml.product_id if ml else prod
        if not product_record:
            return
            
        loc = None
        if loc_maps:
            loc_map_by_id, loc_map_by_barcode, loc_map_by_name = loc_maps
            if suggested_loc_id:
                try:
                    lid_int = int(float(suggested_loc_id))
                    loc = loc_map_by_id.get(lid_int)
                except Exception:
                    pass
            if not loc and suggested_loc_name:
                ln_clean = suggested_loc_name.strip().lower()
                loc = loc_map_by_barcode.get(ln_clean) or loc_map_by_name.get(ln_clean)
        else:
            if suggested_loc_id:
                try:
                    loc = request.env['stock.location'].sudo().browse(int(float(suggested_loc_id)))
                    if not loc.exists():
                        loc = None
                except Exception:
                    pass
                    
            if not loc and suggested_loc_name:
                loc = request.env['stock.location'].sudo().search([('barcode', '=', suggested_loc_name)], limit=1)
                if not loc:
                    loc = request.env['stock.location'].sudo().search([('name', '=', suggested_loc_name)], limit=1)
                
        if not loc:
            if original_loc_name:
                val_row['warnings'].append({
                    'field': 'PosicionN1', 
                    'code': 'not_found', 
                    'message': f"La ubicación sugerida '{suggested_loc_name}' no existe. Se usará la ubicación original de Odoo: '{original_loc_name}'."
                })
                val_row['data']['PosicionN1'] = original_loc_name
                val_row['data']['posicion_N1_id'] = str(original_loc_id)
                val_row['location_id'] = original_loc_id
            else:
                val_row['errors'].append({
                    'field': 'PosicionN1', 
                    'code': 'not_found', 
                    'message': f"La ubicación '{suggested_loc_name}' no existe."
                })
        else:
            if loc.is_location_blocked():
                if original_loc_name:
                    val_row['warnings'].append({
                        'field': 'PosicionN1', 
                        'code': 'blocked', 
                        'message': f"La ubicación sugerida '{loc.complete_name}' está bloqueada. Se usará la ubicación original de Odoo: '{original_loc_name}'."
                    })
                    val_row['data']['PosicionN1'] = original_loc_name
                    val_row['data']['posicion_N1_id'] = str(original_loc_id)
                    val_row['location_id'] = original_loc_id
                else:
                    val_row['errors'].append({
                        'field': 'PosicionN1', 
                        'code': 'blocked', 
                        'message': f"La ubicación '{loc.complete_name}' está bloqueada."
                    })
            else:
                units = ml.quantity if ml else 0.0
                if unidades_str:
                    try:
                        units = float(unidades_str)
                    except ValueError:
                        pass
                if not units and pick_odoo:
                    move = pick_odoo.move_ids.filtered(lambda m: m.product_id.id == product_record.id)[:1]
                    units = move.product_uom_qty if move else 1.0
                    
                if original_loc_id and loc.id == original_loc_id:
                    val_row['location_id'] = loc.id
                    val_row['data']['PosicionN1'] = loc.barcode or loc.name
                    val_row['data']['posicion_N1_id'] = str(loc.id)
                else:
                    stock_key = (loc.id, product_record.id)
                    if stock_key not in stock_cache:
                        quant = request.env['stock.quant'].sudo().search([('location_id', '=', loc.id), ('product_id', '=', product_record.id)], limit=1)
                        avail_stock = quant.quantity - quant.reserved_quantity if quant else 0.0
                        stock_cache[stock_key] = max(0.0, avail_stock)
                        
                    avail = stock_cache[stock_key]
                    if avail < units:
                        if original_loc_name:
                            val_row['warnings'].append({
                                'field': 'PosicionN1', 
                                'code': 'no_stock', 
                                'message': f"Stock insuficiente en ubicación sugerida (Disponible: {avail}, Requerido: {units}). Se usará la original de Odoo: '{original_loc_name}'."
                            })
                            val_row['data']['PosicionN1'] = original_loc_name
                            val_row['data']['posicion_N1_id'] = str(original_loc_id)
                            val_row['location_id'] = original_loc_id
                        else:
                            val_row['warnings'].append({
                                'field': 'PosicionN1', 
                                'code': 'no_stock', 
                                'message': f"Stock insuficiente en la ubicación sugerida '{loc.barcode or loc.name}' (Disponible: {avail}, Requerido: {units})."
                            })
                    else:
                        stock_cache[stock_key] -= units
                        val_row['location_id'] = loc.id
                        val_row['data']['PosicionN1'] = loc.barcode or loc.name
                        val_row['data']['posicion_N1_id'] = str(loc.id)

    def _validate_units_in_row(self, val_row):
        unidades_str = val_row['data'].get('Unidades')
        if unidades_str:
            try:
                u_float = float(unidades_str)
                if u_float <= 0:
                    val_row['errors'].append({'field': 'Unidades', 'code': 'invalid', 'message': 'Las unidades deben ser mayores a cero.'})
            except ValueError:
                val_row['errors'].append({'field': 'Unidades', 'code': 'invalid', 'message': 'Las unidades deben un número válido.'})

    def _prefetch_sale_orders(self, so_names):
        so_map = {}
        if not so_names:
            return so_map
        so_names_list = list(set(filter(None, [n.strip() for n in so_names])))
        if not so_names_list:
            return so_map
        sales_orders = request.env['sale.order'].sudo().search([('name', 'in', so_names_list)])
        for so in sales_orders:
            so_map[so.name.strip().lower()] = so
            
        missing_so_names = [n for n in so_names_list if n.strip().lower() not in so_map]
        for missing_name in missing_so_names:
            so_found = request.env['sale.order'].sudo().search([('name', '=ilike', missing_name)], limit=1)
            if not so_found:
                so_found = request.env['sale.order'].sudo().search([('name', 'ilike', missing_name)], limit=1)
            if so_found:
                so_map[missing_name.strip().lower()] = so_found
        return so_map

    def _prefetch_products(self, skus):
        product_map = {}
        if not skus:
            return product_map
        skus_list = list(set(filter(None, [s.strip() for s in skus])))
        if not skus_list:
            return product_map
        products = request.env['product.product'].sudo().search(['|', ('default_code', 'in', skus_list), ('barcode', 'in', skus_list)])
        for prod in products:
            if prod.default_code:
                product_map[prod.default_code.strip().lower()] = prod
            if prod.barcode:
                product_map[prod.barcode.strip().lower()] = prod
        return product_map

    def _prefetch_locations(self, loc_names, loc_ids=None):
        loc_map_by_id = {}
        loc_map_by_barcode = {}
        loc_map_by_name = {}
        
        loc_names_list = list(set(filter(None, [ln.strip() for ln in loc_names])))
        loc_ids_list = list(set(filter(None, loc_ids))) if loc_ids else []
        
        if not loc_names_list and not loc_ids_list:
            return loc_map_by_id, loc_map_by_barcode, loc_map_by_name
            
        domain = []
        if loc_ids_list and loc_names_list:
            domain = ['|', ('id', 'in', loc_ids_list), '|', ('barcode', 'in', loc_names_list), ('name', 'in', loc_names_list)]
        elif loc_ids_list:
            domain = [('id', 'in', loc_ids_list)]
        else:
            domain = ['|', ('barcode', 'in', loc_names_list), ('name', 'in', loc_names_list)]
            
        locations = request.env['stock.location'].sudo().search(domain)
        for l in locations:
            loc_map_by_id[l.id] = l
            if l.barcode:
                loc_map_by_barcode[l.barcode.strip().lower()] = l
            if l.name:
                loc_map_by_name[l.name.strip().lower()] = l
                
        return loc_map_by_id, loc_map_by_barcode, loc_map_by_name

    def _prefetch_users(self, user_names, user_ids=None):
        user_map_by_id = {}
        user_map_by_name = {}
        user_map_by_login = {}
        
        names_list = list(set(filter(None, [un.strip() for un in user_names])))
        ids_list = list(set(filter(None, user_ids))) if user_ids else []
        
        if not names_list and not ids_list:
            return user_map_by_id, user_map_by_name, user_map_by_login
            
        domain = []
        if ids_list and names_list:
            domain = ['|', ('id', 'in', ids_list), '|', ('name', 'in', names_list), ('login', 'in', names_list)]
        elif ids_list:
            domain = [('id', 'in', ids_list)]
        else:
            domain = ['|', ('name', 'in', names_list), ('login', 'in', names_list)]
            
        users = request.env['res.users'].sudo().search(domain)
        for u in users:
            user_map_by_id[u.id] = u
            user_map_by_name[u.name.strip().lower()] = u
            user_map_by_login[u.login.strip().lower()] = u
            
        return user_map_by_id, user_map_by_name, user_map_by_login

    def _validate_and_match_rows(self, raw_rows):
        validated_rows = []
        location_product_stock = {}
        
        excel_rows = [r for r in raw_rows if not r.get('not_in_excel', False)]
        virtual_rows = [r for r in raw_rows if r.get('not_in_excel', False)]
        
        # Split excel rows into active and ignored
        active_excel_rows = []
        ignored_excel_rows = []
        for r in excel_rows:
            pos = r.get('data', {}).get('PosicionN1', '').strip()
            sku = r.get('data', {}).get('SKU', '').strip()
            uni = r.get('data', {}).get('Unidades', '').strip()
            if not pos and not sku and not uni:
                ignored_excel_rows.append(r)
            else:
                active_excel_rows.append(r)
                
        # Group active excel rows by SO name
        excel_rows_by_so = {}
        for r in active_excel_rows:
            so_name = r.get('data', {}).get('SO', '').strip()
            excel_rows_by_so.setdefault(so_name, []).append(r)
            
        # Group ignored excel rows by SO name
        ignored_rows_by_so = {}
        for r in ignored_excel_rows:
            so_name = r.get('data', {}).get('SO', '').strip()
            ignored_rows_by_so.setdefault(so_name, []).append(r)
            
        # Group virtual rows by SO name
        virtual_rows_by_so = {}
        for r in virtual_rows:
            so_name = r.get('data', {}).get('SO', '').strip()
            virtual_rows_by_so.setdefault(so_name, []).append(r)
            
        all_so_names = set(excel_rows_by_so.keys()).union(set(virtual_rows_by_so.keys())).union(set(ignored_rows_by_so.keys()))
        
        # 1. Pre-fetch sale.order
        so_map = self._prefetch_sale_orders(list(all_so_names))
        
        # 2. Pre-fetch res.users (pickers)
        picker_names = set()
        picker_ids = set()
        for r in raw_rows:
            pn = r.get('data', {}).get('Picker', '').strip()
            pid = r.get('data', {}).get('picker_id', '').strip()
            if pn:
                picker_names.add(pn)
            if pid:
                try:
                    picker_ids.add(int(float(pid)))
                except ValueError:
                    pass
        user_maps = self._prefetch_users(list(picker_names), list(picker_ids))
        
        # 3. Pre-fetch stock.location (suggested locations)
        loc_names = set()
        loc_ids = set()
        for r in raw_rows:
            ln = r.get('data', {}).get('PosicionN1', '').strip()
            lid = r.get('data', {}).get('posicion_N1_id', '').strip()
            if ln:
                loc_names.add(ln)
            if lid:
                try:
                    loc_ids.add(int(float(lid)))
                except ValueError:
                    pass
        loc_maps = self._prefetch_locations(list(loc_names), list(loc_ids))
        
        # 4. Pre-fetch products
        skus = set()
        for r in raw_rows:
            sku = r.get('data', {}).get('SKU', '').strip()
            if sku:
                skus.add(sku)
        product_map = self._prefetch_products(list(skus))
        
        # 5. Pre-fetch stock.quant
        all_resolved_loc_ids = set()
        all_resolved_prod_ids = set()
        
        for so_name in all_so_names:
            so = so_map.get(so_name.strip().lower())
            if so:
                pick_odoo = so.picking_ids.filtered_domain([
                    ('picking_type_id.name', '=', 'Pick'),
                    ('state', '!=', 'cancel')
                ])[:1]
                if pick_odoo:
                    for ml in pick_odoo.move_line_ids:
                        all_resolved_prod_ids.add(ml.product_id.id)
                        all_resolved_loc_ids.add(ml.location_id.id)
                        
        for l in loc_maps[0].values():
            all_resolved_loc_ids.add(l.id)
            
        for p in product_map.values():
            all_resolved_prod_ids.add(p.id)
            
        if all_resolved_loc_ids and all_resolved_prod_ids:
            quants = request.env['stock.quant'].sudo().search([
                ('location_id', 'in', list(all_resolved_loc_ids)),
                ('product_id', 'in', list(all_resolved_prod_ids))
            ])
            for q in quants:
                location_product_stock[(q.location_id.id, q.product_id.id)] = max(0.0, q.quantity - q.reserved_quantity)
                
        # Main matching and validation loops
        for so_name in all_so_names:
            group_excel = excel_rows_by_so.get(so_name, [])
            group_ignored = ignored_rows_by_so.get(so_name, [])
            group_virtual = virtual_rows_by_so.get(so_name, [])
            
            # Process ignored rows first
            for r in group_ignored:
                val_row = {
                    'index': r.get('index', 0),
                    'original_row': r.get('original_row', []),
                    'data': dict(r.get('data', {})),
                    'excluded': r.get('excluded', False),
                    'errors': [],
                    'warnings': [],
                    'picking_id': False,
                    'picking_name': '',
                    'picking_state': '',
                    'product_id': False,
                    'location_id': False,
                    'picker_id': False,
                    'not_in_excel': False
                }
                if not so_name:
                    val_row['errors'].append({'field': 'SO', 'code': 'missing', 'message': 'El campo SO es obligatorio.'})
                else:
                    so = so_map.get(so_name.strip().lower())
                    if not so:
                        val_row['errors'].append({'field': 'SO', 'code': 'not_found', 'message': f'La SO "{so_name}" no existe.'})
                    else:
                        val_row['data']['SO'] = so.name
                        if not so.data_ready_to_pick:
                            val_row['errors'].append({'field': 'SO', 'code': 'not_ready', 'message': f'La SO "{so.name}" no está lista para recolectar (data_ready_to_pick es falso).'})
                        
                        pick_odoo = so.picking_ids.filtered_domain([
                            ('picking_type_id.name', '=', 'Pick'),
                            ('state', '!=', 'cancel')
                        ])[:1]
                        
                        if not pick_odoo:
                            val_row['errors'].append({'field': 'SO', 'code': 'no_pick', 'message': f'La SO "{so.name}" no tiene un pick de tipo "Pick" válido.'})
                        else:
                            val_row['picking_id'] = pick_odoo.id
                            val_row['picking_name'] = pick_odoo.name
                            val_row['picking_state'] = pick_odoo.state
                            if pick_odoo.batch_id:
                                val_row['errors'].append({'field': 'SO', 'code': 'already_in_batch', 'message': f'El pick {pick_odoo.name} ya pertenece al plan de pickeo (lote) "{pick_odoo.batch_id.name}".'})
                                
                self._validate_picker_in_row(val_row, user_maps=user_maps)
                if not val_row['data'].get('Oleada'):
                    val_row['errors'].append({'field': 'Oleada', 'code': 'missing', 'message': 'El campo Oleada es obligatorio.'})
                validated_rows.append(val_row)
                
            if not so_name:
                for r in group_excel:
                    val_row = {
                        'index': r.get('index', 0),
                        'original_row': r.get('original_row', []),
                        'data': dict(r.get('data', {})),
                        'excluded': r.get('excluded', False),
                        'errors': [{'field': 'SO', 'code': 'missing', 'message': 'El campo SO es obligatorio.'}],
                        'warnings': [],
                        'picking_id': False,
                        'picking_name': '',
                        'picking_state': '',
                        'product_id': False,
                        'location_id': False,
                        'picker_id': False,
                        'not_in_excel': False
                    }
                    self._validate_picker_in_row(val_row, user_maps=user_maps)
                    validated_rows.append(val_row)
                continue
                
            so = so_map.get(so_name.strip().lower())
            if not so:
                for r in group_excel:
                    val_row = {
                        'index': r.get('index', 0),
                        'original_row': r.get('original_row', []),
                        'data': dict(r.get('data', {})),
                        'excluded': r.get('excluded', False),
                        'errors': [{'field': 'SO', 'code': 'not_found', 'message': f'La SO "{so_name}" no existe.'}],
                        'warnings': [],
                        'picking_id': False,
                        'picking_name': '',
                        'picking_state': '',
                        'product_id': False,
                        'location_id': False,
                        'picker_id': False,
                        'not_in_excel': False
                    }
                    self._validate_picker_in_row(val_row, user_maps=user_maps)
                    validated_rows.append(val_row)
                continue
                
            for r in group_excel:
                r['data']['SO'] = so.name
            for r in group_virtual:
                r['data']['SO'] = so.name
                
            so_errors = []
            if not so.data_ready_to_pick:
                so_errors.append({
                    'field': 'SO', 
                    'code': 'not_ready', 
                    'message': f'La SO "{so.name}" no está lista para recolectar (data_ready_to_pick es falso).'
                })
                
            pick_odoo = so.picking_ids.filtered_domain([
                ('picking_type_id.name', '=', 'Pick'),
                ('state', '!=', 'cancel')
            ])[:1]
            
            if not pick_odoo:
                so_errors.append({
                    'field': 'SO', 
                    'code': 'no_pick', 
                    'message': f'La SO "{so.name}" no tiene un pick de tipo "Pick" válido.'
                })
            else:
                if pick_odoo.batch_id:
                    so_errors.append({
                        'field': 'SO', 
                        'code': 'already_in_batch', 
                        'message': f'El pick {pick_odoo.name} ya pertenece al plan de pickeo (lote) "{pick_odoo.batch_id.name}".'
                    })
                    
            if so_errors:
                for r in group_excel:
                    val_row = {
                        'index': r.get('index', 0),
                        'original_row': r.get('original_row', []),
                        'data': dict(r.get('data', {})),
                        'excluded': r.get('excluded', False),
                        'errors': list(so_errors),
                        'warnings': [],
                        'picking_id': pick_odoo.id if pick_odoo else False,
                        'picking_name': pick_odoo.name if pick_odoo else '',
                        'picking_state': pick_odoo.state if pick_odoo else '',
                        'product_id': False,
                        'location_id': False,
                        'picker_id': False,
                        'not_in_excel': False
                    }
                    self._validate_picker_in_row(val_row, user_maps=user_maps)
                    validated_rows.append(val_row)
                continue
                
            # Match active lines
            move_lines = pick_odoo.move_line_ids
            
            odoo_lines_by_sku = {}
            for ml in move_lines:
                sku_key = ml.product_id.default_code or ml.product_id.barcode
                if sku_key:
                    sku_key_clean = sku_key.strip().lower()
                    odoo_lines_by_sku.setdefault(sku_key_clean, []).append(ml)
                    
            excel_rows_by_sku = {}
            for r in group_excel:
                sku_key = r.get('data', {}).get('SKU', '').strip()
                if sku_key:
                    sku_key_clean = sku_key.lower()
                    excel_rows_by_sku.setdefault(sku_key_clean, []).append(r)
                    
            all_skus = set(excel_rows_by_sku.keys()).union(set(odoo_lines_by_sku.keys()))
            
            for sku in all_skus:
                e_list = excel_rows_by_sku.get(sku, [])
                o_list = odoo_lines_by_sku.get(sku, [])
                
                for i in range(max(len(e_list), len(o_list))):
                    if i < len(e_list) and i < len(o_list):
                        e_row = e_list[i]
                        ml = o_list[i]
                        
                        val_row = {
                            'index': e_row.get('index', 0),
                            'original_row': e_row.get('original_row', []),
                            'data': dict(e_row.get('data', {})),
                            'excluded': e_row.get('excluded', False),
                            'errors': [],
                            'warnings': [],
                            'picking_id': pick_odoo.id,
                            'picking_name': pick_odoo.name,
                            'picking_state': pick_odoo.state,
                            'product_id': ml.product_id.id,
                            'location_id': False,
                            'picker_id': False,
                            'not_in_excel': False,
                            'odoo_data': {
                                'move_line_id': ml.id,
                                'location_name': ml.location_id.barcode or ml.location_id.name or '',
                                'location_id': ml.location_id.id,
                                'quantity': ml.quantity,
                                'product_id': ml.product_id.id
                            }
                        }
                        
                        self._validate_picker_in_row(val_row, user_maps=user_maps)
                        if not val_row['data'].get('Oleada'):
                            val_row['errors'].append({'field': 'Oleada', 'code': 'missing', 'message': 'El campo Oleada es obligatorio.'})
                        self._validate_location_and_stock(val_row, location_product_stock, ml=ml, pick_odoo=pick_odoo, loc_maps=loc_maps)
                        self._validate_units_in_row(val_row)
                        validated_rows.append(val_row)
                        
                    elif i < len(e_list):
                        e_row = e_list[i]
                        
                        val_row = {
                            'index': e_row.get('index', 0),
                            'original_row': e_row.get('original_row', []),
                            'data': dict(e_row.get('data', {})),
                            'excluded': e_row.get('excluded', False),
                            'errors': [],
                            'warnings': [{'field': 'PosicionN1', 'code': 'no_match', 'message': 'Esta línea de Excel no tiene una línea de reserva correspondiente en Odoo.'}],
                            'picking_id': pick_odoo.id,
                            'picking_name': pick_odoo.name,
                            'picking_state': pick_odoo.state,
                            'product_id': False,
                            'location_id': False,
                            'picker_id': False,
                            'not_in_excel': False
                        }
                        
                        self._validate_picker_in_row(val_row, user_maps=user_maps)
                        if not val_row['data'].get('Oleada'):
                            val_row['errors'].append({'field': 'Oleada', 'code': 'missing', 'message': 'El campo Oleada es obligatorio.'})
                            
                        prod_sku = val_row['data'].get('SKU', '')
                        prod = product_map.get(prod_sku.strip().lower())
                            
                        if not prod:
                            val_row['errors'].append({'field': 'SKU', 'code': 'not_found', 'message': f'El producto/SKU "{prod_sku}" no existe.'})
                        else:
                            val_row['product_id'] = prod.id
                            val_row['data']['SKU'] = prod.default_code
                            
                            move = pick_odoo.move_ids.filtered(lambda m: m.product_id.id == prod.id)[:1]
                            if not move:
                                val_row['errors'].append({'field': 'SKU', 'code': 'not_in_pick', 'message': f'El producto "{prod.display_name}" no forma parte del pick {pick_odoo.name}.'})
                            else:
                                self._validate_location_and_stock(val_row, location_product_stock, prod=prod, pick_odoo=pick_odoo, loc_maps=loc_maps)
                                
                        self._validate_units_in_row(val_row)
                        validated_rows.append(val_row)
                        
                    else:
                        ml = o_list[i]
                        
                        existing_v_row = next((vr for vr in group_virtual if vr.get('odoo_data', {}).get('move_line_id') == ml.id), None)
                        
                        default_oleada = ''
                        default_picker_name = ''
                        default_picker_id = ''
                        default_orden_pick = '9999'
                        if group_excel:
                            default_oleada = next((r['data'].get('Oleada') for r in group_excel if r['data'].get('Oleada')), '')
                            default_picker_name = next((r['data'].get('Picker') for r in group_excel if r['data'].get('Picker')), '')
                            default_picker_id = next((r['data'].get('picker_id') for r in group_excel if r['data'].get('picker_id')), '')
                            default_orden_pick = next((r['data'].get('OrdenPick') for r in group_excel if r['data'].get('OrdenPick')), '9999')
                            
                        val_row = {
                            'index': existing_v_row.get('index') if existing_v_row else 10000 + ml.id,
                            'original_row': [],
                            'data': {
                                'SO': so.name,
                                'Oleada': existing_v_row['data'].get('Oleada') if existing_v_row else default_oleada,
                                'Picker': existing_v_row['data'].get('Picker') if existing_v_row else default_picker_name,
                                'picker_id': existing_v_row['data'].get('picker_id') if existing_v_row else default_picker_id,
                                'PosicionN1': ml.location_id.barcode or ml.location_id.name or '',
                                'posicion_N1_id': str(ml.location_id.id),
                                'SKU': ml.product_id.default_code or ml.product_id.barcode or '',
                                'Unidades': str(ml.quantity),
                                'OrdenPick': existing_v_row['data'].get('OrdenPick') if existing_v_row else default_orden_pick
                            },
                            'excluded': existing_v_row.get('excluded', False) if existing_v_row else False,
                            'errors': [],
                            'warnings': [{'field': 'PosicionN1', 'code': 'not_in_excel', 'message': 'No contemplado en el Excel. Se mantiene la reserva de Odoo.'}],
                            'picking_id': pick_odoo.id,
                            'picking_name': pick_odoo.name,
                            'picking_state': pick_odoo.state,
                            'product_id': ml.product_id.id,
                            'location_id': ml.location_id.id,
                            'picker_id': False,
                            'not_in_excel': True,
                            'odoo_data': {
                                'move_line_id': ml.id,
                                'location_name': ml.location_id.barcode or ml.location_id.name or '',
                                'location_id': ml.location_id.id,
                                'quantity': ml.quantity,
                                'product_id': ml.product_id.id
                            }
                        }
                        
                        self._validate_picker_in_row(val_row, user_maps=user_maps)
                        if not val_row['data'].get('Oleada'):
                            val_row['errors'].append({'field': 'Oleada', 'code': 'missing', 'message': 'El campo Oleada es obligatorio.'})
                        self._validate_units_in_row(val_row)
                        validated_rows.append(val_row)
                        
        validated_rows.sort(key=lambda x: x.get('index', 0))
        return validated_rows

    @http.route('/wmds/v2/import_picks/validate_file', type='http', auth='user', methods=['POST'], csrf=False)
    def validate_file(self, **post):
        file = post.get('file')
        has_header_str = post.get('has_header', 'false')
        has_header = has_header_str.lower() == 'true'
        column_mapping_str = post.get('column_mapping')
        
        if not file:
            return request.make_response(json.dumps({'error': True, 'error_msg': 'No se cargó ningún archivo.'}), headers=[('Content-Type', 'application/json')])
        
        filename = file.filename or ''
        ext = filename.split('.')[-1].lower() if '.' in filename else ''
        if ext not in ['csv', 'xlsx', 'xls']:
            return request.make_response(json.dumps({'error': True, 'error_msg': 'Formato de archivo no soportado. Debe ser CSV o XLSX.'}), headers=[('Content-Type', 'application/json')])
            
        file_content = file.read()
        if len(file_content) > 1024 * 1024 * 1024: # 1 GB
            return request.make_response(json.dumps({'error': True, 'error_msg': 'El archivo excede el tamaño máximo permitido de 1 GB.'}), headers=[('Content-Type', 'application/json')])
        
        # Parse rows using Polars
        try:
            if ext == 'csv':
                try:
                    df = pl.read_csv(io.BytesIO(file_content), has_header=has_header)
                except Exception as csv_err:
                    try:
                        df = pl.read_csv(io.BytesIO(file_content), has_header=has_header, encoding='latin1')
                    except Exception:
                        raise csv_err
            else:
                df = pl.read_excel(io.BytesIO(file_content), has_header=has_header)
        except Exception as e:
            return request.make_response(json.dumps({'error': True, 'error_msg': f'Error al leer el archivo con Polars: {str(e)}'}), headers=[('Content-Type', 'application/json')])

        # Clean/Format rows
        if has_header:
            headers = [str(col).strip() for col in df.columns]
        else:
            headers = [f"Columna {i+1}" for i in range(len(df.columns))]
            
        data_rows = []
        for row in df.rows():
            data_rows.append([str(val).strip() if val is not None else '' for val in row])
        
        # Filter out empty rows
        data_rows = [r for r in data_rows if any(val.strip() for val in r)]
        if not data_rows:
            return request.make_response(json.dumps({'error': True, 'error_msg': 'El archivo está vacío.'}), headers=[('Content-Type', 'application/json')])
        
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
        if column_mapping_str:
            try:
                auto_mapping = json.loads(column_mapping_str)
            except Exception:
                pass
                
        if not auto_mapping and has_header:
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
                        
        raw_rows = []
        for row_idx, row in enumerate(data_rows):
            row_data = {}
            for key in ['SO', 'Oleada', 'Picker', 'picker_id', 'PosicionN1', 'posicion_N1_id', 'SKU', 'Unidades', 'OrdenPick']:
                col_idx = auto_mapping.get(key)
                if col_idx is not None and int(col_idx) < len(row):
                    val = str(row[int(col_idx)]).strip()
                    row_data[key] = val
                else:
                    row_data[key] = ''
            
            raw_rows.append({
                'index': row_idx,
                'original_row': row,
                'data': row_data,
                'excluded': False,
                'not_in_excel': False
            })
            
        mapped_results = self._validate_and_match_rows(raw_rows)
            
        result = {
            'status': 'ok',
            'headers': headers,
            'mapping': auto_mapping,
            'rows': mapped_results
        }
        return request.make_response(json.dumps(result), headers=[('Content-Type', 'application/json')])

    @http.route('/wmds/v2/import_picks/validate_rows', type='json', auth='user', methods=['POST'], csrf=True)
    def validate_rows(self, **kw):
        rows = kw.get('rows', [])
        if not rows:
            return {'status': 'ok', 'rows': []}
            
        validated_rows = []
        for row in rows:
            if row.get('excluded', False):
                row['errors'] = []
                row['warnings'] = []
                validated_rows.append(row)
                continue
                
            row_data = row.get('data', {})
            index = row.get('index', 0)
            original_row = row.get('original_row', [])
            
            validated_row = self._validate_row_data(row_data, index, original_row)
            validated_rows.append(validated_row)
            
        return {
            'status': 'ok',
            'rows': validated_rows
        }

    @http.route('/wmds/v2/import_picks/process', type='json', auth='user', methods=['POST'], csrf=True)
    def process_import(self, **kw):
        rows = kw.get('rows', [])
        if not rows:
            return {'error': True, 'error_msg': 'No hay datos para procesar.'}
            
        # 1. Re-validate all rows to ensure we have the latest errors/warnings and IDs using the bulk match.
        raw_rows = []
        for row in rows:
            raw_rows.append({
                'index': row.get('index', 0),
                'original_row': row.get('original_row', []),
                'data': row.get('data', {}),
                'excluded': row.get('excluded', False),
                'not_in_excel': row.get('not_in_excel', False)
            })
        validated_rows = self._validate_and_match_rows(raw_rows)

        picks_data = {}
        picking_to_batch = {}
        picking_to_loc = {}
        picking_to_operator = {}
        
        for row in validated_rows:
            if row.get('excluded', False) or row.get('errors'):
                continue
                
            data = row.get('data', {})
            so_name = data.get('SO')
            oleada = data.get('Oleada')
            picker_name = data.get('Picker')
            posicion = data.get('PosicionN1')
            sku = data.get('SKU')
            unidades_str = data.get('Unidades')
            orden_pick_str = data.get('OrdenPick')
            
            if not so_name or not oleada:
                continue
                
            # Check if there is any warning about the location that requires fallback
            use_odoo_fallback = False
            for warn in row.get('warnings', []):
                if warn.get('field') == 'PosicionN1' and warn.get('code') in ['not_found', 'blocked', 'no_stock']:
                    use_odoo_fallback = True
                    break
                
            if so_name not in picks_data:
                picks_data[so_name] = {
                    'so_name': so_name,
                    'oleada': oleada,
                    'picker_name': picker_name,
                    'orden_pick': self._safe_int(orden_pick_str),
                    'items': []
                }
            
            if posicion and sku:
                picks_data[so_name]['items'].append({
                    'posicion': posicion,
                    'sku': sku,
                    'unidades': float(unidades_str) if unidades_str else None,
                    'use_odoo_fallback': use_odoo_fallback
                })

        oleadas_batches = {}
        
        try:
            # Pre-collect values for bulk prefetching
            so_names = set(picks_data.keys())
            skus = set()
            loc_names = set()
            picker_names = set()
            for p_info in picks_data.values():
                if p_info['picker_name']:
                    picker_names.add(p_info['picker_name'])
                for item in p_info['items']:
                    if item.get('sku'):
                        skus.add(item['sku'])
                    if item.get('posicion'):
                        loc_names.add(item['posicion'])
                        
            # Execute bulk prefetches
            so_map = self._prefetch_sale_orders(list(so_names))
            product_map = self._prefetch_products(list(skus))
            loc_map_by_id, loc_map_by_barcode, loc_map_by_name = self._prefetch_locations(list(loc_names))
            user_map_by_id, user_map_by_name, user_map_by_login = self._prefetch_users(list(picker_names))
            
            for so_name, p_info in picks_data.items():
                so = so_map.get(so_name.strip().lower())
                if not so:
                    continue
                    
                pick_odoo = so.picking_ids.filtered_domain([
                    ('picking_type_id.name', '=', 'Pick'),
                    ('state', '!=', 'cancel')
                ])[:1]
                
                if not pick_odoo:
                    continue
                
                if p_info['items']:
                    # Only delete/unlink existing move lines for the specific products being modified
                    for item in p_info['items']:
                        if item.get('use_odoo_fallback'):
                            continue
                        sku = item['sku']
                        product = product_map.get(sku.strip().lower())
                        if product:
                            mls = pick_odoo.move_line_ids.filtered(lambda l: l.product_id.id == product.id)
                            if mls:
                                mls.sudo().unlink()
                    
                    # Create the new move lines at the requested locations
                    for item in p_info['items']:
                        if item.get('use_odoo_fallback'):
                            continue
                        sku = item['sku']
                        posicion = item['posicion']
                        unidades = item['unidades']
                        
                        pos_clean = posicion.strip().lower()
                        loc = loc_map_by_barcode.get(pos_clean) or loc_map_by_name.get(pos_clean)
                        if not loc:
                            continue
                            
                        product = product_map.get(sku.strip().lower())
                        if not product:
                            continue
                            
                        move = pick_odoo.move_ids.filtered(lambda m: m.product_id.id == product.id)[:1]
                        if not move:
                            continue
                            
                        qty_to_reserve = unidades if unidades is not None else move.product_uom_qty
                        
                        request.env['stock.move.line'].sudo().create({
                            'picking_id': pick_odoo.id,
                            'move_id': move.id,
                            'product_id': product.id,
                            'product_uom_id': move.product_uom.id,
                            'location_id': loc.id,
                            'location_dest_id': move.location_dest_id.id or pick_odoo.location_dest_id.id,
                            'quantity': qty_to_reserve
                        })
                        
                    pick_odoo.sudo().action_assign()
                    
                # Store location names used
                loc_names_used = []
                for ml in pick_odoo.move_line_ids:
                    if ml.quantity > 0:
                        loc_names_used.append(ml.location_id.barcode or ml.location_id.name or '')
                picking_to_loc[pick_odoo.id] = ", ".join(list(set(filter(None, loc_names_used))))
                
                oleada = p_info['oleada']
                if oleada not in oleadas_batches:
                    oleadas_batches[oleada] = []
                oleadas_batches[oleada].append({
                    'pick': pick_odoo,
                    'orden_pick': p_info['orden_pick'],
                    'picker_name': p_info['picker_name']
                })
                
            created_batches_info = []
            for oleada, picks_list in oleadas_batches.items():
                picks_list.sort(key=lambda x: x['orden_pick'])
                picking_ids = [item['pick'].id for item in picks_list]
                
                picker_user = None
                picker_name = picks_list[0]['picker_name']
                if picker_name:
                    pn_clean = picker_name.strip().lower()
                    picker_user = user_map_by_name.get(pn_clean) or user_map_by_login.get(pn_clean)
                
                batch_vals = {
                    'user_id': request.env.user.id,
                    'picking_ids': [(6, 0, picking_ids)]
                }
                
                new_batch = request.env['stock.picking.batch'].sudo().create(batch_vals)
                new_batch.action_confirm()
                
                op_name = "Sin asignar"
                if picker_user:
                    new_batch.operator = picker_user.id
                    op_name = picker_user.name
                    
                for item in picks_list:
                    pick = item['pick']
                    if picker_user:
                        pick.sudo().write({'operator': picker_user.id})
                    
                    request.env['wmds.log'].sudo().create({
                        'pick': pick.id,
                        'user': request.env.user.id,
                        'log': f"Metido en el batch {new_batch.name} (Confirmado) via importación masiva, asignado al operador {op_name}"
                    })
                    
                    picking_to_batch[pick.id] = new_batch.name
                    picking_to_operator[pick.id] = op_name
                    
                created_batches_info.append({
                    'batch_name': new_batch.name,
                    'batch_id': new_batch.id,
                    'oleada': oleada,
                    'picks_count': len(picks_list)
                })
        except Exception as e:
            # Allow continuing with whatever succeeded
            pass

        # Generate feedback Excel report using xlsxwriter
        output_stream = io.BytesIO()
        workbook = xlsxwriter.Workbook(output_stream, {'in_memory': True})
        worksheet = workbook.add_worksheet('Feedback')
        
        # Styles
        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#1E293B',
            'font_color': '#FFFFFF',
            'border': 1,
            'align': 'center'
        })
        cell_format = workbook.add_format({'border': 1})
        error_format = workbook.add_format({'border': 1, 'font_color': '#DC2626'})
        
        original_headers = kw.get('headers', [])
        if not original_headers:
            max_col = max(len(row.get('original_row', [])) for row in validated_rows) if validated_rows else 0
            original_headers = [f"Columna {i+1}" for i in range(max_col)]
            
        new_headers = original_headers + ['Ok', 'Batch', 'Ubicación', 'Operador']
        for col_idx, h_text in enumerate(new_headers):
            worksheet.write(0, col_idx, h_text, header_format)
            
        for row_idx, row in enumerate(validated_rows):
            excel_row_num = row_idx + 1
            orig_row = row.get('original_row', [])
            
            # Write original row columns
            for col_idx, val in enumerate(orig_row):
                worksheet.write(excel_row_num, col_idx, val, cell_format)
                
            is_excluded = row.get('excluded', False)
            errors = row.get('errors', [])
            
            # Col Ok
            if is_excluded:
                ok_val = "Excluido"
                fmt = cell_format
            elif errors:
                ok_val = ", ".join([err.get('message', '') for err in errors])
                fmt = error_format
            else:
                ok_val = "✅"
                fmt = cell_format
                
            # Col Batch, Location, Operator
            pick_id = row.get('picking_id')
            batch_val = ""
            loc_val = ""
            op_val = ""
            
            if not is_excluded and not errors and pick_id:
                batch_val = picking_to_batch.get(pick_id, "")
                loc_val = picking_to_loc.get(pick_id, row.get('data', {}).get('PosicionN1', ''))
                op_val = picking_to_operator.get(pick_id, row.get('data', {}).get('Picker', ''))
            
            worksheet.write(excel_row_num, len(orig_row), ok_val, fmt)
            worksheet.write(excel_row_num, len(orig_row) + 1, batch_val, cell_format)
            worksheet.write(excel_row_num, len(orig_row) + 2, loc_val, cell_format)
            worksheet.write(excel_row_num, len(orig_row) + 3, op_val, cell_format)
            
        workbook.close()
        output_stream.seek(0)
        xlsx_data = output_stream.read()
        xlsx_base64 = base64.b64encode(xlsx_data).decode('utf-8')
        
        had_errors = any(len(r.get('errors', [])) > 0 for r in validated_rows if not r.get('excluded'))
        
        return {
            'status': 'ok',
            'message': 'Procesamiento completado.',
            'xlsx_file': xlsx_base64,
            'filename': 'retroalimentacion_picks.xlsx',
            'had_errors': had_errors
        }

    @http.route('/wmds/v2/picking/unreserve_and_reserve', type='json', auth='user', methods=['POST'], csrf=True)
    def unreserve_and_reserve(self, **kw):
        picking_id = kw.get('picking_id')
        sku = kw.get('sku')
        posicion = kw.get('posicion')
        unidades_str = kw.get('unidades')
        
        if not picking_id:
            return {'error': True, 'error_msg': 'ID de pick no especificado.'}
            
        try:
            picking = request.env['stock.picking'].sudo().browse(int(picking_id))
            if not picking.exists():
                return {'error': True, 'error_msg': 'El picking no existe.'}
                
            # If a specific product and location were requested, we try to force-write it!
            forced_success = False
            if sku and posicion:
                prod = request.env['product.product'].sudo().search([('default_code', '=', sku)], limit=1)
                if not prod:
                    prod = request.env['product.product'].sudo().search([('barcode', '=', sku)], limit=1)
                
                loc = request.env['stock.location'].sudo().search([('barcode', '=', posicion)], limit=1)
                if not loc:
                    loc = request.env['stock.location'].sudo().search([('name', '=', posicion)], limit=1)
                    
                if prod and loc and not loc.is_location_blocked():
                    # Delete/unlink ONLY the existing move lines for this specific product to replace them!
                    mls = picking.move_line_ids.filtered(lambda l: l.product_id.id == prod.id)
                    if mls:
                        mls.sudo().unlink()
                        
                    move = picking.move_ids.filtered(lambda m: m.product_id.id == prod.id)[:1]
                    if move:
                        # Check available stock at requested location
                        quant = request.env['stock.quant'].sudo().search([('location_id', '=', loc.id), ('product_id', '=', prod.id)], limit=1)
                        avail_stock = quant.quantity - quant.reserved_quantity if quant else 0.0
                        
                        units = float(unidades_str) if unidades_str else move.product_uom_qty
                        
                        if avail_stock >= units:
                            # Force create new move line at target location
                            request.env['stock.move.line'].sudo().create({
                                'picking_id': picking.id,
                                'move_id': move.id,
                                'product_id': prod.id,
                                'product_uom_id': move.product_uom.id,
                                'location_id': loc.id,
                                'location_dest_id': move.location_dest_id.id or picking.location_dest_id.id,
                                'quantity': units
                            })
                            picking.sudo().action_assign()
                            forced_success = True
            
            if not forced_success:
                # If we couldn't force it (no stock), unlink mismatching lines for the product
                # and let Odoo standard reservation handle it automatically
                if sku:
                    prod = request.env['product.product'].sudo().search([('default_code', '=', sku)], limit=1)
                    if not prod:
                        prod = request.env['product.product'].sudo().search([('barcode', '=', sku)], limit=1)
                    if prod:
                        mls = picking.move_line_ids.filtered(lambda l: l.product_id.id == prod.id)
                        if mls:
                            mls.sudo().unlink()
                else:
                    picking.sudo().do_unreserve()
                picking.sudo().action_assign()
            
            # Find active source location barcodes/names mapped by product default_code
            reservations = {}
            for ml in picking.move_line_ids:
                if ml.product_id and ml.quantity > 0:
                    sku_code = ml.product_id.default_code
                    loc_name = ml.location_id.barcode or ml.location_id.name
                    if sku_code:
                        reservations[sku_code] = loc_name
                        
            return {
                'status': 'ok', 
                'picking_state': picking.state,
                'reservations': reservations,
                'forced_success': forced_success
            }
        except Exception as e:
            return {'error': True, 'error_msg': f'Error de Odoo: {str(e)}'}
