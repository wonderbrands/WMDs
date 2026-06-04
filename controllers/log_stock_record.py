from odoo import http
from odoo.http import request
from datetime import datetime
import traceback

class LogStockRecord(http.Controller):
    
    @http.route('/wmds/v2/engine/post/log_stock_record', type='json', auth='user', methods=['POST'], csrf=False)
    def log_stock_record(self, **kw):
        try:
            params = kw
            pick_id = params.get('pick_id')
            pick_name = params.get('pick_name')
            operator_mail = params.get('operator_mail')
            message = params.get('message')
            type_of_log = params.get('type')

            picking = request.env['stock.picking'].sudo()
            if pick_id:
                picking = picking.browse(int(pick_id))
            elif pick_name:
                picking = picking.search([('name', '=', pick_name)], limit=1)

            if not picking or not picking.exists():
                return {"error": "Picking no encontrado"}

            operator_id = False
            if operator_mail:
                operator_id = request.env['res.users'].sudo().search([('login', '=ilike', str(operator_mail).strip())], limit=1)
            
            # --- EXTRACCIÓN DE CANTIDADES SEGURA ---
            # Agregamos por producto usando los movimientos (moves) para evitar inconsistencias con líneas divididas
            product_data = {}
            lines = picking.move_ids
            
            for m in lines:
                p_id = m.product_id.id
                p_name = m.product_id.display_name
                
                done = m.quantity
                demand = m.product_uom_qty
                
                if p_id not in product_data:
                    product_data[p_id] = {'name': p_name, 'done': 0.0, 'demand': 0.0}
                
                product_data[p_id]['done'] += done
                product_data[p_id]['demand'] += demand
            
            product_list_arr = [f"{data['name']}: {int(data['done'])}/{int(data['demand'])}" for data in product_data.values()]
            product_list = " | ".join(product_list_arr)
            # ---------------------------------------
            
            p_type_name = picking.picking_type_id.name or ""
            p_type_code = picking.picking_type_id.code
            
            is_storage = any(word in p_type_name.lower() for word in ["storage", "rack", "rackeo"])
            
            dest_location_names = []
            if picking.location_dest_id:
                dest_location_names.append(picking.location_dest_id.name)
            
            if picking.move_line_ids:
                for ml in picking.move_line_ids:
                    loc_name = ml.location_dest_id.name
                    if loc_name and loc_name not in dest_location_names:
                        dest_location_names.append(loc_name)
            
            location_header = ""
            if dest_location_names:
                location_header = f"Hacia {', '.join(dest_location_names)}, "

            detail_header = f"{location_header}Productos: {product_list}"

            is_done = picking.state == 'done'
            
            if type_of_log == "external":
                status_str = "completado" if is_done else "procesado/excluido"
                if is_storage:
                    base_log = f"Rackeo {picking.name} {status_str}."
                elif p_type_code == 'incoming':
                    base_log = f"Recepción {picking.name} {status_str}."
                elif "Pick" in p_type_name:
                    base_log = f"Pick {picking.name} {status_str}."
                elif "Pack" in p_type_name:
                    base_log = f"Pack {picking.name} {status_str}."
                elif p_type_code == 'outgoing':
                    base_log = f"Out {picking.name} despacho {status_str}."
                else:
                    base_log = f"Operación {picking.name} {status_str}."
                log_msg = f"{base_log} {detail_header}"
            
            elif type_of_log == "backorder":
                log_msg = f"Backorder para {picking.name}. {detail_header}"
            
            else:
                log_msg = f"{message} {detail_header}" if message else detail_header

            # Limpiar saltos de línea por si acaso
            log_msg = log_msg.replace('\n', ' ').replace('\r', ' ').strip()

            from odoo import fields
            request.env["wmds.log"].sudo().create({
                'user': operator_id.id if operator_id else request.env.user.id,
                'date': fields.Datetime.now(),
                'pick': picking.id,
                'log': log_msg
            })
            return {"saved": True, "log_created": log_msg} 
            
        except Exception as e:
            # Al estar todo en el try, si algo falla, siempre recibirás un JSON con el error
            import traceback
            return {"error": f"{str(e)} - Trace: {traceback.format_exc()}"}

    @http.route('/wmds/v2/engine/post/change_wmds_status', type='json', auth='user', methods=['POST'], csrf=False)
    def change_wmds_status(self, **kw):
        pass
        """
        params = kw
        pick_id = params.get('pick_id')
        pick_name = params.get('pick_name')
        status = params.get('status')

        try:
            picking = request.env['stock.picking'].sudo()
            if pick_id:
                picking = picking.browse(int(pick_id))
            elif pick_name:
                picking = picking.search([('name', '=', pick_name)], limit=1)
            
            if picking and picking.exists():
                status_rec = request.env['wmds.stock.status'].sudo().search([('value', '=', status)], limit=1)
                if status_rec:
                    picking.wmds_status = status_rec.id
                    return {"saved": True}
            return {"error": "Picking o Estatus no encontrado"}
        except Exception as e:
            return {"error": f"{str(e)}\n{traceback.format_exc()}"}
        """
        pass