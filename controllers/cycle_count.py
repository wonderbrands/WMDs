from odoo import http
from odoo.http import request
import logging
import re

_logger = logging.getLogger(__name__)

class CycleCount(http.Controller):

    def convert_value_in_label(self, model, value, field_name):
        if not value: return ''
        return dict(model._fields[field_name].selection).get(value, value)

    @http.route('/wmds/v2/engine/get/cycle_counts', type='json', auth='user', methods=['POST'])
    def get_cycle_counts(self, **kw):
        try:
            model = request.env['scheduled.cycle.count'].sudo()
            counts = model.search([], order='id desc')
            
            # Encabezados legibles para el frontend
            map_cols = [
                {"field": "id", "header": "ID"},
                {"field": "name", "header": "Código"},
                {"field": "notes", "header": "Referencia"},
                {"field": "state", "header": "Estado"}
            ]

            data = []
            for count in counts:
                data.append({
                    "id": count.id,
                    "name": count.name,
                    "notes": count.notes or '',
                    "state": self.convert_value_in_label(model, count.state, "state")
                })

            return {
                "ok": True,
                "map_cols": map_cols,
                "data": data,
                "total_count": len(counts)
            }
        except Exception as e:
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
            all_locs = request.env['stock.location'].sudo().search(domain, order='complete_name asc')
            locations = all_locs.filtered(lambda u: re.fullmatch(final_regex, u.complete_name, re.IGNORECASE))
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
            return {'ok': True}
        except Exception as e:
            return {'ok': False, 'error': str(e)}