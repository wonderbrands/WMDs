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

            operator_id = request.env['res.users'].sudo().search([('login', '=', operator_mail)], limit=1)
            
            # --- EXTRACCIÓN DE CANTIDADES SEGURA ---
            lines = picking.move_line_ids or picking.move_ids_without_package
            product_list_arr = []
            
            for m in lines:
                # 1. Buscamos lo procesado (qty_done en move_line, quantity_done en move)
                qty = getattr(m, 'qty_done', 0)
                if not qty:
                    qty = getattr(m, 'quantity_done', 0)
                
                # 2. Si es 0 (como en backorders nuevas), buscamos lo demandado/reservado
                if not qty:
                    qty = getattr(m, 'product_uom_qty', getattr(m, 'reserved_uom_qty', 0))
                    
                product_list_arr.append(f"- {m.product_id.display_name}: {qty}")
                
            product_list = "; ".join(product_list_arr)
            # ---------------------------------------
            
            p_type_name = picking.picking_type_id.name or ""
            p_type_code = picking.picking_type_id.code
            
            is_storage = any(word in p_type_name.lower() for word in ["storage", "rack", "rackeo"])
            
            location_header = ""
            if not is_storage and picking.location_dest_id:
                location_header = f"Hacia la ubicación {picking.location_dest_id.name}, "

            detail_header = f"{location_header}se han trasladado los siguientes productos: {product_list}"

            if type_of_log == "external":
                if is_storage:
                    base_log = f"El rackeo {picking.name} ha sido completado."
                elif p_type_code == 'incoming':
                    base_log = f"Se ha ejecutado la recepción {picking.name}."
                elif "Pick" in p_type_name:
                    base_log = f"Se ha ejecutado el pick {picking.name}."
                elif "Pack" in p_type_name:
                    base_log = f"Se ha ejecutado el pack {picking.name}."
                elif p_type_code == 'outgoing':
                    base_log = f"Se ha ejecutado el out {picking.name}, despacho completado."
                else:
                    base_log = f"Operación {picking.name} completada."
                log_msg = f"{base_log} {detail_header}"
            
            elif type_of_log == "backorder":
                log_msg = f"Backorder creada para {picking.name}. {detail_header}"
            
            else:
                log_msg = f"{message} {detail_header}" if message else detail_header

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