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
        mapped_row = {
            'index': index,
            'original_row': original_row,
            'data': row_data,
            'excluded': False,
            'errors': [],
            'warnings': [],
            'picking_id': False,
            'picking_name': '',
            'picking_state': '',
            'product_id': False,
            'location_id': False,
            'picker_id': False
        }
        
        so_name = row_data.get('SO')
        oleada = row_data.get('Oleada')
        picker_name = row_data.get('Picker')
        posicion = row_data.get('PosicionN1')
        sku = row_data.get('SKU')
        unidades_str = row_data.get('Unidades')
        
        # Validate SO
        if not so_name:
            mapped_row['errors'].append({'field': 'SO', 'code': 'missing', 'message': 'El campo SO es obligatorio.'})
        else:
            so = request.env['sale.order'].sudo().search([('name', '=', so_name)], limit=1)
            if not so:
                so = request.env['sale.order'].sudo().search([('name', 'ilike', so_name)], limit=1)
            if not so:
                mapped_row['errors'].append({'field': 'SO', 'code': 'not_found', 'message': f'La SO "{so_name}" no existe.'})
            else:
                mapped_row['data']['SO'] = so.name
                if not so.data_ready_to_pick:
                    mapped_row['errors'].append({'field': 'SO', 'code': 'not_ready', 'message': f'La SO "{so.name}" no está lista para recolectar (data_ready_to_pick es falso).'})
                
                pick_odoo = so.picking_ids.filtered_domain([
                    ('picking_type_id.name', '=', 'Pick'),
                    ('state', '!=', 'cancel')
                ])[:1]
                
                if not pick_odoo:
                    mapped_row['errors'].append({'field': 'SO', 'code': 'no_pick', 'message': f'La SO "{so.name}" no tiene un pick de tipo "Pick" válido.'})
                else:
                    mapped_row['picking_id'] = pick_odoo.id
                    mapped_row['picking_name'] = pick_odoo.name
                    mapped_row['picking_state'] = pick_odoo.state
                    
                    # Validate if picking is already in a batch (lote)
                    if pick_odoo.batch_id:
                        mapped_row['errors'].append({
                            'field': 'SO', 
                            'code': 'already_in_batch', 
                            'message': f'El pick {pick_odoo.name} ya pertenece al plan de pickeo (lote) "{pick_odoo.batch_id.name}".'
                        })
                    
                    if pick_odoo.state != 'assigned':
                        mapped_row['warnings'].append({'field': 'SO', 'code': 'not_assigned', 'message': f'El pick {pick_odoo.name} no está en estado disponible (Estado actual: {pick_odoo.state}).'})
        
        # Validate Oleada
        if not oleada:
            mapped_row['errors'].append({'field': 'Oleada', 'code': 'missing', 'message': 'El campo Oleada es obligatorio.'})
        
        # Validate Picker
        if picker_name:
            picker_user = request.env['res.users'].sudo().search([('name', '=', picker_name)], limit=1)
            if not picker_user:
                picker_user = request.env['res.users'].sudo().search([('login', '=', picker_name)], limit=1)
            if not picker_user:
                mapped_row['errors'].append({'field': 'Picker', 'code': 'not_found', 'message': f'El operador/usuario "{picker_name}" no existe.'})
            else:
                mapped_row['picker_id'] = picker_user.id
                mapped_row['data']['Picker'] = picker_user.name
        
        # If all 3 fields (PosicionN1, SKU, Unidades) are empty, we ignore them completely
        # and do not validate or modify stock.move.line.
        if not posicion and not sku and not unidades_str:
            return mapped_row

        # Get actual reservation from Odoo if possible
        actual_loc_name = ""
        if mapped_row['picking_id'] and sku:
            pick_odoo_record = request.env['stock.picking'].sudo().browse(mapped_row['picking_id'])
            prod_record = request.env['product.product'].sudo().search([('default_code', '=', sku)], limit=1)
            if not prod_record:
                prod_record = request.env['product.product'].sudo().search([('barcode', '=', sku)], limit=1)
            if prod_record:
                ml = pick_odoo_record.move_line_ids.filtered(lambda l: l.product_id.id == prod_record.id)[:1]
                if ml:
                    actual_loc_name = ml.location_id.barcode or ml.location_id.name

        # Auto-fill empty position from Odoo's actual reservation
        if not posicion and actual_loc_name:
            mapped_row['data']['PosicionN1'] = actual_loc_name
            posicion = actual_loc_name

        # Validate PosicionN1 and SKU
        if posicion and sku:
            loc = request.env['stock.location'].sudo().search([('barcode', '=', posicion)], limit=1)
            if not loc:
                loc = request.env['stock.location'].sudo().search([('name', '=', posicion)], limit=1)
            
            if not loc:
                if actual_loc_name:
                    mapped_row['warnings'].append({
                        'field': 'PosicionN1', 
                        'code': 'not_found', 
                        'message': f'La ubicación sugerida "{posicion}" no existe. Se usará la ubicación original de Odoo: "{actual_loc_name}".'
                    })
                    mapped_row['data']['PosicionN1'] = actual_loc_name
                else:
                    mapped_row['errors'].append({
                        'field': 'PosicionN1', 
                        'code': 'not_found', 
                        'message': f'La ubicación "{posicion}" no existe.'
                    })
            else:
                mapped_row['location_id'] = loc.id
                mapped_row['data']['PosicionN1'] = loc.barcode or loc.name
                if loc.is_location_blocked():
                    if actual_loc_name:
                        mapped_row['warnings'].append({
                            'field': 'PosicionN1', 
                            'code': 'blocked', 
                            'message': f'La ubicación sugerida "{loc.complete_name}" está bloqueada. Se usará la ubicación original de Odoo: "{actual_loc_name}".'
                        })
                        mapped_row['data']['PosicionN1'] = actual_loc_name
                    else:
                        mapped_row['errors'].append({
                            'field': 'PosicionN1', 
                            'code': 'blocked', 
                            'message': f'La ubicación "{loc.complete_name}" está bloqueada.'
                        })
            
            prod = request.env['product.product'].sudo().search([('default_code', '=', sku)], limit=1)
            if not prod:
                prod = request.env['product.product'].sudo().search([('barcode', '=', sku)], limit=1)
            if not prod:
                mapped_row['errors'].append({'field': 'SKU', 'code': 'not_found', 'message': f'El producto/SKU "{sku}" no existe.'})
            else:
                mapped_row['product_id'] = prod.id
                mapped_row['data']['SKU'] = prod.default_code
                
                if mapped_row['picking_id']:
                    pick_odoo = request.env['stock.picking'].sudo().browse(mapped_row['picking_id'])
                    move = pick_odoo.move_ids.filtered(lambda m: m.product_id.id == prod.id)[:1]
                    if not move:
                        mapped_row['errors'].append({'field': 'SKU', 'code': 'not_in_pick', 'message': f'El producto "{prod.display_name}" no forma parte del pick {pick_odoo.name}.'})
                    else:
                        if loc:
                            quant = request.env['stock.quant'].sudo().search([('location_id', '=', loc.id), ('product_id', '=', prod.id)], limit=1)
                            avail_stock = quant.quantity - quant.reserved_quantity if quant else 0.0
                            units = 0.0
                            if unidades_str:
                                try:
                                    units = float(unidades_str)
                                except ValueError:
                                    pass
                            else:
                                units = move.product_uom_qty
                                
                            if avail_stock < units:
                                if actual_loc_name:
                                    mapped_row['warnings'].append({
                                        'field': 'PosicionN1', 
                                        'code': 'no_stock', 
                                        'message': f'Stock insuficiente en ubicación sugerida (Disponible: {avail_stock}, Requerido: {units}). Se usará la ubicación original de Odoo: "{actual_loc_name}".'
                                    })
                                    mapped_row['data']['PosicionN1'] = actual_loc_name
                                else:
                                    mapped_row['warnings'].append({
                                        'field': 'PosicionN1', 
                                        'code': 'no_stock', 
                                        'message': f'Stock insuficiente en la ubicación (Disponible: {avail_stock}, Requerido: {units}).'
                                    })
        elif (posicion and not sku) or (sku and not posicion):
            mapped_row['errors'].append({'field': 'SKU', 'code': 'partial', 'message': 'Debe proporcionar tanto la Posición como el SKU.'})
        
        # Validate Units
        if unidades_str:
            try:
                u_float = float(unidades_str)
                if u_float <= 0:
                    mapped_row['errors'].append({'field': 'Unidades', 'code': 'invalid', 'message': 'Las unidades deben ser mayores a cero.'})
            except ValueError:
                mapped_row['errors'].append({'field': 'Unidades', 'code': 'invalid', 'message': 'Las unidades deben un número válido.'})
                
        return mapped_row

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
            'PosicionN1': ['posicionn1', 'posicion', 'posicion n1', 'ubicacion', 'ubicación', 'estanteria', 'shelf', 'location', 'ubicación origen'],
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
                        
        mapped_results = []
        for row_idx, row in enumerate(data_rows):
            row_data = {}
            for key in ['SO', 'Oleada', 'Picker', 'PosicionN1', 'SKU', 'Unidades', 'OrdenPick']:
                col_idx = auto_mapping.get(key)
                if col_idx is not None and int(col_idx) < len(row):
                    val = str(row[int(col_idx)]).strip()
                    row_data[key] = val
                else:
                    row_data[key] = ''
            
            mapped_row = self._validate_row_data(row_data, row_idx, row)
            mapped_results.append(mapped_row)
            
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
            
        # 1. Re-validate all rows to ensure we have the latest errors/warnings and IDs.
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
            validated_row['excluded'] = False
            validated_rows.append(validated_row)

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
            for so_name, p_info in picks_data.items():
                so = request.env['sale.order'].sudo().search([('name', '=', so_name)], limit=1)
                if not so:
                    so = request.env['sale.order'].sudo().search([('name', 'ilike', so_name)], limit=1)
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
                        product = request.env['product.product'].sudo().search([('default_code', '=', sku)], limit=1)
                        if not product:
                            product = request.env['product.product'].sudo().search([('barcode', '=', sku)], limit=1)
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
                        
                        loc = request.env['stock.location'].sudo().search([('barcode', '=', posicion)], limit=1)
                        if not loc:
                            loc = request.env['stock.location'].sudo().search([('name', '=', posicion)], limit=1)
                        if not loc:
                            continue
                            
                        product = request.env['product.product'].sudo().search([('default_code', '=', sku)], limit=1)
                        if not product:
                            product = request.env['product.product'].sudo().search([('barcode', '=', sku)], limit=1)
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
                loc_names = []
                for ml in pick_odoo.move_line_ids:
                    if ml.quantity > 0:
                        loc_names.append(ml.location_id.barcode or ml.location_id.name or '')
                picking_to_loc[pick_odoo.id] = ", ".join(list(set(filter(None, loc_names))))
                
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
                    picker_user = request.env['res.users'].sudo().search([('name', '=', picker_name)], limit=1)
                    if not picker_user:
                        picker_user = request.env['res.users'].sudo().search([('login', '=', picker_name)], limit=1)
                
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
