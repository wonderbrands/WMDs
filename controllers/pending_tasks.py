from odoo import http
from odoo.http import request
import traceback
import logging

logger = logging.getLogger(__name__)

class PendingTasks(http.Controller):

    @http.route(
        '/wmds/v2/engine/get/pending_tasks',
        type='json',
        auth='user',
        methods=['POST'],
        csrf=True
    )
    def get_pending_tasks(self, **kw):
        try:
            task = kw.get('task')
            email = kw.get('email')

            map_task = {
                "picks": "Pick",
                "ingresos": "Recepciones",
                "acomodo": "Storage",
                "pack": "Pack"
            }

            if task=="batch_pick":
                pending_tasks = request.env['stock.picking.batch'].sudo().search([
                    ('state', '=', 'in_progress'),
                    ('operator.login', '=', email)
                ])

            else:
                fields = [
                    ('picking_type_id.name', '=', map_task[task]),
                    ('state', '=', 'assigned'),
                ]

                if task not in ["acomodo"]:
                    fields.append(('operator.login', '=', email))

                pending_tasks = request.env['stock.picking'].sudo().search(fields)


            return [
                {
                    "key": task.id,
                    "label": task.name,
                    "data": task.name
                } for task in pending_tasks
            ] 
        except Exception as e:
            return {
                "error": f"{str(e)}\n{traceback.format_exc()}"
            }