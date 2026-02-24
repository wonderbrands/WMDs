from odoo import http
from odoo.http import request
import traceback
import logging
from datetime import datetime

logger = logging.getLogger(__name__)



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
        params = kw.get('params', kw)  # Soporte para JSON-RPC estándar
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

        if type_of_log == "external":
            log_vals = {
                'user': operator_id.id if operator_id else False,
                'date': datetime.now(),
            }
            
            if picking.picking_type_id.name == "Storage":
                po = request.env["purchase.order"].sudo().search([('name', '=', picking.origin)], limit=1)
                log_vals.update({'log': f"El acomodo {picking.name} ha sido completado", 'purchase': po.id if po else False})
            
            elif picking.picking_type_id.name == "Recepciones":
                po = request.env["purchase.order"].sudo().search([('name', '=', picking.origin)], limit=1)
                log_vals.update({'log': f"Se ha ejecutado la recepción {picking.name}", 'purchase': po.id if po else False})
            
            elif picking.picking_type_id.name == "Pick":
                so = request.env["sale.order"].sudo().search([('name', '=', picking.origin)], limit=1)
                log_vals.update({'log': f"Se ha ejecutado el pick {picking.name}", 'sale': so.id if so else False})

            if log_vals.get('log'):
                request.env["wmds.log"].sudo().create(log_vals)
            return {"saved": True}

        elif type_of_log == "backorder":
            if picking.origin:
                if picking.origin.startswith("P"):
                    orm_origin = request.env["purchase.order"].sudo().search([('name', '=', picking.origin)], limit=1)
                elif picking.origin.startswith("S"):
                    orm_origin = request.env["sale.order"].sudo().search([('name', '=', picking.origin)], limit=1)

                if orm_origin:
                    orm_origin.write({
                        'wmds_log': [(0, 0, {
                            'user': operator_id.id if operator_id else False,
                            'log': f"No se validaron todos los productos del traslado, se ha creado la backorder {picking.name}"
                        })]
                    })

        else:
            try:
                picking.wmds_log.create({
                    'log': message,
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
        pick_id = kw.get('pick_id')
        pick_name = kw.get('pick_name')
        status = kw.get('status')

        try:
            if pick_id:
                picking = request.env['stock.picking'].sudo().search([('id', '=', pick_id)], limit=1)
            if pick_name:
                picking = request.env['stock.picking'].sudo().search([('name', '=', pick_name)], limit=1)
            picking.wmds_status = request.env['wmds.stock.status'].search([('value', '=', status)], limit=1)
            return {
                "saved": True
            }
        except Exception as e:
            return {
                "error": f"{str(e)}\n{traceback.format_exc()}"
            }
    
