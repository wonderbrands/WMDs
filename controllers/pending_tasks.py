from odoo import http, fields
from odoo.http import request
import logging

_logger = logging.getLogger(__name__)


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
            client_tz = kw.get('tz')

            env = request.env
            if client_tz:
                env = env(context=dict(env.context, tz=client_tz))

            map_task = {
                "picks": "Pick",
                "ingresos": "Recepciones",
                "acomodo": "Storage",
                "pack": "Pack"
            }

            if task == "batch_pick":
                pending_tasks = env['stock.picking.batch'].sudo().search([
                    ('state', '=', 'in_progress'),
                    ('operator.login', '=', email)
                ])

            else:
                search_domain = [
                    ('picking_type_id.name', '=', map_task[task]),
                    ('state', '=', 'assigned'),
                ]

                if task not in ["acomodo", "ingresos"]:
                    search_domain.append(('operator.login', '=', email))


                pending_tasks = env['stock.picking'].sudo().search(search_domain)
            
            result = []
            for record in pending_tasks:
                
                source_doc = getattr(record, 'origin', False)
                
                if source_doc:
                    label = f"{record.name} - {source_doc}"
                else:
                    label = record.name

                scheduled_date_tz = False
                if record.scheduled_date:
                    scheduled_date_tz = fields.Datetime.context_timestamp(record, record.scheduled_date).strftime('%Y-%m-%d %H:%M:%S')

                sale = env['sale.order'].sudo().search([
                    ('name', '=', source_doc),
                ])
                carrier = None if not sale else sale.data_carrier_selection_relational.name

                #manage if the movement is a pack
                #if so, get the pick and get the batch it was part of 
                if task == "pack":
                    pick = sale.picking_ids.filtered(lambda pick: "PICK" in pick.name)
                    if len(pick)>0:
                        batch = pick.batch_id
                        batch_name = None if not batch else batch.name

                result.append({
                    "key": record.id,
                    "label": label,
                    "data": record.name,
                    "pick": record.name,
                    "origin": source_doc,
                    "date": scheduled_date_tz,
                    "carrier": carrier,
                    "batch": None if not batch_name else batch_name
                })
            
            return result
        except Exception as e:
            return {"error": str(e)}