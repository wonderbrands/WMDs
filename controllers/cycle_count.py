from odoo import http
from odoo.http import request
import logging
import re

_logger = logging.getLogger(__name__)

def convert_value_in_label(map_cols, value, key):
    if not value:
        return ""

    for col in map_cols:
        if col.get('field') == key and col.get('type') == 'selectable':
            for option in col.get('options', []):
                if option['value'] == value:
                    return option['label']
    return value

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

            state_options = [{'value': s[0], 'label': s[1]} for s in model._fields['state'].selection]
            default_state = next((opt['value'] for opt in state_options if opt['value'] == 'in_progress'), None)

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
                    "state": convert_value_in_label(map_cols, count.state, "state")
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
            re_aisle = rf"[{f['a_from']}-{f['a_to']}]"
            pos_list = [str(i).zfill(2) for i in range(f['p_from'], f['p_to'] + 1)]
            re_pos = rf"P({'|'.join(pos_list)})"
            re_front = rf"F[{f['f_from']}-{f['f_to']}]"
            re_level = rf"N[{f['l_from']}-{f['l_to']}]"
            final_regex = rf".*{re_aisle}-{re_pos}-{re_front}-{re_level}$"
            
            domain = [
                ('complete_name', '=ilike', 'WH%'),
                ('complete_name', 'not ilike', 'Cuarentena'),
                ('usage', '=', 'internal') 
            ]
            all_locs = request.env['stock.location'].sudo().with_context(active_test=True).search(domain, order='complete_name asc')
            
            active_counts = request.env['scheduled.cycle.count'].sudo().search([('state', 'not in', ['finalized', 'cancelled'])])
            active_location_ids = active_counts.mapped('selected_location_ids.location_id.id')
            
            locations = all_locs.filtered(lambda u: u.id not in active_location_ids and re.fullmatch(final_regex, u.complete_name, re.IGNORECASE))
            return {
                'ok': True,
                'locations': [{'id': l.id, 'complete_name': l.complete_name} for l in locations]
            }
        except Exception as e:
            return {'ok': False, 'error': str(e)}

    @http.route('/wmds/v2/engine/create_full_cycle_count', type='json', auth='user', methods=['POST'])
    def create_full_cycle_count(self, **kw):
        try:
            location_ids = kw.get('location_ids', [])
            operators = kw.get('operators', [])
            user_notes = kw.get('name')

            if not location_ids or not operators:
                return {'ok': False, 'error': 'Faltan ubicaciones u operadores.'}

            # 1. Crear el maestro
            count_obj = request.env['scheduled.cycle.count'].sudo().create({
                'notes': user_notes,
                'selected_location_ids': [(0, 0, {'location_id': lid}) for lid in location_ids]
            })

            # 2. Crear las olas (El nombre se computa solo en el modelo)
            for op_id in operators:
                wave_obj = request.env['cycle.count.wave'].sudo().create({
                    'cycle_count_id': count_obj.id,
                    'operator_id': op_id,
                    'state': 'draft'
                })
                line_vals = [(0, 0, {'stock_location_id': lid}) for lid in location_ids]
                wave_obj.write({'line_ids': line_vals})

            # 3. Archive the locations so they aren't used in sales/other operations
            locations = request.env['stock.location'].sudo().browse(location_ids)
            locations.write({'active': False})

            return {'ok': True, 'id': count_obj.id, 'name': count_obj.name}
        except Exception as e:
            _logger.error(f"Error creando ciclo: {str(e)}")
            return {'ok': False, 'error': str(e)}

    @http.route('/wmds/v2/engine/get/cycle_count_details', type='json', auth='user', methods=['POST'])
    def get_cycle_count_details(self, **kw):
        try:
            count = request.env['scheduled.cycle.count'].sudo().browse(kw.get('count_id'))
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
            wave.write({'state': 'done'})
            return {'ok': True}
        except Exception as e:
            return {'ok': False, 'error': str(e)}

    @http.route('/wmds/v2/engine/close_cycle_count', type='json', auth='user', methods=['POST'])
    def close_cycle_count(self, **kw):
        try:
            count = request.env['scheduled.cycle.count'].sudo().browse(kw.get('count_id'))
            count.write({'state': 'finalized'})
            
            # Unarchive the locations
            location_ids = count.selected_location_ids.mapped('location_id.id')
            if location_ids:
                locations = request.env['stock.location'].sudo().with_context(active_test=False).browse(location_ids)
                locations.write({'active': True})
                
            return {'ok': True}
        except Exception as e:
            return {'ok': False, 'error': str(e)}

    @http.route('/wmds/v2/engine/cancel_cycle_count', type='json', auth='user', methods=['POST'])
    def cancel_cycle_count(self, **kw):
        try:
            count = request.env['scheduled.cycle.count'].sudo().browse(kw.get('count_id'))
            count.write({'state': 'cancelled'})
            # Cancelar olas no terminadas
            count.wave_ids.filtered(lambda w: w.state not in ['done', 'cancelled']).write({'state': 'cancelled'})
            
            # Unarchive the locations
            location_ids = count.selected_location_ids.mapped('location_id.id')
            if location_ids:
                locations = request.env['stock.location'].sudo().with_context(active_test=False).browse(location_ids)
                locations.write({'active': True})
                
            return {'ok': True}
        except Exception as e:
            return {'ok': False, 'error': str(e)}

    @http.route('/wmds/v2/engine/reassign_cycle_count_wave_operator', type='json', auth='user', methods=['POST'])
    def reassign_cycle_count_wave_operator(self, **kw):
        try:
            wave = request.env['cycle.count.wave'].sudo().browse(kw.get('wave_id'))
            wave.write({'operator_id': kw.get('operator_id')})
            return {'ok': True}
        except Exception as e:
            return {'ok': False, 'error': str(e)}

    @http.route('/wmds/v2/engine/cancel_cycle_count_wave', type='json', auth='user', methods=['POST'])
    def cancel_cycle_count_wave(self, **kw):
        try:
            wave = request.env['cycle.count.wave'].sudo().browse(kw.get('wave_id'))
            wave.write({'state': 'cancelled'})
            return {'ok': True}
        except Exception as e:
            return {'ok': False, 'error': str(e)}

    @http.route('/wmds/v2/engine/get/cycle_wave_lines', type='json', auth='user', methods=['POST'])
    def get_cycle_wave_lines(self, **kw):
        try:
            wave_id = kw.get('wave_id')
            if not wave_id:
                return {'ok': False, 'error': 'Se requiere ID de ola.'}
            
            lines = request.env['cycle.count.line'].sudo().search([('wave_id', '=', wave_id)])
            
            map_cols = [
                {'name': 'Producto', 'field': 'product_name'},
                {'name': 'SKU', 'field': 'product_sku'},
                {'name': 'Ubicación', 'field': 'location_name'},
                {'name': 'Cantidad Contada', 'field': 'qty'},
            ]
            
            data = [{
                'id': line.id,
                'product_name': line.product_id.display_name,
                'product_sku': line.product_id.default_code,
                'location_name': line.stock_location_id.complete_name,
                'qty': line.qty,
            } for line in lines]
            
            return {'ok': True, 'map_cols': map_cols, 'data': data, 'total_count': len(lines)}
        except Exception as e:
            _logger.error(f"Error getting wave lines {e}")
            return {'ok': False, 'error': str(e)}

    @http.route('/wmds/v2/engine/create_waves_for_cycle', type='json', auth='user', methods=['POST'])
    def create_waves_for_cycle(self, **kw):
        try:
            location_ids = kw.get('location_ids', [])
            operators = kw.get('operators', [])
            cycle_count_id = kw.get('cycle_count_id')

            if not location_ids or not operators or not cycle_count_id:
                return {'ok': False, 'error': 'Faltan ubicaciones, operadores o id del ciclo.'}

            for op_id in operators:
                wave_obj = request.env['cycle.count.wave'].sudo().create({
                    'cycle_count_id': cycle_count_id,
                    'operator_id': op_id,
                    'state': 'draft'
                })
                line_vals = [(0, 0, {'stock_location_id': lid}) for lid in location_ids]
                wave_obj.write({'line_ids': line_vals})

            return {'ok': True}
        except Exception as e:
            _logger.error(f"Error creando olas: {str(e)}")
            return {'ok': False, 'error': str(e)}


    @http.route('/wmds/v2/engine/cycle_count_assigned', type='json', auth='user', methods=['POST'])
    def cycle_count_assigned(self, **kw):
        operator = kw.get("email")
        
        waves = request.env['cycle.count.wave'].sudo().search(
            [
                ('operator_id.login', '=', operator),
                ("state", "in", ["draft", "ongoing"])
            ]
        )

        if not waves:
            return []

        result = []
        for wave in waves:
            result.append({
                    "key": wave.id,
                    "label": wave.name,
                    "data": wave.name,
                    "pick": wave.name,
                    "date": None
                })
        
        return result
    