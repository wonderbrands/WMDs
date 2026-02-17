
#must get an url like this
#https://wonderbrands2026-v2-26809106.dev.odoo.com/odoo/barcode/72/action-508
#where 72 id the id of the operation
#and action-508 the id of the action "Acción del cliente de recolección de código de barras"

from odoo import http
from odoo.http import request
import traceback
import logging

logger = logging.getLogger(__name__)

class GetURLOfPick(http.Controller):

    @http.route(
        '/wmds/v2/engine/get/barcode_url',
        type='json',
        auth='user',
        methods=['POST'],
        csrf=True
    )
    def get_pick_url(self, **kw):
        try:
            pick_name = kw.get('pick_name')
            
            if not pick_name:
                return {
                    "error": "Bad request",
                    "message": "Missing required field: pick_name"
                }

            
            if pick_name.startswith("BATCH"):
                action = request.env.ref('stock_barcode.stock_barcode_batch_picking_client_action', raise_if_not_found=False)
                record = request.env['stock.picking.batch'].sudo().search([('name', '=', pick_name)], limit=1)
                
                if not record:
                    return {"error": "Bad request", "message": "Batch Pick not found"}
            else:
                action = request.env.ref('stock_barcode.stock_barcode_picking_client_action', raise_if_not_found=False)
                record = request.env['stock.picking'].sudo().search([('name', '=', pick_name)], limit=1)
                
                if not record:
                    return {"error": "Bad request", "message": "Pick not found"}

            if not action:
                return {"error": "Internal Error", "message": "Barcode Client Action not found in system"}

            url = f"/odoo/barcode/{record.id}/action-{action.id}"

            return {"url": url}
            
        except Exception as e:
            logger.error(traceback.format_exc())
            return {
                "error": "Internal Server Error",
                "message": str(e)
            }    

    @http.route(
        '/wmds/v2/engine/get/wmds-url',
        type='json',
        auth='user',
        methods=['POST'],
        csrf=True
    )
    def get_wmds_url(self, **kw):
        try:
            action_id = request.env['ir.actions.actions'].sudo().search(
                [
                    (
                        'name', '=', 'WMDs'
                    )
                ], 
                limit=1
            )

            if not action_id:
                return {
                    "error": "Bad request",
                    "message": "Missing required field: pick_id or action_id"
                }

            url = f"/odoo/action-{action_id.id}"
            return {
                "url": url
            }
            
        except:
            return {
                "error": f"{str(e)}\n{traceback.format_exc()}"
            }