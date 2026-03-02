from odoo import http, fields
from odoo.http import request
import traceback
import logging

_logger = logging.getLogger(__name__)

class Dispatch(http.Controller):

    @http.route('/wmds/v2/engine/post/dispatch_packet', type='json', auth='user', methods=['POST'], csrf=True)
    def dispatch_packet(self, **kw):
        try:
            packs_ids = kw.get("picks_ids", []) 
            operator_login = kw.get("operator_login")

            if not packs_ids:
                return {"status": "error", "message": "No hay guías para procesar"}

            operator = request.env["res.users"].sudo().search([('login', '=', operator_login)], limit=1)
            user_id = operator.id if operator else request.env.user.id

            attachments = request.env["sale.order.attachment"].sudo().search([
                ('display_name_custom', 'in', packs_ids)
            ])
            
            attachments.write({'dispatched': True})
            sale_orders = attachments.mapped('so_id')
            
            missing_packs_global = []

            for so in sale_orders:
                pending = so.attachments.filtered(lambda a: not a.dispatched)
                if pending:
                    missing_packs_global.extend(pending.mapped('display_name_custom'))
                else:
                    pickings = request.env['stock.picking'].sudo().search([
                        ('sale_id', '=', so.id),
                        ('picking_type_id.name', '=', 'Órdenes de entrega'),
                        ('state', 'not in', ['done', 'cancel'])
                    ])
                    for picking in pickings:
                        try:
                            picking.action_assign()
                            picking.button_validate()
                        except Exception as e:
                            _logger.error(f"Error validando picking {picking.name}: {e}")

                request.env['wmds.log'].sudo().create({
                    'sale': so.id,
                    'log': f"Paquetes entregados a paquetería por {operator_login}.",
                    'user': user_id,
                    'date': fields.Datetime.now(),
                })

            res = {"status": "success"}
            if missing_packs_global:
                res["warning"] = f"Atención: Faltan paquetes por entregar de estas órdenes: {', '.join(missing_packs_global)}"
            
            return res

        except Exception as e:
            return {"status": "error", "message": str(e)}