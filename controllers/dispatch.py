from odoo import http, fields
from odoo.http import request
import logging

_logger = logging.getLogger(__name__)

class Dispatch(http.Controller):

    @http.route('/wmds/v2/engine/get/pending_full_dispatch', type='json', auth='user', methods=['POST'], csrf=True)
    def get_pending_full_dispatch(self, **kw):
        try:
            moves = request.env["stock.move"].sudo().search([
                ('on_dock', '=', True),
                ('dispatched', '=', False)
            ])
            
            res = []
            for move in moves:
                res.append({
                    "id": move.id,
                    "product": move.product_id.display_name,
                    "qty": move.qty_remaining,
                    "total_qty": move.quantity,
                    "origin": move.picking_id.origin or move.picking_id.name,
                    "dock": move.dock_id.name
                })
            return res
        except Exception as e:
            return {"error": str(e)}

    @http.route('/wmds/v2/engine/post/dispatch_full_items', type='json', auth='user', methods=['POST'], csrf=True)
    def dispatch_full_items(self, **kw):
        try:
            items = kw.get("items", []) # List of {move_id, qty}
            operator_login = kw.get("operator_login")
            
            operator = False
            if operator_login:
                operator = request.env["res.users"].sudo().search([('login', '=ilike', str(operator_login).strip())], limit=1)
            user_id = operator.id if operator else request.env.user.id

            for item in items:
                move = request.env["stock.move"].sudo().browse(item['move_id'])
                if not move.exists():
                    continue
                
                qty_to_dispatch = item['qty']
                if qty_to_dispatch <= 0:
                    continue
                
                # Check if we are over-dispatching
                if qty_to_dispatch > move.qty_remaining:
                    qty_to_dispatch = move.qty_remaining
                
                new_qty_dispatched = move.qty_dispatched + qty_to_dispatch
                
                move_vals = {
                    'qty_dispatched': new_qty_dispatched,
                }
                
                if new_qty_dispatched >= move.quantity:
                    move_vals.update({
                        'dispatched': True,
                        'on_dock': False,
                        'dock_id': False
                    })
                
                move.write(move_vals)
                
                log_msg = f"Despacho parcial: {qty_to_dispatch} de {move.product_id.display_name} (Origen: {move.picking_id.name}) entregado a paquetería por {operator_login}."
                if move.dispatched:
                    log_msg = f"Despacho total: {move.product_id.display_name} (Origen: {move.picking_id.name}) entregado a paquetería por {operator_login}."
                
                # Log en picking
                request.env['wmds.log'].sudo().create({
                    'pick': move.picking_id.id,
                    'log': log_msg,
                    'user': user_id,
                    'date': fields.Datetime.now(),
                })
                
                # Note: wmds.log.create override will automatically propagate this to the batch if pick has one.

            return {"status": "success"}
        except Exception as e:
            _logger.error(f"Error en dispatch_full_items: {e}")
            return {"status": "error", "message": str(e)}

    @http.route('/wmds/v2/engine/post/dispatch_packet', type='json', auth='user', methods=['POST'], csrf=True)
    def dispatch_packet(self, **kw):
        try:
            packs_ids = kw.get("picks_ids", []) 
            operator_login = kw.get("operator_login")

            _logger.info("Inicio de dispatch_packet")

            if not packs_ids:
                _logger.info("Validacion fallida: sin guias")
                return {"status": "error", "message": "No hay guías para procesar"}

            if len(packs_ids) > 10:
                import json
                task = request.env['wmds.queued_tasks'].sudo().create({
                    'task_type': 'dispatch_package',
                    'params': json.dumps(kw),
                    'operator_login': operator_login or '',
                    'status': 'pending',
                })
                task._trigger_async_process()
                return {
                    "status": "queued",
                    "queued_task_id": task.id,
                    "message": f"Debido al número de paquetes ({len(packs_ids)}), la tarea se ha encolado en segundo plano."
                }

            operator = False
            if operator_login:
                operator = request.env["res.users"].sudo().search([('login', '=ilike', str(operator_login).strip())], limit=1)
            user_id = operator.id if operator else request.env.user.id

            _logger.info(f"Usuario asignado: {user_id}")

            ei_tags = request.env["sale.order.ei"].sudo().search([
                ('display_name_custom', 'in', packs_ids)
            ])

            # Pre-check for cancelled orders
            cancelled_sos = ei_tags.mapped('so_id').filtered(lambda s: s.state == 'cancel')
            if cancelled_sos:
                so_names = ", ".join(cancelled_sos.mapped('name'))
                return {
                    "status": "error", 
                    "message": f"No se puede despachar: Los pedidos {so_names} están cancelados."
                }
            
            ei_tags.write({
                'dispatched': True,
                'on_dock': False,
                'dock_id': False
            })
            _logger.info("EI tags actualizados a dispatched y removidos de DOCK")
            
            for tag in ei_tags:
                log_msg = f"Paquete {tag.display_name_custom} entregado a paquetería por {operator_login}."
                
                # Log en Picking
                picking = request.env['stock.picking'].sudo().search([
                    ('sale_id', '=', tag.so_id.id),
                    ('state', 'in', ['assigned', 'done']),
                    ('picking_type_id.name', 'ilike', 'Pick')
                ], order='date_done desc', limit=1)
                
                if picking:
                    request.env["wmds.log"].sudo().create({
                        "pick": picking.id,
                        "log": log_msg,
                        "user": user_id,
                    })
                else:
                    # If no picking found (unlikely), log to Sale Order at least
                    request.env['wmds.log'].sudo().create({
                        'sale': tag.so_id.id,
                        'log': log_msg,
                        'user': user_id,
                        'date': fields.Datetime.now(),
                    })
                
                _logger.info(f"Log creado para paquete {tag.display_name_custom}")

            sale_orders = ei_tags.mapped('so_id')
            missing_packs_global = []

            for so in sale_orders:
                # Verificar si faltan etiquetas por despachar según ei_total
                total_ei = so.ei_total
                dispatched_ei_count = request.env['sale.order.ei'].sudo().search_count([
                    ('so_id', '=', so.id),
                    ('dispatched', '=', True)
                ])
                
                if dispatched_ei_count < total_ei:
                    # Encontrar cuáles faltan (secuencias)
                    existing_seqs = request.env['sale.order.ei'].sudo().search([
                        ('so_id', '=', so.id),
                        ('dispatched', '=', True)
                    ]).mapped('sequence_number')
                    
                    missing_seqs = [str(i) for i in range(1, total_ei + 1) if i not in existing_seqs]
                    missing_packs_global.append(f"{so.name} (Faltan: {', '.join(missing_seqs)})")
                    _logger.info(f"Faltan paquetes para SO {so.id}")
                else:
                    # Si ya están todos, procesar pickings
                    pickings = request.env['stock.picking'].sudo().search([
                        ('sale_id', '=', so.id),
                        '|',
                        ('picking_type_id.code', '=', 'outgoing'),
                        ('picking_type_id.name', 'in', ['Órdenes de entrega', 'Delivery Orders']),
                        ('state', 'not in', ['done', 'cancel'])
                    ])
                    
                    # Log on Sale Order that all packages have been dispatched
                    request.env['wmds.log'].sudo().create({
                        'sale': so.id,
                        'log': "Pedido totalmente despachado. Cerrando transferencias de salida (OUT).",
                        'user': user_id,
                        'date': fields.Datetime.now(),
                    })
                    
                    for picking in pickings:
                        try:
                            picking.action_assign()
                            
                            # Pre-llenar cantidades realizadas para evitar wizard de cantidades vacías
                            for move in picking.move_ids:
                                if move.state not in ('done', 'cancel'):
                                    move.write({
                                        'quantity': move.product_uom_qty,
                                        'picked': True
                                    })
                            
                            res = picking.button_validate()
                            if isinstance(res, dict) and res.get('res_model') == 'stock.backorder.confirmation':
                                wizard = request.env['stock.backorder.confirmation'].with_context(res['context']).sudo().create({
                                    'pick_ids': [(4, picking.id)]
                                })
                                wizard.process()
                                
                            # Log on the OUT picking
                            request.env['wmds.log'].sudo().create({
                                'pick': picking.id,
                                'log': f"Salida ({picking.name}) validada automáticamente por despacho completo.",
                                'user': user_id,
                                'date': fields.Datetime.now(),
                            })
                            
                            _logger.info(f"Picking {picking.name} validado")
                        except Exception as e:
                            _logger.error(f"Error validando picking {picking.name}: {e}")

            res = {"status": "success"}
            if missing_packs_global:
                res["warning"] = f"Atención: Faltan paquetes por entregar de estas órdenes: {', '.join(missing_packs_global)}"
            
            _logger.info("Fin de dispatch_packet")
            return res

        except Exception as e:
            _logger.error(f"Excepcion: {e}")
            return {"status": "error", "message": str(e)}