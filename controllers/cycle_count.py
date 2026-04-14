from odoo import http, fields
from odoo.http import request
import logging
import re
import pytz

_logger = logging.getLogger(__name__)

def convert_value_in_label(map_cols, value, key, return_severity=False):
    if not value:
        return "" if not return_severity else None

    for col in map_cols:
        if col.get('field') == key and col.get('type') == 'selectable':
            for option in col.get('options', []):
                if option['value'] == value:
                    if return_severity:
                        return option.get('severity', 'secondary')
                    return option['label']
    return value if not return_severity else None

class CycleCount(http.Controller):

    @http.route('/wmds/v2/engine/get/cycle_counts', type='json', auth='user', methods=['POST'])
    def get_cycle_counts(self, **kw):
        try:
            model = request.env['scheduled.cycle.count'].sudo()
            
            parsed_params = {
                "cur_page": kw.get('page', 1),
                "per_page": kw.get('per_page', 30),
                "sort_by": kw.get('sort_by'),
                "sort_order": kw.get('sort_order'),
            }
            for popped_param in ['page', 'per_page', 'sort_by', 'sort_order']:
                if popped_param in kw:
                    kw.pop(popped_param)

            domain = []
            for key, value in kw.items():
                if value:
                    domain.append((key, 'ilike', value))
            
            order = f"{parsed_params['sort_by']} {parsed_params['sort_order']}" if parsed_params['sort_by'] and parsed_params['sort_order'] else 'id desc'
            limit = parsed_params['per_page']
            offset = (parsed_params['cur_page'] - 1) * parsed_params['per_page']

            counts = model.search(domain, order=order, limit=limit, offset=offset)
            total_count = model.search_count(domain)

            state_options = [
                {'value': 'created', 'label': 'Borrador', 'severity': 'secondary'},
                {'value': 'in_progress', 'label': 'En Progreso', 'severity': 'info'},
                {'value': 'finalized', 'label': 'Finalizado', 'severity': 'success'},
                {'value': 'cancelled', 'label': 'Cancelado', 'severity': 'danger'}
            ]
            default_state = 'in_progress'

            map_cols = [
                {"field": "id", "name": "ID"},
                {"field": "name", "name": "Código"},
                {"field": "notes", "name": "Referencia"},
                {"field": "create_date", "name": "Fecha Creación", "type": "date"},
                {"field": "create_uid", "name": "Creado por"},
                {
                    "field": "state", "name": "Estado", "type": "selectable",
                    "options": state_options,
                    "default": default_state
                }
            ]

            data = []
            for count in counts:
                data.append({
                    "id": count.id,
                    "name": count.name,
                    "notes": count.notes or '',
                    "create_date": count.create_date.strftime('%Y-%m-%d %H:%M') if count.create_date else '',
                    "create_uid": count.create_uid.name if count.create_uid else '',
                    "state": {
                        "label": convert_value_in_label(map_cols, count.state, "state"),
                        "severity": convert_value_in_label(map_cols, count.state, "state", return_severity=True)
                    }
                })

            return {
                "ok": True,
                "map_cols": map_cols,
                "data": data,
                "total_count": total_count
            }
        except Exception as e:
            _logger.error(f"Error fetching cycle counts: {e}")
            return {'ok': False, 'error': str(e)}


    @http.route('/wmds/v2/engine/get/locations_by_range', type='json', auth='user', methods=['POST'])
    def get_locations_by_range(self, **kw):
        try:
            f = {
                'a_from': str(kw.get('aisle_from', 'A')).upper(),
                'a_to': str(kw.get('aisle_to', 'Z')).upper(),
                'p_from': int(kw.get('position_from', 1)),
                'p_to': int(kw.get('position_to', 99)),
                'l_from': int(kw.get('level_from', 1)),
                'l_to': int(kw.get('level_to', 5)),
                'f_from': int(kw.get('front_from', 1)),
                'f_to': int(kw.get('front_to', 2)),
            }

            # Regex to identify the structure and extract parts: [Aisle]-[Position]-[Front]-[Level]
            # Supports 1 or 2 letters for Aisle.
            loc_pattern = re.compile(r"([A-Z]{1,2})-P(\d{2})-F(\d)-N(\d)$", re.IGNORECASE)

            def aisle_to_key(val):
                return (len(val), val)

            def is_location_in_range(complete_name):
                match = loc_pattern.search(complete_name)
                if not match:
                    return False
                
                aisle, pos, front, level = match.groups()
                aisle = aisle.upper()
                pos, front, level = int(pos), int(front), int(level)

                if not (aisle_to_key(f['a_from']) <= aisle_to_key(aisle) <= aisle_to_key(f['a_to'])):
                    return False
                if not (f['p_from'] <= pos <= f['p_to']):
                    return False
                if not (f['f_from'] <= front <= f['f_to']):
                    return False
                if not (f['l_from'] <= level <= f['l_to']):
                    return False
                
                return True
            
            domain = [
                ('complete_name', '=ilike', 'WH%'),
                ('complete_name', 'not ilike', 'Cuarentena'),
                ('usage', '=', 'internal') 
            ]
            all_locs = request.env['stock.location'].sudo().with_context(active_test=True).search(domain, order='complete_name asc')
            
            active_counts = request.env['scheduled.cycle.count'].sudo().search([('state', 'not in', ['finalized', 'cancelled'])])
            active_location_ids = active_counts.mapped('selected_location_ids.location_id.id')
            
            # Apply our advanced range filter
            locations = all_locs.filtered(lambda u: u.id not in active_location_ids and is_location_in_range(u.complete_name))
            
            # Identify locations with active reservations
            reservations = request.env['stock.move.line'].sudo().search([
                ('location_id', 'in', locations.ids),
                ('state', 'not in', ['done', 'cancel']),
                ('quantity', '>', 0)
            ])
            
            res_info_map = {}
            for res in reservations:
                lid = res.location_id.id
                if lid not in res_info_map:
                    res_info_map[lid] = []
                p_name = res.picking_id.name or res.move_id.reference or "Movimiento Interno"
                if p_name not in res_info_map[lid]:
                    res_info_map[lid].append(p_name)

            return {
                'ok': True,
                'locations': [
                    {
                        'id': l.id, 
                        'complete_name': l.complete_name,
                        'has_reservation': l.id in res_info_map,
                        'reservation_info': ", ".join(res_info_map.get(l.id, []))
                    } for l in locations
                ]
            }
        except Exception as e:
            return {'ok': False, 'error': str(e)}

    @http.route('/wmds/v2/engine/create_full_cycle_count', type='json', auth='user', methods=['POST'])
    def create_full_cycle_count(self, **kw):
        try:
            location_ids = [int(lid) for lid in kw.get('location_ids', [])]
            operators = kw.get('operators', [])
            user_notes = kw.get('name')

            if not location_ids or not operators:
                return {'ok': False, 'error': 'Faltan ubicaciones u operadores.'}

            locations = request.env['stock.location'].sudo().browse(location_ids)
            for loc in locations:
                # Check for active reservations
                reservations = request.env['stock.move.line'].sudo().search([
                    ('location_id', '=', loc.id),
                    ('state', 'not in', ['done', 'cancel']),
                    ('quantity', '>', 0)
                ], limit=1)

                if reservations:
                    return {
                        'ok': False, 
                        'error': f"No se puede bloquear la ubicación {loc.complete_name}, tiene una reserva en el movimiento {reservations.picking_id.name or reservations.move_id.reference}. Termine el traslado o anule la reserva."
                    }

            # 2. Crear el maestro
            count_obj = request.env['scheduled.cycle.count'].sudo().create({
                'notes': user_notes,
                'selected_location_ids': [(0, 0, {
                    'location_id': lid,
                }) for lid in location_ids]
            })

            blocked_parent = request.env.ref('wmds.location_blocked').sudo()
            block_reason_text = f"Conteo Cíclico: {count_obj.name}"
            if user_notes:
                block_reason_text += f" ({user_notes})"

            for loc in locations:
                if not loc.original_parent_id:
                    loc.write({
                        'original_parent_id': loc.location_id.id,
                        'location_id': blocked_parent.id,
                        'block_reason': block_reason_text
                    })
                else:
                    # Already has an original parent (maybe from another block), just change parent and reason
                    loc.write({
                        'location_id': blocked_parent.id,
                        'block_reason': block_reason_text
                    })

            # 3. Crear las olas
            for op_id in operators:
                wave_obj = request.env['cycle.count.wave'].sudo().create({
                    'cycle_count_id': count_obj.id,
                    'operator_id': op_id,
                    'state': 'draft'
                })
                # Las líneas de la ola apuntan a la ubicación (que ahora está bloqueada)
                line_vals = [(0, 0, {'stock_location_id': lid}) for lid in location_ids]
                wave_obj.write({'line_ids': line_vals})

            return {'ok': True, 'id': count_obj.id, 'name': count_obj.name}
        except Exception as e:
            _logger.error(f"Error creando ciclo: {str(e)}")
            return {'ok': False, 'error': str(e)}

    @http.route('/wmds/v2/engine/get/cycle_count_details', type='json', auth='user', methods=['POST'])
    def get_cycle_count_details(self, **kw):
        try:
            count = request.env['scheduled.cycle.count'].sudo().with_context(active_test=False).browse(kw.get('count_id'))
            return {
                'ok': True,
                'details': {
                    'state': count.state,
                    'notes': count.notes,
                    'locations': [{'id': l.location_id.id, 'complete_name': l.location_id.complete_name} for l in count.selected_location_ids],
                    'waves': [{
                        'id': w.id,
                        'name': w.name,
                        'operator_name': w.operator_id.name,
                        'state': w.state,
                        'state_label': dict(w._fields['state'].selection).get(w.state)
                    } for w in count.wave_ids]
                }
            }
        except Exception as e:
            return {'ok': False, 'error': str(e)}

    @http.route('/wmds/v2/engine/finish_cycle_count_wave', type='json', auth='user', methods=['POST'])
    def finish_cycle_count_wave(self, **kw):
        try:
            wave = request.env['cycle.count.wave'].sudo().browse(kw.get('wave_id'))
            
            # Validation: All planned locations in this wave must have been counted
            # (at least one line in cycle.count.line for each stock_location_id in wave.line_ids)
            planned_loc_ids = wave.line_ids.mapped('stock_location_id.id')
            counted_loc_ids = request.env['cycle.count.line'].sudo().search([
                ('wave_id', '=', wave.id)
            ]).mapped('stock_location_id.id')
            
            missing_loc_ids = [lid for lid in planned_loc_ids if lid not in counted_loc_ids]
            
            if missing_loc_ids:
                missing_names = request.env['stock.location'].sudo().browse(missing_loc_ids).mapped('complete_name')
                return {
                    'ok': False, 
                    'error': f"No se puede finalizar. Faltan contar {len(missing_names)} ubicaciones: {', '.join(missing_names)}"
                }

            wave.write({'state': 'done'})
            
            # Registrar en log
            request.env['wmds.log'].sudo().create({
                'cycle_count': wave.cycle_count_id.id,
                'log': f"Ola {wave.name} finalizada por {request.env.user.name}",
                'user': request.env.user.id,
                'date': fields.Datetime.now()
            })
            
            return {'ok': True}
        except Exception as e:
            return {'ok': False, 'error': str(e)}

    @http.route('/wmds/v2/engine/close_cycle_count', type='json', auth='user', methods=['POST'])
    def close_cycle_count(self, **kw):
        try:
            count = request.env['scheduled.cycle.count'].sudo().with_context(active_test=False).browse(kw.get('count_id'))
            count.write({'state': 'finalized'})
            
            # Registrar en log
            request.env['wmds.log'].sudo().create({
                'cycle_count': count.id,
                'log': f"Ciclo de conteo {count.name} FINALIZADO por {request.env.user.name}",
                'user': request.env.user.id,
                'date': fields.Datetime.now()
            })
            
            # Restore the location parents
            for sl in count.selected_location_ids:
                if sl.location_id:
                    if sl.location_id.original_parent_id:
                        sl.location_id.write({
                            'location_id': sl.location_id.original_parent_id.id,
                            'block_reason': False,
                            'original_parent_id': False
                        })
                    else:
                        sl.location_id.write({
                            'block_reason': False
                        })
                
            return {'ok': True}
        except Exception as e:
            return {'ok': False, 'error': str(e)}

    @http.route('/wmds/v2/engine/cancel_cycle_count', type='json', auth='user', methods=['POST'])
    def cancel_cycle_count(self, **kw):
        try:
            count = request.env['scheduled.cycle.count'].sudo().with_context(active_test=False).browse(kw.get('count_id'))
            count.write({'state': 'cancelled'})
            
            # Registrar en log
            request.env['wmds.log'].sudo().create({
                'cycle_count': count.id,
                'log': f"Ciclo de conteo {count.name} CANCELADO por {request.env.user.name}",
                'user': request.env.user.id,
                'date': fields.Datetime.now()
            })
            
            # Cancelar olas no terminadas
            count.wave_ids.filtered(lambda w: w.state not in ['done', 'cancelled']).write({'state': 'cancelled'})
            
            # Restore the location parents
            for sl in count.selected_location_ids:
                if sl.location_id:
                    if sl.location_id.original_parent_id:
                        sl.location_id.write({
                            'location_id': sl.location_id.original_parent_id.id,
                            'block_reason': False,
                            'original_parent_id': False
                        })
                    else:
                        sl.location_id.write({
                            'block_reason': False
                        })
                
            return {'ok': True}
        except Exception as e:
            return {'ok': False, 'error': str(e)}

    @http.route('/wmds/v2/engine/reassign_cycle_count_wave_operator', type='json', auth='user', methods=['POST'])
    def reassign_cycle_count_wave_operator(self, **kw):
        try:
            wave = request.env['cycle.count.wave'].sudo().browse(kw.get('wave_id'))
            new_op = request.env['res.users'].sudo().browse(kw.get('operator_id'))
            old_op_name = wave.operator_id.name
            wave.write({'operator_id': new_op.id})
            
            # Registrar en log
            request.env['wmds.log'].sudo().create({
                'cycle_count': wave.cycle_count_id.id,
                'log': f"Ola {wave.name} reasignada de {old_op_name} a {new_op.name} por {request.env.user.name}",
                'user': request.env.user.id,
                'date': fields.Datetime.now()
            })
            
            return {'ok': True}
        except Exception as e:
            return {'ok': False, 'error': str(e)}

    @http.route('/wmds/v2/engine/cancel_cycle_count_wave', type='json', auth='user', methods=['POST'])
    def cancel_cycle_count_wave(self, **kw):
        try:
            wave = request.env['cycle.count.wave'].sudo().browse(kw.get('wave_id'))
            wave.write({'state': 'cancelled'})
            
            # Registrar en log
            request.env['wmds.log'].sudo().create({
                'cycle_count': wave.cycle_count_id.id,
                'log': f"Ola {wave.name} CANCELADA por {request.env.user.name}",
                'user': request.env.user.id,
                'date': fields.Datetime.now()
            })
            
            return {'ok': True}
        except Exception as e:
            return {'ok': False, 'error': str(e)}

    @http.route('/wmds/v2/engine/get/cycle_count_comparison', type='json', auth='user', methods=['POST'])
    def get_cycle_count_comparison(self, **kw):
        try:
            count_id = kw.get('count_id')
            if not count_id:
                return {'ok': False, 'error': 'ID de ciclo requerido.'}
            
            count = request.env['scheduled.cycle.count'].sudo().with_context(active_test=False).browse(count_id)
            waves = count.wave_ids
            
            # Mapeo de ubicaciones seleccionadas y su estado de bloqueo
            loc_block_map = {sl.location_id.id: sl.is_blocked for sl in count.selected_location_ids}
            loc_ids = list(loc_block_map.keys())
            
            # Obtener todas las líneas de todas las olas
            all_lines = request.env['cycle.count.line'].sudo().with_context(active_test=False).search([('wave_id', 'in', waves.ids)])
            
            comparison_map = {}
            # Track which locations were marked as empty by which waves
            empty_locations_by_wave = set() # (wave_id, location_id)
            
            # Identify locations with active reservations for comparison view
            reservations = request.env['stock.move.line'].sudo().search([
                ('location_id', 'in', loc_ids),
                ('state', 'not in', ['done', 'cancel']),
                ('quantity', '>', 0)
            ])
            res_info_map = {}
            for res in reservations:
                lid = res.location_id.id
                if lid not in res_info_map:
                    res_info_map[lid] = []
                p_name = res.picking_id.name or res.move_id.reference or "Movimiento Interno"
                if p_name not in res_info_map[lid]:
                    res_info_map[lid].append(p_name)

            # Inicializar con lo contado
            for line in all_lines:
                if not line.product_id or not line.stock_location_id:
                    if line.description == 'Marcada como vacía':
                        empty_locations_by_wave.add((line.wave_id.id, line.stock_location_id.id))
                    continue
                key = (line.stock_location_id.id, line.product_id.id)
                if key not in comparison_map:
                    lid = line.stock_location_id.id
                    comparison_map[key] = {
                        'location_id': lid,
                        'location_name': line.stock_location_id.complete_name,
                        'is_blocked': loc_block_map.get(lid, False),
                        'has_reservation': lid in res_info_map,
                        'reservation_info': ", ".join(res_info_map.get(lid, [])),
                        'product_id': line.product_id.id,
                        'product_sku': line.product_id.default_code or 'N/A',
                        'product_name': line.product_id.name,
                        'barcode': line.product_id.barcode or 'N/A',
                        'wave_counts': {str(w.id): '-' for w in waves},
                        'theoretical_qty': 0,
                    }
                comparison_map[key]['wave_counts'][str(line.wave_id.id)] = line.qty

            # Obtener stock teórico de las ubicaciones
            quants = request.env['stock.quant'].sudo().with_context(active_test=False).search([
                ('location_id', 'in', loc_ids),
                ('quantity', '>', 0)
            ])
            
            for q in quants:
                key = (q.location_id.id, q.product_id.id)
                if key not in comparison_map:
                    lid = q.location_id.id
                    comparison_map[key] = {
                        'location_id': lid,
                        'location_name': q.location_id.complete_name,
                        'is_blocked': loc_block_map.get(lid, False),
                        'has_reservation': lid in res_info_map,
                        'reservation_info': ", ".join(res_info_map.get(lid, [])),
                        'product_id': q.product_id.id,
                        'product_sku': q.product_id.default_code or 'N/A',
                        'product_name': q.product_id.name,
                        'barcode': q.product_id.barcode or 'N/A',
                        'wave_counts': {str(w.id): '-' for w in waves},
                        'theoretical_qty': 0,
                    }
                comparison_map[key]['theoretical_qty'] += q.quantity

            # Also ensure all locations appear at least once even if empty and not counted
            for loc_id in loc_ids:
                has_loc = any(entry['location_id'] == loc_id for entry in comparison_map.values())
                if not has_loc:
                    loc = request.env['stock.location'].sudo().browse(loc_id)
                    key = (loc_id, 0) # Dummy product id
                    comparison_map[key] = {
                        'location_id': loc_id,
                        'location_name': loc.complete_name,
                        'is_blocked': loc_block_map.get(loc_id, False),
                        'has_reservation': loc_id in res_info_map,
                        'reservation_info': ", ".join(res_info_map.get(loc_id, [])),
                        'product_id': 0,
                        'product_sku': '---',
                        'product_name': '(Ubicación Vacía)',
                        'barcode': '---',
                        'wave_counts': {str(w.id): '-' for w in waves},
                        'theoretical_qty': 0,
                    }

            # Apply "marked as empty" 0s to all products in those locations for those waves
            for (wave_id, loc_id) in empty_locations_by_wave:
                wave_key = str(wave_id)
                for entry in comparison_map.values():
                    if entry['location_id'] == loc_id:
                        if entry['wave_counts'].get(wave_key) == '-':
                            entry['wave_counts'][wave_key] = 0

            # 3. Formatear data final y detectar discrepancias
            report_data = []
            for entry in comparison_map.values():
                # Calculamos si hay discrepancia
                # Una discrepancia ocurre si algun conteo de ola difiere del teorico
                # o si las olas difieren entre sí.
                counts = [v for v in entry['wave_counts'].values() if v != '-']
                theo = entry['theoretical_qty']
                
                has_discrepancy = False
                if not counts and theo > 0:
                    has_discrepancy = True
                else:
                    for c in counts:
                        if c != theo:
                            has_discrepancy = True
                            break
                    if len(set(counts)) > 1:
                        has_discrepancy = True
                
                entry['has_discrepancy'] = has_discrepancy
                report_data.append(entry)

            return {
                'ok': True,
                'waves': [{'id': w.id, 'name': w.name, 'operator': w.operator_id.name, 'state': w.state} for w in waves],
                'data': report_data
            }
        except Exception as e:
            _logger.error(f"Error en reporte de comparación: {e}")
            return {'ok': False, 'error': str(e)}

    @http.route('/wmds/v2/engine/reopen_cycle_count_wave', type='json', auth='user', methods=['POST'])
    def reopen_cycle_count_wave(self, **kw):
        try:
            wave_id = kw.get('wave_id')
            reason = kw.get('reason', 'Sin motivo especificado')
            wave = request.env['cycle.count.wave'].sudo().browse(wave_id)
            if not wave.exists():
                return {'ok': False, 'error': 'Ola no encontrada.'}
            
            wave.write({'state': 'ongoing'})
            
            # Registrar en log
            request.env['wmds.log'].sudo().create({
                'cycle_count': wave.cycle_count_id.id,
                'log': f"Ola {wave.name} reabierta por {request.env.user.name}. Motivo: {reason}",
                'user': request.env.user.id,
                'date': fields.Datetime.now()
            })
            
            return {'ok': True}
        except Exception as e:
            return {'ok': False, 'error': str(e)}

    @http.route('/wmds/v2/engine/adjust_cycle_count_stock', type='json', auth='user', methods=['POST'])
    def adjust_cycle_count_stock(self, **kw):
        try:
            line_data = kw.get('line')
            new_qty = float(kw.get('new_qty', 0))
            reason = kw.get('reason', '')
            count_name = kw.get('count_name', '')
            
            if not line_data or not reason:
                return {'ok': False, 'error': 'Datos insuficientes para el ajuste.'}
            
            # 1. Verificar que todas las olas estén cerradas/canceladas
            count = request.env['scheduled.cycle.count'].sudo().with_context(active_test=False).search([('name', '=', count_name)], limit=1)
            if count:
                open_waves = count.wave_ids.filtered(lambda w: w.state not in ['done', 'cancelled'])
                if open_waves:
                    return {'ok': False, 'error': f"Existen {len(open_waves)} olas abiertas. Finalícelas antes de ajustar."}

            product_id = line_data.get('product_id')
            location_id = line_data.get('location_id')
            
            product = request.env['product.product'].sudo().browse(product_id)
            # El ajuste se realiza en la UBICACIÓN bloqueada
            location = request.env['stock.location'].sudo().with_context(active_test=False).browse(location_id)
            
            if not product.exists() or not location.exists():
                return {'ok': False, 'error': 'Producto o ubicación no válidos.'}

            # Realizar el ajuste de inventario vía stock.quant
            quant = request.env['stock.quant'].sudo().with_context(active_test=False).search([
                ('product_id', '=', product.id),
                ('location_id', '=', location.id),
                ('lot_id', '=', False),
                ('package_id', '=', False),
                ('owner_id', '=', False)
            ], limit=1)
            
            old_qty = quant.quantity if quant else 0
            
            if old_qty == new_qty:
                return {'ok': True, 'skipped': True}

            if not quant:
                quant = request.env['stock.quant'].sudo().with_context(active_test=False).create({
                    'product_id': product.id,
                    'location_id': location.id,
                    'inventory_quantity': new_qty,
                })
            else:
                quant.with_context(active_test=False).inventory_quantity = new_qty
            
            # Aplicar el inventario
            quant.with_context(inventory_name=f"Ajuste Conteo {count_name}: {reason}", active_test=False).action_apply_inventory()
            
            loc_name = location.complete_name
            
            # Registrar en el log de WMDS
            manager_name = request.env.user.name
            product_name = product.display_name
            log_msg = f"AJUSTE DE INVENTARIO - Producto: {product_name} | Ubicación: {loc_name} | Cant. Anterior: {old_qty} | Cant. Nueva: {new_qty} | Motivo: {reason} | Manager: {manager_name}"
            
            request.env['wmds.log'].sudo().create({
                'cycle_count': count.id if count else False,
                'log': log_msg,
                'user': request.env.user.id,
                'date': fields.Datetime.now()
            })

            return {'ok': True}
        except Exception as e:
            _logger.error(f"Error ajustando stock: {e}")
            return {'ok': False, 'error': str(e)}

    @http.route('/wmds/v2/engine/get/cycle_count_details_minimal', type='json', auth='user', methods=['POST'])
    def get_cycle_count_details_minimal(self, **kw):
        try:
            wave_id = kw.get('wave_id')
            wave = request.env['cycle.count.wave'].sudo().browse(wave_id)
            if wave.exists():
                # Planned locations (those created with wave)
                # We identify them because they are in wave.line_ids
                # and maybe they are the ones without product_id or just all stock_location_ids in that wave
                
                # Let's get all stock_location_ids that were assigned to this wave
                all_loc_ids = wave.line_ids.mapped('stock_location_id.id')
                
                # Check which ones have at least one line with product_id OR marked as counted
                # Actually, a location is counted if it has at least one line with product_id OR it was explicitly marked as empty.
                # However, the current logic for mark_location_empty also creates lines.
                
                # We consider a location 'done' if there is ANY line for it that HAS a product_id
                # OR if it was explicitly marked as empty (maybe we should have a flag or just check lines).
                
                # Let's get the status of each location
                locations_data = []
                for loc_id in set(all_loc_ids):
                    location = request.env['stock.location'].sudo().browse(loc_id)
                    # A location is done if there is at least one line with counted_by_id set
                    has_count = request.env['cycle.count.line'].sudo().search_count([
                        ('wave_id', '=', wave.id),
                        ('stock_location_id', '=', loc_id),
                        ('counted_by_id', '!=', False)
                    ]) > 0
                    
                    locations_data.append({
                        'id': loc_id,
                        'name': location.complete_name,
                        'status': 'done' if has_count else 'pending'
                    })

                return {
                    'ok': True, 
                    'name': wave.name.split(' ')[0] if wave.name else '',
                    'locations': locations_data
                }
            return {'ok': False, 'error': 'Ola no encontrada.'}
        except Exception as e:
            return {'ok': False, 'error': str(e)}

    @http.route('/wmds/v2/engine/get/cycle_wave_lines', type='json', auth='user', methods=['POST'])
    def get_cycle_wave_lines(self, **kw):
        try:
            wave_id = kw.get('wave_id')
            if not wave_id:
                return {'ok': False, 'error': 'Se requiere ID de ola.'}
            
            wave = request.env['cycle.count.wave'].sudo().browse(wave_id)
            lines = request.env['cycle.count.line'].sudo().search([('wave_id', '=', wave_id)])
            
            map_cols = [
                {'name': 'Producto', 'field': 'product_name'},
                {'name': 'SKU', 'field': 'product_sku'},
                {'name': 'Código de Barras', 'field': 'barcode'},
                {'name': 'Ubicación', 'field': 'location_name'},
                {'name': 'Cantidad Contada', 'field': 'qty'},
            ]
            
            data = []
            for line in lines:
                if line.product_id:
                    data.append({
                        'id': line.id,
                        'product_name': line.product_id.display_name,
                        'product_sku': line.product_id.default_code or '---',
                        'barcode': line.product_id.barcode or '---',
                        'location_name': line.stock_location_id.complete_name,
                        'qty': line.qty,
                    })
                elif line.description == 'Marcada como vacía':
                    data.append({
                        'id': line.id,
                        'product_name': '(EL OPERADOR MARCÓ LA UBICACIÓN COMO VACÍA)',
                        'product_sku': 'N/A',
                        'barcode': 'N/A',
                        'location_name': line.stock_location_id.complete_name,
                        'qty': 0,
                    })
            
            return {'ok': True, 'map_cols': map_cols, 'data': data, 'total_count': len(data)}
        except Exception as e:
            _logger.error(f"Error getting wave lines {e}")
            return {'ok': False, 'error': str(e)}

    @http.route('/wmds/v2/engine/get/cycle_count_logs', type='json', auth='user', methods=['POST'])
    def get_cycle_count_logs(self, **kw):
        try:
            import pytz
            count_id = kw.get('count_id')
            client_tz = kw.get('tz') or request.env.user.tz or 'UTC'
            
            if not count_id:
                return {'ok': False, 'error': 'Se requiere ID de ciclo.'}

            logs = request.env['wmds.log'].sudo().search([('cycle_count', '=', count_id)], order='date desc')

            tz = pytz.timezone(client_tz)
            data = []
            for log in logs:
                # Convert UTC date to client timezone
                utc_date = log.date.replace(tzinfo=pytz.utc)
                local_date = utc_date.astimezone(tz)
                
                data.append({
                    'id': log.id,
                    'log': log.log,
                    'user': log.user.name if log.user else '---',
                    'date': local_date.strftime('%Y-%m-%d %H:%M:%S'),
                })

            return {'ok': True, 'data': data}
        except Exception as e:
            _logger.error(f"Error getting cycle count logs {e}")
            return {'ok': False, 'error': str(e)}

    @http.route('/wmds/v2/engine/create_waves_for_cycle', type='json', auth='user', methods=['POST'])
    def create_waves_for_cycle(self, **kw):
        try:
            location_ids = kw.get('location_ids', [])
            operators = kw.get('operators', [])
            cycle_count_id = kw.get('cycle_count_id')

            if not location_ids or not operators or not cycle_count_id:
                return {'ok': False, 'error': 'Faltan ubicaciones, operadores o id del ciclo.'}

            count_obj = request.env['scheduled.cycle.count'].sudo().with_context(active_test=False).browse(cycle_count_id)
            
            # Filter out blocked locations
            blocked_location_ids = count_obj.selected_location_ids.filtered(lambda sl: sl.is_blocked).mapped('location_id.id')
            active_location_ids = [lid for lid in location_ids if lid not in blocked_location_ids]

            if not active_location_ids:
                return {'ok': False, 'error': 'No hay ubicaciones activas (no bloqueadas) para asignar.'}

            for op_id in operators:
                wave_obj = request.env['cycle.count.wave'].sudo().create({
                    'cycle_count_id': cycle_count_id,
                    'operator_id': op_id,
                    'state': 'draft'
                })
                # Las líneas de la ola apuntan a la ubicación
                line_vals = [(0, 0, {'stock_location_id': lid}) for lid in active_location_ids]
                wave_obj.write({'line_ids': line_vals})

            return {'ok': True}
        except Exception as e:
            _logger.error(f"Error creando olas: {str(e)}")
            return {'ok': False, 'error': str(e)}

    @http.route('/wmds/v2/engine/toggle_location_block', type='json', auth='user', methods=['POST'])
    def toggle_location_block(self, **kw):
        try:
            count_id = kw.get('count_id')
            location_id = kw.get('location_id')
            if not count_id or not location_id:
                return {'ok': False, 'error': 'Faltan parámetros.'}
            
            sl = request.env['cycle.count.selected.location'].sudo().search([
                ('cycle_count_id', '=', count_id),
                ('location_id', '=', location_id)
            ], limit=1)
            
            if not sl:
                return {'ok': False, 'error': 'Ubicación no encontrada en este ciclo.'}
            
            # Check for active reservations if we are blocking
            if not sl.is_blocked:
                loc = sl.location_id
                reservations = request.env['stock.move.line'].sudo().search([
                    ('location_id', '=', loc.id),
                    ('state', 'not in', ['done', 'cancel']),
                    ('quantity', '>', 0)
                ], limit=1)
                
                if reservations:
                    return {
                        'ok': False, 
                        'error': f"No se puede bloquear la ubicación {loc.complete_name}, tiene una reserva en el movimiento {reservations.picking_id.name or reservations.move_id.reference}. Termine el traslado o anule la reserva."
                    }

            sl.is_blocked = not sl.is_blocked
            
            # Registrar en log
            request.env['wmds.log'].sudo().create({
                'cycle_count': count_id,
                'log': f"Ubicación {sl.location_id.complete_name} {'BLOQUEADA' if sl.is_blocked else 'DESBLOQUEADA'} para nuevas olas por {request.env.user.name}",
                'user': request.env.user.id,
                'date': fields.Datetime.now()
            })
            
            return {'ok': True, 'is_blocked': sl.is_blocked}
        except Exception as e:
            return {'ok': False, 'error': str(e)}

    @http.route('/wmds/v2/engine/mark_location_empty', type='json', auth='user', methods=['POST'])
    def mark_location_empty(self, **kw):
        try:
            wave_id = kw.get('wave_id')
            location_id = kw.get('location_id')
            operator_email = kw.get('operator_email')
            
            if not all([wave_id, location_id, operator_email]):
                return {'ok': False, 'error': 'Faltan datos.'}
            
            wave = request.env['cycle.count.wave'].sudo().browse(wave_id)
            operator = request.env['res.users'].sudo().search([('login', '=', operator_email)], limit=1)
            
            # Get all products that Odoo thinks are in this location
            quants = request.env['stock.quant'].sudo().search([
                ('location_id', '=', location_id),
                ('quantity', '>', 0)
            ])
            
            products_to_zero = quants.mapped('product_id')
            
            # Also include products already in the wave lines for this location
            wave_lines = request.env['cycle.count.line'].sudo().search([
                ('wave_id', '=', wave.id),
                ('stock_location_id', '=', location_id),
                ('product_id', '!=', False)
            ])
            products_to_zero |= wave_lines.mapped('product_id')

            if not products_to_zero:
                # If Odoo thinks it's empty and no lines exist, just create one generic 0 line if needed?
                # Actually, the user wants to mark it as empty. We'll create at least one line to mark it as "counted".
                request.env['cycle.count.line'].sudo().create({
                    'wave_id': wave.id,
                    'stock_location_id': location_id,
                    'product_id': False, # No specific product, but it's counted as empty
                    'qty': 0,
                    'counted_by_id': operator.id if operator else False,
                    'counted_at': fields.Datetime.now(),
                    'description': 'Marcada como vacía'
                })
            else:
                for product in products_to_zero:
                    existing = request.env['cycle.count.line'].sudo().search([
                        ('wave_id', '=', wave.id),
                        ('stock_location_id', '=', location_id),
                        ('product_id', '=', product.id)
                    ], limit=1)
                    if existing:
                        existing.write({
                            'qty': 0,
                            'counted_by_id': operator.id if operator else False,
                            'counted_at': fields.Datetime.now()
                        })
                    else:
                        request.env['cycle.count.line'].sudo().create({
                            'wave_id': wave.id,
                            'stock_location_id': location_id,
                            'product_id': product.id,
                            'qty': 0,
                            'counted_by_id': operator.id if operator else False,
                            'counted_at': fields.Datetime.now()
                        })

            if wave.state == 'draft':
                wave.write({'state': 'ongoing'})

            # Log in WMDS
            loc_name = request.env['stock.location'].sudo().browse(location_id).complete_name
            request.env['wmds.log'].sudo().create({
                'cycle_count': wave.cycle_count_id.id,
                'log': f"Operador {operator.name if operator else operator_email} marcó la ubicación {loc_name} como VACÍA en la ola {wave.name}",
                'user': operator.id if operator else False,
                'date': fields.Datetime.now()
            })

            return {'ok': True}
        except Exception as e:
            return {'ok': False, 'error': str(e)}


    @http.route('/wmds/v2/engine/cycle_count_assigned', type='json', auth='user', methods=['POST'])
    def cycle_count_assigned(self, **kw):
        operator = kw.get("email")
        
        waves = request.env['cycle.count.wave'].sudo().search(
            [
                ('operator_id.login', '=', operator),
                ("state", "in", ["draft", "ongoing"])
            ], order='id desc', limit=5
        )

        if not waves:
            return []

        result = []
        for wave in waves:
            label = wave.name.split(' ')[0] if wave.name else ''
            
            result.append({
                    "key": wave.id,
                    "label": label,
                    "data": wave.name,
                    "pick": wave.name,
                    "date": wave.create_date.strftime('%Y-%m-%d %H:%M') if wave.create_date else None
                })
        
        return result

    @http.route('/wmds/v2/engine/validate_cycle_count_location', type='json', auth='user', methods=['POST'])
    def validate_cycle_count_location(self, **kw):
        try:
            wave_id = kw.get('wave_id')
            location_data = kw.get('location_name') # This could be name or barcode
            
            if not wave_id or not location_data:
                return {'ok': False, 'error': 'Faltan parámetros.'}
            
            wave = request.env['cycle.count.wave'].sudo().browse(wave_id)
            if not wave.exists():
                return {'ok': False, 'error': 'Ola no encontrada.'}
            
            # Buscar la ubicación escaneada
            scanned_location = request.env['stock.location'].sudo().with_context(active_test=False).search([
                '|', ('complete_name', '=', location_data), ('barcode', '=', location_data)
            ], limit=1)
            
            if not scanned_location:
                return {'ok': False, 'error': 'Ubicación no encontrada.'}
            
            # Buscar en el maestro si esta ubicación está asignada
            count = wave.cycle_count_id
            sl_entry = count.selected_location_ids.filtered(
                lambda sl: sl.location_id.id == scanned_location.id
            )
            
            if not sl_entry:
                return {'ok': False, 'error': 'Esta ubicación no está asignada a este ciclo de conteo.'}
            
            target_location = sl_entry.location_id
            
            # Verificar si esta ubicación está en la ola
            planned_location = wave.line_ids.filtered(lambda l: l.stock_location_id.id == target_location.id)
            if not planned_location:
                return {'ok': False, 'error': 'Esta ubicación no está en su ola de trabajo.'}
            
            if wave.state == 'draft':
                wave.write({'state': 'ongoing'})
            
            return {
                'ok': True,
                'location_id': target_location.id,
                'location_name': target_location.complete_name
            }
        except Exception as e:
            return {'ok': False, 'error': str(e)}

    @http.route('/wmds/v2/engine/validate_cycle_count_product', type='json', auth='user', methods=['POST'])
    def validate_cycle_count_product(self, **kw):
        try:
            barcode = kw.get('barcode')
            location_id = kw.get('location_id')
            if not barcode:
                return {'ok': False, 'error': 'Se requiere código de barras.'}
            
            product = request.env['product.product'].sudo().search([
                '|', ('barcode', '=', barcode), ('default_code', '=', barcode)
            ], limit=1)
            
            if not product:
                return {'ok': False, 'error': 'Producto no encontrado.'}
            
            theoretical_qty = 0
            if location_id:
                quant = request.env['stock.quant'].sudo().search([
                    ('product_id', '=', product.id),
                    ('location_id', '=', int(location_id))
                ], limit=1)
                theoretical_qty = quant.quantity if quant else 0

            return {
                'ok': True,
                'product_id': product.id,
                'product_name': product.display_name,
                'product_sku': product.default_code,
                'theoretical_qty': theoretical_qty
            }
        except Exception as e:
            return {'ok': False, 'error': str(e)}

    @http.route('/wmds/v2/engine/log_cycle_count_line', type='json', auth='user', methods=['POST'])
    def log_cycle_count_line(self, **kw):
        try:
            wave_id = kw.get('wave_id')
            location_id = kw.get('location_id')
            product_id = kw.get('product_id')
            qty = float(kw.get('qty', 0))
            operator_email = kw.get('operator_email')
            
            if not all([wave_id, location_id, product_id, operator_email]):
                return {'ok': False, 'error': 'Faltan datos para registrar el conteo.'}
            
            wave = request.env['cycle.count.wave'].sudo().browse(wave_id)
            operator = request.env['res.users'].sudo().search([('login', '=', operator_email)], limit=1)
            
            if not wave.exists():
                return {'ok': False, 'error': 'Ola no encontrada.'}
            
            # Buscar si ya existe una línea para este producto en esta ubicación para esta ola
            # pero SOLO si ya tiene producto. Las líneas iniciales no tienen producto.
            existing_line = request.env['cycle.count.line'].sudo().search([
                ('wave_id', '=', wave.id),
                ('stock_location_id', '=', location_id),
                ('product_id', '=', product_id)
            ], limit=1)
            
            if existing_line:
                # Si ya existe, actualizamos la cantidad (asumimos que es un re-conteo o suma?)
                # El usuario dijo "set a quantity", así que probablemente sobreescribir.
                existing_line.write({
                    'qty': qty,
                    'counted_by_id': operator.id if operator else False,
                    'counted_at': fields.Datetime.now()
                })
            else:
                # Si no existe, buscamos una línea de "ubicación vacía" (sin producto) para aprovecharla?
                # No, mejor crear una nueva y si al final quedan líneas sin producto, son las que no se contaron o estaban vacías.
                request.env['cycle.count.line'].sudo().create({
                    'wave_id': wave.id,
                    'stock_location_id': location_id,
                    'product_id': product_id,
                    'qty': qty,
                    'counted_by_id': operator.id if operator else False,
                    'counted_at': fields.Datetime.now()
                })
            
            # Si el estado era draft, pasar a ongoing
            if wave.state == 'draft':
                wave.write({'state': 'ongoing'})
                
            # Logging the action in wmds.log
            user_tz = request.env.user.tz or operator.tz or 'UTC'
            tz = pytz.timezone(user_tz)
            local_time = fields.Datetime.now().replace(tzinfo=pytz.utc).astimezone(tz)
            time_str = local_time.strftime('%H:%M:%S (%Z)')
            
            count = wave.cycle_count_id
            loc_name = request.env['stock.location'].sudo().browse(location_id).complete_name
            
            product = request.env['product.product'].sudo().browse(product_id)
            product_name = product.display_name
            wave_name = wave.name
            operator_name = operator.name if operator else operator_email
            
            log_msg = f"Operador {operator_name} contó {qty} unidades de {product_name} en la ola {wave_name} a las {time_str} en la ubicación {loc_name}"
            
            request.env['wmds.log'].sudo().create({
                'cycle_count': count.id,
                'log': log_msg,
                'user': operator.id if operator else False,
                'date': fields.Datetime.now()
            })
            
            return {'ok': True}
        except Exception as e:
            _logger.error(f"Error logging cycle count line: {e}")
            return {'ok': False, 'error': str(e)}