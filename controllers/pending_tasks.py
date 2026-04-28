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
                "pack": "Pack",
                "reabastecimiento": "Reabastecimiento",
                "dispatch_ful": "Resurtido a Ful: Despacho",
                "devoluciones": "Devolucion",
            }

            if task == "batch_pick":
                pending_tasks = env['stock.picking.batch'].sudo().search([
                    ('state', '=', 'in_progress'),
                    ('operator.login', '=', email)
                ], order='write_date desc', limit=20)

            else:
                search_domain = [
                    ('state', '=', 'assigned'),
                ]

                if task == "acomodo":
                    search_domain.append('|')
                    search_domain.append(('picking_type_id.name', 'ilike', 'Storage'))
                    search_domain.append(('picking_type_id.name', 'ilike', 'Rackeo'))
                else:
                    search_domain.append(('picking_type_id.name', 'ilike', map_task[task]))

                if task not in ["acomodo", "ingresos"]:
                    search_domain.append(('operator.login', '=', email))
                else:
                    search_domain.append('|')
                    search_domain.append(('operator', '=', False))
                    search_domain.append(('operator.login', '=', email))

                pending_tasks = env['stock.picking'].sudo().search(search_domain, order='scheduled_date desc, id desc', limit=30)
            
            result = []
            for record in pending_tasks:
                batch_name = None
                source_doc = getattr(record, 'origin', False)
                carrier = None
                
                if source_doc:
                    label = f"{record.name} - {source_doc}"
                else:
                    label = record.name

                scheduled_date_tz = False
                if record.scheduled_date:
                    scheduled_date_tz = fields.Datetime.context_timestamp(record, record.scheduled_date).strftime('%Y-%m-%d %H:%M:%S')

                # manage if the movement is a pack
                # if so, get the pick and get the batch it was part of 
                if task == "pack":
                    sale = env['sale.order'].sudo().search([
                        ('name', '=', source_doc),
                    ], limit=1)
                    if sale:
                        carrier = sale.data_carrier_selection_relational.name
                        pick = sale.picking_ids.filtered(lambda p: "PICK" in p.name)
                        if pick:
                            batch = pick[0].batch_id
                            batch_name = batch.name if batch else None

                result.append({
                    "key": record.id,
                    "label": label,
                    "data": record.name,
                    "pick": record.name,
                    "origin": source_doc,
                    "date": scheduled_date_tz,
                    "carrier": carrier,
                    "batch": batch_name
                })
            
            return result
        except Exception as e:
            return {"error": str(e)}