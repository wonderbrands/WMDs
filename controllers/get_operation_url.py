
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
        '/wmds/v2/engine/get/pick-url',
        type='json',
        auth='user',
        methods=['POST'],
        csrf=True
    )
    def get_pick_url(self, **kw):
        try:
            pick_id = kw.get('pick_id')
            action_id = request.env['ir.actions.actions'].sudo().search(
                [
                    (
                        'name', '=', 'Acción del cliente de recolección de código de barras'
                    )
                ], 
                limit=1
            )

            if not pick_id or not action_id:
                return {
                    "error": "Bad request",
                    "message": "Missing required field: pick_id or action_id"
                }

            url = f"https://wonderbrands2026-v2-26809106.dev.odoo.com/odoo/barcode/{pick_id}/action-{action_id.id}"
            return {
                "url": url
            }
            
        except:
            return {
                "error": f"{str(e)}\n{traceback.format_exc()}"
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

            url = f"https://wonderbrands2026-v2-26809106.dev.odoo.com/odoo/action-{action_id.id}"
            return {
                "url": url
            }
            
        except:
            return {
                "error": f"{str(e)}\n{traceback.format_exc()}"
            }