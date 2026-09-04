# -*- coding: utf-8 -*-
"""
Script para Odoo Shell: Importación masiva de Rackeos (STOR)
============================================================
Permite procesar texto copiado/pegado de hojas de cálculo con las columnas:
PO, SKU, UBICACIÓN, PZS

Uso dentro de odoo-bin shell:
-----------------------------
>>> from odoo.addons.wmds.scripts.rackeo_import_shell import process_rackeo_text
>>> raw_text = '''
PO	SKU	UBICACIÓN	PZS
PO00056	BIFIPRO-8	S-P3-F2-N3	16
PO00056	BIFIPRO-8	S-P3-F1-N3	16
PO00056	BIFISPIN1	D-P11-F2-N3	24
'''
>>> process_rackeo_text(raw_text, env)
"""

import re
import logging

_logger = logging.getLogger(__name__)

def _normalize_code(code):
    if not code:
        return ""
    return re.sub(r'[^A-Za-z0-9]', '', str(code)).lower()

def _safe_float(val, default=0.0):
    if val is None or val == '':
        return default
    try:
        return float(str(val).strip().replace(',', ''))
    except (ValueError, TypeError):
        return default

def _format_qty(val):
    if val is None or val == '':
        return ''
    try:
        q_float = float(str(val).strip().replace(',', ''))
        if q_float.is_integer():
            return str(int(q_float))
        return str(q_float)
    except (ValueError, TypeError):
        return str(val)

def parse_rackeo_text(raw_text):
    """
    Parsea y sanitiza texto crudo delimitado por tabulaciones, comas, punto y coma o espacios.
    Retorna una lista de diccionarios: [{'PO': ..., 'SKU': ..., 'UBICACION': ..., 'PZS': ...}]
    """
    if not raw_text or not raw_text.strip():
        return []

    lines = [l.strip() for l in raw_text.strip().splitlines() if l.strip()]
    if not lines:
        return []

    parsed_rows = []
    
    # Detect delimiter on first line
    header_line = lines[0]
    is_header = False
    
    # Check if first line is header
    header_clean = header_line.lower()
    if 'po' in header_clean or 'sku' in header_clean or 'ubicacion' in header_clean or 'ubicación' in header_clean:
        is_header = True
        data_lines = lines[1:]
    else:
        data_lines = lines

    for line_idx, line in enumerate(data_lines, start=2 if is_header else 1):
        if not line:
            continue
            
        # Split by tab, semicolon, comma or multiple spaces
        if '\t' in line:
            parts = [p.strip() for p in line.split('\t')]
        elif ';' in line:
            parts = [p.strip() for p in line.split(';')]
        elif ',' in line:
            parts = [p.strip() for p in line.split(',')]
        else:
            parts = [p.strip() for p in re.split(r'\s{2,}', line)]
            
        if len(parts) < 4:
            # Fallback single space split if 4 tokens
            space_parts = line.split()
            if len(space_parts) >= 4:
                parts = space_parts[:4]
            else:
                _logger.warning(f"Línea {line_idx} ignorada (menos de 4 columnas): '{line}'")
                continue

        po_val = parts[0].strip()
        sku_val = parts[1].strip()
        loc_val = parts[2].strip()
        pzs_val = parts[3].strip()

        # Skip if header repeated
        if po_val.lower() in ('po', 'purchase order', 'orden') and sku_val.lower() in ('sku', 'producto'):
            continue

        parsed_rows.append({
            'line_num': line_idx,
            'PO': po_val,
            'SKU': sku_val,
            'UBICACION': loc_val,
            'PZS': _safe_float(pzs_val),
            'raw_pzs': pzs_val
        })

    return parsed_rows

def _has_bom(product, env):
    if not product:
        return False
    if hasattr(product, 'bom_count') and product.bom_count > 0:
        return True
    if hasattr(product, 'bom_ids') and bool(product.bom_ids):
        return True
    if hasattr(product, 'product_tmpl_id') and hasattr(product.product_tmpl_id, 'bom_ids') and bool(product.product_tmpl_id.bom_ids):
        return True
    if 'mrp.bom' in env:
        bom_exists = env['mrp.bom'].sudo().search_count([
            '|', ('product_id', '=', product.id), ('product_tmpl_id', '=', product.product_tmpl_id.id)
        ])
        if bom_exists > 0:
            return True
    return False

def process_rackeo_text(raw_text, env=None, commit=True):
    """
    Procesa el texto de rackeo dentro del entorno de Odoo:
    1. Sanitiza y valida las líneas.
    2. Agrupa por Purchase Order (PO).
    3. Desreserva STORs abiertos previos de la PO.
    4. Valida disponibilidad en WH/Recepcion.
    5. Valida ubicaciones destino (existencia, bloqueo, regla N1 vs vacía).
    6. Crea y valida el nuevo STOR (WH/Recepcion -> WH/Stock) con sus líneas exactas y purchase_id.
    7. Registra en wmds.log con usuario y mención de automatización.
    8. Imprime y retorna resumen de ejecución.
    """
    if env is None:
        try:
            from odoo.http import request
            env = request.env
        except Exception:
            raise RuntimeError("Se requiere pasar el 'env' de Odoo a process_rackeo_text(raw_text, env).")

    rows = parse_rackeo_text(raw_text)
    if not rows:
        print("⚠️ No se encontraron filas de datos válidas en el texto proporcionado.")
        return {'status': 'error', 'message': 'No hay filas para procesar.'}

    print(f"\n========================================================")
    print(f"📦 INICIANDO IMPORTACIÓN MASIVA DE RACKEO ({len(rows)} FILAS)")
    print(f"========================================================\n")

    # Pre-fetch locations, products and POs
    po_names = list(set(r['PO'] for r in rows if r['PO']))
    skus = list(set(r['SKU'] for r in rows if r['SKU']))
    loc_names = list(set(r['UBICACION'] for r in rows if r['UBICACION']))

    # 1. POs (Strict exact match)
    po_map = {}
    for po_name in po_names:
        po = env['purchase.order'].sudo().search([('name', '=ilike', po_name.strip())], limit=1)
        if po:
            po_map[po_name.lower()] = po
            po_map[po.name.lower()] = po

    # 2. Products
    product_map = {}
    products = env['product.product'].sudo().search(['|', ('default_code', 'in', skus), ('barcode', 'in', skus)])
    for p in products:
        if p.default_code:
            product_map[p.default_code.lower()] = p
            product_map[_normalize_code(p.default_code)] = p
        if p.barcode:
            product_map[p.barcode.lower()] = p
            product_map[_normalize_code(p.barcode)] = p

    for sku in skus:
        norm_sku = _normalize_code(sku)
        if sku.lower() not in product_map and norm_sku not in product_map:
            p_found = env['product.product'].sudo().search(['|', ('default_code', '=ilike', sku), ('barcode', '=ilike', sku)], limit=1)
            if not p_found:
                tokens = re.findall(r'[A-Za-z]+|\d+', sku)
                if tokens:
                    pattern = '%'.join(tokens)
                    candidates = env['product.product'].sudo().search(['|', ('default_code', 'ilike', pattern), ('barcode', 'ilike', pattern)], limit=10)
                    for cand in candidates:
                        if _normalize_code(cand.default_code) == norm_sku or _normalize_code(cand.barcode) == norm_sku:
                            p_found = cand
                            break
                    if not p_found and candidates:
                        p_found = candidates[0]
            if p_found:
                product_map[sku.lower()] = p_found
                product_map[norm_sku] = p_found
                if p_found.default_code:
                    product_map[p_found.default_code.lower()] = p_found
                if p_found.barcode:
                    product_map[p_found.barcode.lower()] = p_found

    # 3. Locations
    loc_map = {}
    locations = env['stock.location'].sudo().search(['|', ('barcode', 'in', loc_names), '|', ('name', 'in', loc_names), ('complete_name', 'in', loc_names)])
    for l in locations:
        if l.barcode:
            loc_map[l.barcode.lower()] = l
        if l.name:
            loc_map[l.name.lower()] = l
        if l.complete_name:
            loc_map[l.complete_name.lower()] = l

    for ln in loc_names:
        if ln.lower() not in loc_map:
            l_found = env['stock.location'].sudo().search(['|', ('barcode', '=ilike', ln), '|', ('name', '=ilike', ln), ('complete_name', '=ilike', ln)], limit=1)
            if l_found:
                loc_map[ln.lower()] = l_found

    # Picking type & locations
    pt_stor = env['stock.picking.type'].sudo().search([('sequence_code', '=', 'STOR')], limit=1)
    if not pt_stor:
        print("❌ Error crítico: No se encontró el tipo de operación STOR (Storage) en Odoo.")
        return {'status': 'error', 'message': 'Tipo de operación STOR no encontrado.'}

    rec_loc = pt_stor.default_location_src_id or env['stock.location'].sudo().search([('complete_name', '=', 'WH/Recepcion')], limit=1)
    dest_stock = pt_stor.default_location_dest_id or env['stock.location'].sudo().search([('complete_name', '=', 'WH/Stock')], limit=1)

    # Group rows by PO
    rows_by_po = {}
    for r in rows:
        rows_by_po.setdefault(r['PO'], []).append(r)

    results = []

    for po_name, po_rows in rows_by_po.items():
        print(f"\n▶ Procesando Orden de Compra: {po_name} ({len(po_rows)} líneas)")
        print("-" * 50)

        po = po_map.get(po_name.lower())
        if not po:
            msg = f"❌ PO '{po_name}' no existe en Odoo."
            print(f"  {msg}")
            results.append({'po': po_name, 'status': 'error', 'message': msg})
            continue

        # Check line validity
        po_has_errors = False
        parsed_items = []
        for r in po_rows:
            sku = r['SKU']
            loc_str = r['UBICACION']
            pzs = r['PZS']
            line_no = r['line_num']

            prod = product_map.get(sku.lower()) or product_map.get(_normalize_code(sku))
            if not prod:
                print(f"  ❌ Línea {line_no}: SKU '{sku}' no existe en el catálogo.")
                po_has_errors = True
                continue

            if _has_bom(prod, env):
                print(f"  ❌ Línea {line_no}: SKU '{prod.default_code or sku}' es un producto padre con lista de materiales (combo/multicaja). No se puede rackear directamente.")
                po_has_errors = True
                continue

            loc = loc_map.get(loc_str.lower())
            if not loc:
                print(f"  ❌ Línea {line_no}: Ubicación '{loc_str}' no existe en Odoo.")
                po_has_errors = True
                continue

            if hasattr(loc, 'is_location_blocked') and loc.is_location_blocked():
                print(f"  ❌ Línea {line_no}: Ubicación '{loc.complete_name}' está bloqueada ({loc.block_reason or 'Sin motivo'}).")
                po_has_errors = True
                continue

            # Occupancy check
            loc_quants = env['stock.quant'].sudo().search([('location_id', '=', loc.id), ('quantity', '>', 0)])
            if loc_quants:
                is_n1 = loc.name and loc.name.upper().endswith('N1')
                if is_n1:
                    other_prods = loc_quants.filtered(lambda q: q.product_id.id != prod.id)
                    if other_prods:
                        print(f"  ❌ Línea {line_no}: Ubicación N1 '{loc.name}' ocupada por SKU diferente ({other_prods[0].product_id.default_code}).")
                        po_has_errors = True
                        continue
                else:
                    print(f"  ❌ Línea {line_no}: Ubicación '{loc.complete_name}' no está vacía (contiene {loc_quants[0].product_id.default_code}: {loc_quants[0].quantity} pzs).")
                    po_has_errors = True
                    continue

            if pzs <= 0:
                print(f"  ❌ Línea {line_no}: Cantidad inválida ({pzs}).")
                po_has_errors = True
                continue

            parsed_items.append({
                'product': prod,
                'location': loc,
                'pzs': pzs,
                'line_num': line_no
            })

        if po_has_errors:
            print(f"  ❌ Cancelando procesamiento de PO {po_name} debido a errores en las líneas.")
            results.append({'po': po_name, 'status': 'error', 'message': 'Errores de validación en líneas.'})
            continue

        # Check Reservoir in WH/Recepcion (and unreserve open STORs)
        open_stors = env['stock.picking'].sudo().search([
            ('origin', '=', po.name),
            ('picking_type_id.sequence_code', '=', 'STOR'),
            ('state', 'not in', ('done', 'cancel'))
        ])
        
        if open_stors:
            print(f"  ℹ️ Cancelando reservas y poniendo demanda a 0 en {len(open_stors)} STOR(s) original(es) ({', '.join(open_stors.mapped('name'))})...")
            for s in open_stors:
                s.do_unreserve()
                for m in s.move_ids:
                    if m.state not in ('done', 'cancel'):
                        m.write({'product_uom_qty': 0.0})
                        m._action_cancel()
                s.action_cancel()

        # Check total requested vs available in WH/Recepcion
        items_by_prod = {}
        for item in parsed_items:
            items_by_prod.setdefault(item['product'], []).append(item)

        reservoir_ok = True
        for prod, p_items in items_by_prod.items():
            total_req = sum(it['pzs'] for it in p_items)
            quants = env['stock.quant'].sudo().search([('location_id', '=', rec_loc.id), ('product_id', '=', prod.id)])
            total_rec = sum(quants.mapped('quantity'))
            
            if total_rec < total_req:
                print(f"  ❌ Falta de reserva de producto en WH/Recepcion para SKU {prod.default_code}:")
                print(f"     Requerido: {total_req} pzs | Disponible en recepción: {total_rec} pzs")
                reservoir_ok = False

        if not reservoir_ok:
            results.append({'po': po_name, 'status': 'error', 'message': 'Falta de reserva de producto en WH/Recepcion.'})
            continue

        # Create new STOR picking
        try:
            new_stor = env['stock.picking'].sudo().create({
                'picking_type_id': pt_stor.id,
                'location_id': rec_loc.id,
                'location_dest_id': dest_stock.id,
                'origin': po.name,
                'purchase_id': po.id,
                'user_id': env.user.id,
            })

            created_moves = {}
            for prod, p_items in items_by_prod.items():
                total_prod_qty = sum(it['pzs'] for it in p_items)
                move = env['stock.move'].sudo().create({
                    'name': f"STOR: {prod.display_name}",
                    'product_id': prod.id,
                    'product_uom_qty': total_prod_qty,
                    'product_uom': prod.uom_id.id,
                    'picking_id': new_stor.id,
                    'location_id': rec_loc.id,
                    'location_dest_id': dest_stock.id,
                })
                created_moves[prod.id] = move

            new_stor.action_confirm()
            if new_stor.move_line_ids:
                new_stor.move_line_ids.unlink()

            for item in parsed_items:
                prod = item['product']
                move = created_moves[prod.id]
                env['stock.move.line'].sudo().create({
                    'picking_id': new_stor.id,
                    'move_id': move.id,
                    'product_id': prod.id,
                    'product_uom_id': prod.uom_id.id,
                    'location_id': rec_loc.id,
                    'location_dest_id': item['location'].id,
                    'quantity': item['pzs'],
                })

            new_stor.button_validate()

            # WMDS logs
            total_pzs = sum(it['pzs'] for it in parsed_items)
            user_name = env.user.name or f"Usuario #{env.user.id}"
            log_msg = f"Rackeo masivo realizado por automatización por {user_name}: {new_stor.name} ({len(parsed_items)} líneas, {total_pzs} pzs) para PO {po.name}."
            env['wmds.log'].sudo().create({
                'purchase': po.id,
                'pick': new_stor.id,
                'log': log_msg,
                'user': env.user.id,
            })

            print(f"  ✅ CREADO Y VALIDADO EXITOSAMENTE: {new_stor.name}")
            print(f"     Estado: {new_stor.state.upper()} | Total Líneas: {len(parsed_items)} | Total Pzs: {total_pzs}")
            for item in parsed_items:
                print(f"       • SKU: {item['product'].default_code:<15} -> Ubicación: {item['location'].barcode or item['location'].name:<15} ({_format_qty(item['pzs'])} pzs)")

            results.append({
                'po': po.name,
                'status': 'ok',
                'stor_name': new_stor.name,
                'stor_id': new_stor.id,
                'lines_count': len(parsed_items),
                'total_pzs': total_pzs
            })

        except Exception as e:
            msg = f"Error al crear/validar STOR: {str(e)}"
            print(f"  ❌ {msg}")
            results.append({'po': po.name, 'status': 'error', 'message': msg})

    print(f"\n========================================================")
    print(f"🏁 RESUMEN FINAL:")
    success_count = sum(1 for r in results if r['status'] == 'ok')
    print(f"   • POs exitosas: {success_count} de {len(rows_by_po)}")
    for r in results:
        if r['status'] == 'ok':
            print(f"   ✅ PO {r['po']}: {r['stor_name']} ({r['total_pzs']} pzs)")
        else:
            print(f"   ❌ PO {r['po']}: {r.get('message', 'Error')}")
    print(f"========================================================\n")

    return results

if __name__ == '__main__':
    # Interactive mode if executed directly
    print("Pegue el contenido del Excel y presione Ctrl+D (o Ctrl+Z en Windows) al finalizar:")
    import sys
    try:
        input_data = sys.stdin.read()
        if input_data.strip():
            # If running in standalone python environment with odoo configured
            try:
                import odoo
                odoo.tools.config.parse_config(['--config=/src/odoo.conf', '-d', 'admin'])
                registry = odoo.registry('admin')
                with registry.cursor() as cr:
                    env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})
                    process_rackeo_text(input_data, env)
            except Exception as ex:
                print(f"Ejecute este script dentro de odoo shell: python3 /odoo/odoo-bin shell ...\nError: {ex}")
    except KeyboardInterrupt:
        pass
