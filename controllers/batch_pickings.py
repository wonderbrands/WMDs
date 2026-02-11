from odoo import http
from odoo.http import request

class BatchPickController(http.Controller):

    def _get_and_validate_picking(self, reference):
        if not reference:
            return None, "Es necesario pasar un valor válido."

        ref_cap = reference.upper().strip()
        pick_odoo = None

        if ref_cap.startswith("S"):
            so = request.env['sale.order'].sudo().search([("name", "=", ref_cap)], limit=1)
            if not so:
                return None, f"La SO {ref_cap} no existe."
            
            if so.state != "sale":
                return None, f"La SO {ref_cap} no está confirmada (Estado actual: {so.state})."

            pick_odoo = so.picking_ids.filtered_domain([
                ('picking_type_id.name', '=', 'Pick'),
                ('state', '!=', 'cancel')
            ])[:1]

            if not pick_odoo:
                return None, f"La SO {ref_cap} no tiene un pick de tipo 'Pick' válido."

        elif ref_cap.startswith("WH/PICK"):
            pick_odoo = request.env['stock.picking'].sudo().search([
                ("name", "=", ref_cap),
                ('picking_type_id.name', '=', 'Pick'),
            ], limit=1)
            
            if not pick_odoo:
                return None, f"El pick {ref_cap} no existe."
        else:
            return None, f"Formato no reconocido: {ref_cap}. Use SO... o WH/PICK..."

        # NUEVA VALIDACIÓN: Verificar si ya tiene un batch asignado
        if pick_odoo.batch_id:
            return None, f"El pick {pick_odoo.name} ya pertenece al lote {pick_odoo.batch_id.name}."

        if pick_odoo.state != "assigned":
            return None, f"El pick {pick_odoo.name} no está disponible (Estado: {pick_odoo.state})."

        return pick_odoo, None

    @http.route('/wmds/v2/engine/post/validate_pick_for_batch', type='json', auth='user', methods=['POST'], csrf=True)
    def validate_pick_for_batch(self, **kw):
        pick_ref = kw.get("pick")
        pick_obj, error_msg = self._get_and_validate_picking(pick_ref)

        if error_msg:
            return {
                'error': True,
                'error_msg': error_msg
            }

        return {
            'status': "ok",
            'picking_id': pick_obj.id,
            'picking_name': pick_obj.name
        }

    @http.route('/wmds/v2/engine/post/save_batch', type='json', auth='user', methods=['POST'], csrf=True)
    def save_batch(self, **kw):
        picks_to_process = kw.get("batch_create")
        operator_code = kw.get("operator_id")

        if not picks_to_process or not isinstance(picks_to_process, list):
            return {
                'error': True,
                'error_msg': "Es necesario pasar una lista de 'batch_create'."
            }

        operator_user = None
        if operator_code:
            operator_user = request.env['res.users'].sudo().search([('login', '=', operator_code)], limit=1)
            if not operator_user:
                 operator_user = request.env['res.users'].sudo().search([('id', '=', operator_code)], limit=1)

        valid_picks = []

        for item in picks_to_process:
            ref = item.get('value') if isinstance(item, dict) else item
            pick_obj, error_msg = self._get_and_validate_picking(ref)

            if error_msg:
                return {
                    'error': True,
                    'error_msg': f"Error en lote con '{ref}': {error_msg}"
                }
            
            valid_picks.append(pick_obj)

        if not valid_picks:
             return {
                'error': True,
                'error_msg': "No se encontraron picks válidos."
            }

        try:
            pick_ids = [p.id for p in valid_picks]

            batch_vals = {
                'user_id': request.env.user.id,
                'picking_ids': [(6, 0, pick_ids)] 
            }
            
            new_batch = request.env['stock.picking.batch'].sudo().create(batch_vals)
            
           
            new_batch.action_confirm()
            console.log(f"[Backend] >> Batch {new_batch.name} confirmado automáticamente")

            op_name = operator_user.name if operator_user else "Sin asignar"

            for pick in valid_picks:
                if operator_user:
                    pick.sudo().write({'operator': operator_user.id})
                
                request.env['wmds.log'].sudo().create({
                    'pick': pick.id,
                    'user': request.env.user.id,
                    'log': f"Metido en el batch {new_batch.name} (Confirmado), asignado al operador {op_name}"
                })

        except Exception as e:
            return {'error': True, 'error_msg': f"Error de sistema al crear/confirmar batch: {str(e)}"}
        
        return {
            'status': "ok",
            'message': f"Batch {new_batch.name} creado y confirmado exitosamente con {len(valid_picks)} órdenes.",
            'batch_name': new_batch.name,
            'batch_id': new_batch.id,
            'state': new_batch.state
        }