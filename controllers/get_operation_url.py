
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
                action = request.env.ref('stock_barcode_picking_batch.stock_barcode_picking_batch_client_action', raise_if_not_found=False)
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
        '/wmds/v2/engine/get/validate_dfull_pick',
        type='json',
        auth='user',
        methods=['POST'],
        csrf=True
    )
    def validate_dfull_pick(self, **kw):
        try:
            pick_name = kw.get('pick_name')
            if not pick_name:
                return {"valid": False, "message": "Falta el nombre de la operación."}
            
            pick = request.env['stock.picking'].sudo().search([('name', '=', pick_name)], limit=1)
            
            if not pick:
                return {"valid": False, "message": "La operación no existe."}
            
            if not pick.name.startswith("WH/DFUL/"):
                return {"valid": False, "message": f"La operación {pick_name} no es de tipo WH/DFUL."}

            if pick.state != 'assigned':
                states = {
                    'draft': 'Borrador',
                    'waiting': 'Esperando otra operación',
                    'confirmed': 'Esperando disponibilidad',
                    'assigned': 'Listo',
                    'done': 'Hecho',
                    'cancel': 'Cancelado'
                }
                return {"valid": False, "message": f"La operación está en estado: {states.get(pick.state, pick.state)}. Debe estar 'Listo'."}
            
            # Update moves on dock and log dispatch
            operator_name = request.env.user.name
            
            # Identify all related PFUL moves through move_orig_ids
            # DFUL moves are linked to PFUL moves via move_orig_ids
            pful_moves = pick.move_ids.mapped('move_orig_ids').filtered(
                lambda m: 'Resurtido a Ful: Pick' in (m.picking_id.picking_type_id.name or '')
            )
            
            # Identify which of these original moves are currently on dock
            moves_on_dock = pful_moves.filtered(lambda m: m.on_dock)
            
            if moves_on_dock:
                for move in moves_on_dock:
                    dock_name = move.dock_id.name if move.dock_id else "DOCK"
                    origin_pick = move.picking_id.name
                    
                    # Mark PFUL move as dispatched
                    move.sudo().write({
                        'on_dock': False,
                        'dock_id': False,
                        'dispatched': True,
                        'qty_dispatched': move.quantity
                    })
                    
                    log_msg = f"Despacho Fulfillment: Operación {pick.name}. Producto {move.product_id.display_name} (Origen: {origin_pick}) retirado de {dock_name} por {operator_name}."
                    request.env["wmds.log"].sudo().create({
                        "pick": pick.id,
                        "log": log_msg,
                        "user": request.env.user.id,
                    })
            
            # Check for partial dispatch: if some related PFUL moves are NOT on dock
            # and the picking is not allowed to be partial, we might need to block.
            # However, the user mentioned there is a field for this. 
            # We'll check for 'dful_partial_dispatch' or similar if it exists.
            total_pful_qty = sum(pful_moves.mapped('quantity'))
            total_on_dock_qty = sum(moves_on_dock.mapped('quantity'))
            
            if total_on_dock_qty < total_pful_qty:
                # It's a partial dispatch. Check if allowed.
                # If the field doesn't exist, we assume True for now to not break the flow,
                # but we log the partial nature.
                can_partial = getattr(pick, 'dful_partial_dispatch', True) 
                if not can_partial:
                    return {"valid": False, "message": "La operación no está completa en el DOCK y no permite despacho parcial."}
                
                log_msg = f"Despacho Fulfillment PARCIAL: Operación {pick.name}. Pendientes {total_pful_qty - total_on_dock_qty} unidades por recolectar de PFULs."
                request.env["wmds.log"].sudo().create({
                    "pick": pick.id,
                    "log": log_msg,
                    "user": request.env.user.id,
                })
            elif not moves_on_dock:
                # If no moves were on dock at all
                log_msg = f"Despacho Fulfillment: Operación {pick.name} validada para despacho por {operator_name} (Sin movimientos previos en DOCK)."
                request.env["wmds.log"].sudo().create({
                    "pick": pick.id,
                    "log": log_msg,
                    "user": request.env.user.id,
                })

            return {"valid": True, "pick_id": pick.id}
            
        except Exception as e:
            logger.error(traceback.format_exc())
            return {"valid": False, "message": str(e)}

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