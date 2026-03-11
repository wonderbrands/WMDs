from odoo import http
from odoo.http import request
import logging
import re

_logger = logging.getLogger(__name__)

class CycleCount(http.Controller):

    @http.route('/wmds/v2/engine/get/locations_by_range', type='json', auth='user', methods=['POST'], csrf=True)
    def get_locations_by_range(self, **kw):
        try:
            # Extraer y asegurar tipos de datos
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
            
            _logger.info(f"Buscando ubicaciones con Regex: {final_regex}")

           
            domain = [
                ('complete_name', '=ilike', 'WH%'),
                ('complete_name', 'not ilike', 'Cuarentena'),
                ('usage', '=', 'internal') 
            ]
            
            all_locs = request.env['stock.location'].sudo().search(domain, order='complete_name asc')
            
            locations = all_locs.filtered(
                lambda ubi: re.fullmatch(final_regex, ubi.complete_name, re.IGNORECASE)
            )

            res_locations = [{'id': loc.id, 'complete_name': loc.complete_name} for loc in locations]

            return {
                'ok': True,
                'locations': res_locations
            }

        except Exception as e:
            _logger.error(f"Error en búsqueda de ubicaciones: {str(e)}")
            return {'ok': False, 'error': str(e)}


    @http.route('/wmds/v2/engine/get/cycle_counts', type='json', auth='user', methods=['POST'])
    def get_cycle_counts(self, **kw):
        try:
            counts = request.env['scheduled.cycle.count'].sudo().search([], order='create_date desc')
            
            result = []
            for count in counts:
                result.append({
                    'id': count.id,
                    'name': count.name,
                    'notes': count.notes or '',
                    'state': count.state,
                    'state_label': dict(count._fields['state'].selection).get(count.state)
                })
                
            return {
                'ok': True,
                'data': result
            }
        except Exception as e:
            _logger.error(f"Error obteniendo conteos cíclicos: {str(e)}")
            return {'ok': False, 'error': str(e)}


    @http.route('/wmds/v2/engine/create_full_cycle_count', type='json', auth='user', methods=['POST'], csrf=True)
    def create_full_cycle_count(self, **kw):
        try:
            location_ids = kw.get('location_ids', [])
            operators = kw.get('operators', [])
            user_notes = kw.get('name')

            if not location_ids or not operators:
                return {'ok': False, 'error': 'Faltan ubicaciones u operadores para generar el conteo.'}

            count_obj = request.env['scheduled.cycle.count'].sudo().create({
                'notes': user_notes,
                'selected_location_ids': [(0, 0, {'location_id': lid}) for lid in location_ids]
            })

            for index, op_id in enumerate(operators, start=1):
                wave_name = f"{count_obj.name}-WAVE{str(index).zfill(3)}"
                wave_obj = request.env['cycle.count.wave'].sudo().create({
                    'name': wave_name,
                    'cycle_count_id': count_obj.id,
                    'operator_id': op_id,
                    'state': 'draft'
                })

                line_vals = []
                for loc_id in location_ids:
                    line_vals.append((0, 0, {
                        'wave_id': wave_obj.id,
                        'stock_location_id': loc_id,
                    }))
                
                wave_obj.sudo().write({'line_ids': line_vals})

            return {
                'ok': True, 
                'id': count_obj.id, 
                'name': count_obj.name
            }

        except Exception as e:
            _logger.error(f"Error creando conteo cíclico completo: {str(e)}")
            return {'ok': False, 'error': str(e)}