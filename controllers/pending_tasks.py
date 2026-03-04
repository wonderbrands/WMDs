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

                if task not in ["acomodo", "ingresos"]:
                    fields.append(('operator.login', '=', email))

                pending_tasks = request.env['stock.picking'].sudo().search(fields)


            result = []
            for record in pending_tasks:
                
                source_doc = getattr(record, 'origin', False)
                
                if source_doc:
                    label = f"{record.name} - {source_doc}"
                else:
                    label = record.name

                result.append({
                    "key": record.id,
                    "label": label,
                    "data": record.name,
                    "pick": record.name,
                    "origin": source_doc,
                    "date": record.scheduled_date
                })

            return result

        except Exception as e:
            return {
                "error": f"{str(e)}\n{traceback.format_exc()}"
            }
        except Exception as e:
            return {
                "error": f"{str(e)}\n{traceback.format_exc()}"
            }