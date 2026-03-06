from odoo import http
from odoo.http import request
from datetime import datetime
import traceback

class LogStockRecord(http.Controller):

    @http.route('/wmds/v2/engine/post/log_stock_record', type='json', auth='user', methods=['POST'], csrf=False)
    def log_stock_record(self, **kw):
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
        
        product_list = "; ".join([f"- {m.product_id.display_name}: {m.qty_done if m.qty_done>0 else m.product_uom_qty}" for m in picking.move_line_ids])
        
        p_type_name = picking.picking_type_id.name or ""
        p_type_code = picking.picking_type_id.code
        
        is_storage = any(word in p_type_name.lower() for word in ["storage", "rack", "rackeo"])
        
        location_header = ""
        if not is_storage:
            location_header = f"Hacia la ubicación {picking.location_dest_id.name}, "

        detail_header = f"{location_header}se han trasladado los siguientes productos:{product_list}"

        if type_of_log == "external":
            base_log = ""
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

            log_msg = f"{base_log}\n\n{detail_header}"
        
        elif type_of_log == "backorder":
            log_msg = f"Backorder creada para {picking.name}.{detail_header}"
        
        else:
            log_msg = f"{message}\n\n{detail_header}" if message else detail_header

        try:
            request.env["wmds.log"].sudo().create({
                'user': operator_id.id if operator_id else request.env.user.id,
                'date': datetime.now(),
                'pick': picking.id,
                'log': log_msg
            })
            return {"saved": True}
        except Exception as e:
            return {"error": f"{str(e)}\n{traceback.format_exc()}"}

    @http.route('/wmds/v2/engine/post/change_wmds_status', type='json', auth='user', methods=['POST'], csrf=False)
    def change_wmds_status(self, **kw):
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