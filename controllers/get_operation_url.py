
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
            action_id = request.env['ir.actions.actions'].sudo().search(
                [
                    (
                        'name', '=', 'Barcode Picking Client Action'
                    )
                ], 
                limit=1
            )

            if not pick_name or not action_id:
                return {
                    "error": "Bad request",
                    "message": "Missing required field: pick_id or action_id"
                }

            if pick_name.startswith("BATCH"):
                barcode_action = request.env['ir.actions.actions'].sudo().search(
                    [
                        (
                            'name', '=', 'Barcode Batch Picking Client Action'
                        )
                    ], 
                    limit=1
                )
                batch_id = request.env['stock.picking.batch'].sudo().search([('name', '=', pick_name)], limit=1).id
                if not batch_id:
                    return {
                        "error": "Bad request",
                        "message": "Pick not found"
                    }
                url = f"/odoo/barcode/{batch_id}/action-{barcode_action}"

            else:
                pick_id = request.env['stock.picking'].sudo().search([('name', '=', pick_name)], limit=1).id
                if not pick_id:
                    return {
                        "error": "Bad request",
                        "message": "Pick not found"
                    }
                url = f"/odoo/barcode/{pick_id}/action-{action_id.id}"

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

            url = f"/odoo/action-{action_id.id}"
            return {
                "url": url
            }
            
        except:
            return {
                "error": f"{str(e)}\n{traceback.format_exc()}"
            }