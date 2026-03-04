from odoo import http
from odoo.http import request
from datetime import datetime
import traceback

class LogStockRecord(http.Controller):

    @http.route(
        '/wmds/v2/engine/post/log_stock_record',
        type='json',
        auth='user',
        methods=['POST'],
        csrf=True
    )
    def log_stock_record(self, **kw):
        params = kw.get('params', kw)
        pick_id = params.get('pick_id')
        pick_name = params.get('pick_name')
        operator_mail = params.get('operator_mail')
        message = params.get('message')
        type_of_log = params.get('type')

        operator_id = request.env['res.users'].sudo().search([('login', '=', operator_mail)], limit=1)
        
        picking = request.env['stock.picking'].sudo()
        if pick_id:
            picking = picking.browse(int(pick_id))
        elif pick_name:
            picking = picking.search([('name', '=', pick_name)], limit=1)

        if not picking:
            return {"error": "Picking no encontrado"}

        product_list = "\n".join([f"- {m.product_id.display_name}: {m.quantity_done or m.product_uom_qty}" for m in picking.move_ids])
        location_dest = picking.location_dest_id.name
        
        detail_header = f"Hacia la ubicación {location_dest}, se han trasladado los siguientes productos:\n{product_list}"

        if type_of_log == "external":
            log_vals = {
                'user': operator_id.id if operator_id else False,
                'date': datetime.now(),
                'pick': picking.id
            }
            
            base_log = ""
            p_type = picking.picking_type_id.name
            
            if p_type == "Storage":
                base_log = f"El rackeo {picking.name} ha sido completado."
            elif p_type == "Recepciones":
                base_log = f"Se ha ejecutado la recepción {picking.name}."
            elif p_type == "Pick":
                base_log = f"Se ha ejecutado el pick {picking.name}."
            elif p_type == "Pack":
                base_log = f"Se ha ejecutado el pack {picking.name}."
            elif p_type == "Órdenes de entrega":
                base_log = f"Se ha ejecutado el out {picking.name}, despacho completado."

            log_vals['log'] = f"{base_log}\n\n{detail_header}"
            request.env["wmds.log"].sudo().create(log_vals)
            return {"saved": True}

        elif type_of_log == "backorder":
            request.env["wmds.log"].sudo().create({
                'user': operator_id.id if operator_id else False,
                'log': f"Backorder creada para {picking.name}.\n\n{detail_header}",
                'pick': picking.id,
                'date': datetime.now()
            })
            return {"saved": True}

        else:
            try:
                final_msg = f"{message}\n\n{detail_header}" if message else detail_header
                request.env["wmds.log"].sudo().create({
                    'log': final_msg,
                    'user': operator_id.id if operator_id else False,
                    'date': datetime.now(),
                    'pick': picking.id
                })
                return {"saved": True}
            except Exception as e:
                return {"error": f"{str(e)}\n{traceback.format_exc()}"}

    @http.route(
        '/wmds/v2/engine/post/change_wmds_status',
        type='json',
        auth='user',
        methods=['POST'],
        csrf=True
    )
    def change_wmds_status(self, **kw):
        params = kw.get('params', kw)
        pick_id = params.get('pick_id')
        pick_name = params.get('pick_name')
        status = params.get('status')

        try:
            picking = request.env['stock.picking'].sudo()
            if pick_id:
                picking = picking.search([('id', '=', pick_id)], limit=1)
            elif pick_name:
                picking = picking.search([('name', '=', pick_name)], limit=1)
            
            if picking:
                status_rec = request.env['wmds.stock.status'].sudo().search([('value', '=', status)], limit=1)
                picking.wmds_status = status_rec.id
                return {"saved": True}
            return {"error": "Picking no encontrado"}
        except Exception as e:
            return {"error": f"{str(e)}\n{traceback.format_exc()}"}