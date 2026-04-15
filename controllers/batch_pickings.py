from odoo import http
from odoo.http import request

class BatchPickController(http.Controller):

    def _get_and_validate_picking(self, reference, type_of_batch):
        if not reference:
            return None, "Es necesario pasar un valor válido."

        ref_cap = reference.upper().strip()
        pick_odoo = None

        if type_of_batch=="sale":
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

                #verificar si la orden esta lista para recolectar
                if not so.data_ready_to_pick:
                    return None, f"La SO {ref_cap} no esta lista para recolectar (le hace falta guía y/o carrier)"

            elif ref_cap.startswith("WH/PICK"):
                pick_odoo = request.env['stock.picking'].sudo().search([
                    ("name", "=", ref_cap),
                    ('picking_type_id.name', '=', 'Pick'),
                    ('state', '!=', 'cancel')
                ], limit=1)
                
                if not pick_odoo:
                    return None, f"El pick {ref_cap} no existe o no esta disponible para recolección."

                so = request.env['sale.order'].sudo().search([
                    ("name", "=", pick_odoo.origin),
                ], limit=1)

                if not so:
                     return None, f"El pick {ref_cap} no tiene una SO asociada válida."

                if not so.data_ready_to_pick:
                    return None, f"La SO {so.name} no esta lista para recolectar (le hace falta guía y/o carrier)"

            else:
                return None, f"Formato no reconocido: {ref_cap}. Use SO... o WH/PICK..."

        elif type_of_batch=="full": 
            if ref_cap.startswith("WH/PFUL"):
                pick_odoo = request.env['stock.picking'].sudo().search([
                    ("name", "=", ref_cap),
                    ('picking_type_id.name', 'in', ["Resurtido a Ful: Pick"]),
                    ('state', '!=', 'cancel')
                ], limit=1)
                
                if not pick_odoo:
                    return None, f"El traslado {ref_cap} no existe o no esta disponible para recoleccion."
            else:
                return None, f"Formato no reconocido: {ref_cap}. Use WH/PFUL..."


        # NUEVA VALIDACIÓN: Verificar si ya tiene un batch asignado
        if pick_odoo.batch_id:
            return None, f"El pick {pick_odoo.name} ya pertenece al lote {pick_odoo.batch_id.name}."

        if pick_odoo.state != "assigned":
            return None, f"El pick {pick_odoo.name} no está disponible (Estado: {pick_odoo.state})."

        return pick_odoo, None

    @http.route('/wmds/v2/engine/post/validate_pick_for_batch', type='json', auth='user', methods=['POST'], csrf=True)
    def validate_pick_for_batch(self, **kw):
        pick_ref = kw.get("pick")
        type_of_batch = kw.get("type_of_batch")
        pick_obj, error_msg = self._get_and_validate_picking(pick_ref, type_of_batch)

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
        type_of_batch = kw.get("type_of_batch")

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
            pick_obj, error_msg = self._get_and_validate_picking(ref, type_of_batch)

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

            op_name = operator_user.name if operator_user else "Sin asignar"
            new_batch.operator =  operator_user.id

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

    @http.route('/wmds/v2/engine/post/cancel_batch', type='json', auth='user', methods=['POST'], csrf=True)
    def cancel_batch(self, **kw):
        batch_id = kw.get("id")
        if not batch_id:
            return {'error': True, 'error_msg': "Es necesario pasar un ID de lote."}

        try:
            batch = request.env['stock.picking.batch'].sudo().browse(int(batch_id))
            if not batch.exists():
                return {'error': True, 'error_msg': "El lote no existe."}

            # Reset picked qty in all move lines
            batch.move_line_ids.sudo().write({'wmds_picked_qty': 0.0})
            
            # Cancel the batch in Odoo
            batch.action_cancel()

            request.env['wmds.log'].sudo().create({
                'batch_pick': batch.id,
                'user': request.env.user.id,
                'log': "Plan de pickeo cancelado manualmente por el manager. Cantidades recolectadas reiniciadas."
            })

            return {'status': "ok", 'message': "Plan de pickeo cancelado exitosamente."}

        except Exception as e:
            return {'error': True, 'error_msg': f"Error de sistema al cancelar batch: {str(e)}"}