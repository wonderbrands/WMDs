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
        decision = params.get('decision') # CREATE o CANCELLED

        # Refactor: Búsqueda de usuario común para todos los casos
        operator_id = request.env['res.users'].sudo().search([('login', '=', operator_mail)], limit=1)
        
        # Búsqueda del picking principal
        picking = request.env['stock.picking'].sudo()
        if pick_id:
            picking = picking.browse(int(pick_id))
        elif pick_name:
            picking = picking.search([('name', '=', pick_name)], limit=1)

        if not picking:
            return {"error": "Picking no encontrado"}

        # --- CASO 1: EXTERNAL (Lógica original intacta) ---
        if type_of_log == "external":
            log_vals = {
                'user': operator_id.id if operator_id else False,
                'date': datetime.now(),
            }
            
            # Determinamos origen segun el tipo
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

        # --- CASO 2: BACKORDER (Nueva Lógica) ---
        elif type_of_log == "backorder":
            try:
                if decision == "CREATE":
                    # Buscamos el pick hijo (el nuevo backorder)
                    backorder_hijo = request.env['stock.picking'].sudo().search([
                        ('backorder_id', '=', picking.id)
                    ], order='id desc', limit=1)

                    # Log en el VIEJO (Padre)
                    picking.wmds_log.create({
                        'log': f"No se validaron todos los productos. Se creó backorder: {backorder_hijo.name if backorder_hijo else 'Pendiente'}",
                        'user': operator_id.id,
                        'date': datetime.now(),
                        'pick': picking.id
                    })

                    # Log en el NUEVO (Hijo)
                    if backorder_hijo:
                        backorder_hijo.wmds_log.create({
                            'log': f"Creado desde {picking.name} por validación parcial.",
                            'user': operator_id.id,
                            'date': datetime.now(),
                            'pick': backorder_hijo.id
                        })
                
                else: # Decision CANCELLED
                    picking.wmds_log.create({
                        'log': "Validación parcial: El usuario decidió NO crear backorder (cantidades restantes canceladas).",
                        'user': operator_id.id,
                        'date': datetime.now(),
                        'pick': picking.id
                    })
                return {"saved": True}
            except Exception as e:
                return {"error": str(e)}

        # --- CASO 3: GENERICO (Original) ---
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
    
