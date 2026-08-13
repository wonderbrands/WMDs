# -*- coding: utf-8 -*-
from odoo import http, fields
from odoo.http import request
import traceback
import logging

logger = logging.getLogger(__name__)

class CompactacionController(http.Controller):

    def _is_blocked(self, location):
        if not location:
            return False
        if hasattr(location, 'is_location_blocked') and location.is_location_blocked():
            return True
        if location.block_reason:
            return True
        if location.complete_name and any(kw in location.complete_name.lower() for kw in ['bloquead', 'bloqueo']):
            return True
        return False

    @http.route('/wmds/v2/engine/compactacion/create_picking', type='json', auth='user', methods=['POST'], csrf=True)
    def create_picking(self, **kw):
        try:
            operator_email = kw.get('operator_email')
            operator_user = request.env['res.users'].sudo().search([('login', '=', operator_email)], limit=1) if operator_email else request.env.user

            # Search picking type for Compactación
            picking_type = request.env['stock.picking.type'].sudo().search([
                ('name', 'ilike', 'Compactación')
            ], limit=1)
            if not picking_type:
                picking_type = request.env['stock.picking.type'].sudo().search([
                    ('code', '=', 'internal')
                ], limit=1)

            if not picking_type:
                return {"status": "error", "message": "No se encontró un tipo de operación de traslado interno para Compactación."}

            default_src = picking_type.default_location_src_id.id or request.env.ref('stock.stock_location_stock').id
            default_dest = picking_type.default_location_dest_id.id or request.env.ref('stock.stock_location_stock').id

            picking = request.env['stock.picking'].sudo().create({
                'picking_type_id': picking_type.id,
                'location_id': default_src,
                'location_dest_id': default_dest,
                'operator': operator_user.id,
                'state': 'draft',
            })

            # Create an initial log
            log_msg = f"Inicio de Compactación creada por operador {operator_user.name}."
            request.env['wmds.log'].sudo().create({
                'pick': picking.id,
                'log': log_msg,
                'user': request.env.user.id
            })

            return {
                "status": "ok",
                "picking_id": picking.id,
                "picking_name": picking.name
            }
        except Exception as e:
            logger.error(traceback.format_exc())
            return {"status": "error", "message": str(e)}

    @http.route('/wmds/v2/engine/compactacion/validate_origin_location', type='json', auth='user', methods=['POST'], csrf=True)
    def validate_origin_location(self, **kw):
        try:
            location_barcode = kw.get('location_barcode', '').strip()
            if not location_barcode:
                return {"status": "error", "message": "Código de ubicación vacío."}

            location = request.env['stock.location'].sudo().search([('barcode', '=', location_barcode)], limit=1)
            if not location:
                location = request.env['stock.location'].sudo().search([('name', '=', location_barcode)], limit=1)

            if not location:
                return {"status": "error", "message": f"Ubicación '{location_barcode}' no encontrada."}

            # Constraint: No permitir ubicaciones bloqueadas
            if self._is_blocked(location):
                return {"status": "error", "message": "La ubicación de origen está bloqueada."}

            # Constraint: No compactar lo reservado
            # We search quants in this location with quantity > 0
            quants = request.env['stock.quant'].sudo().search([
                ('location_id', '=', location.id),
                ('quantity', '>', 0)
            ])

            if not quants:
                return {"status": "error", "message": "La ubicación de origen no tiene stock disponible."}

            # If any product has reservations, show warning and restrict
            if any(q.reserved_quantity > 0 for q in quants):
                return {
                    "status": "error",
                    "message": "Tienes stock reservado; no se pueden tomar piezas de esa posición."
                }

            products = []
            for q in quants:
                products.append({
                    "product_id": q.product_id.id,
                    "product_name": q.product_id.display_name,
                    "sku": q.product_id.default_code or '---',
                    "barcode": q.product_id.barcode or '',
                    "qty_available": q.quantity
                })

            return {
                "status": "ok",
                "location_id": location.id,
                "location_name": location.display_name,
                "products": products
            }
        except Exception as e:
            logger.error(traceback.format_exc())
            return {"status": "error", "message": str(e)}

    @http.route('/wmds/v2/engine/compactacion/add_location_lines', type='json', auth='user', methods=['POST'], csrf=True)
    def add_location_lines(self, **kw):
        try:
            picking_id = int(kw.get('picking_id'))
            location_src_id = int(kw.get('location_src_id'))
            lines = kw.get('lines', [])

            picking = request.env['stock.picking'].sudo().browse(picking_id)
            if not picking.exists():
                return {"status": "error", "message": "Operación de Compactación no encontrada."}

            location_src = request.env['stock.location'].sudo().browse(location_src_id)
            if not location_src.exists():
                return {"status": "error", "message": "Ubicación de origen no encontrada."}

            # Safety check: Blocked location or reserved stock in origin
            if self._is_blocked(location_src):
                return {"status": "error", "message": "La ubicación de origen está bloqueada."}

            quants = request.env['stock.quant'].sudo().search([
                ('location_id', '=', location_src.id),
                ('quantity', '>', 0)
            ])
            if any(q.reserved_quantity > 0 for q in quants):
                return {"status": "error", "message": "Tienes stock reservado; no se pueden tomar piezas de esa posición."}

            # Create moves and attempt reservation
            created_moves = request.env['stock.move'].sudo()
            for line in lines:
                product_id = int(line.get('product_id'))
                qty = float(line.get('qty', 0.0))
                if qty <= 0:
                    continue

                product = request.env['product.product'].sudo().browse(product_id)
                if not product.exists():
                    return {"status": "error", "message": f"Producto ID {product_id} no encontrado."}

                # Check if enough stock exists in source
                product_quant = quants.filtered(lambda q: q.product_id.id == product.id)
                available_qty = sum(product_quant.mapped('quantity'))
                if qty > available_qty:
                    return {"status": "error", "message": f"Cantidad solicitada ({qty}) supera el stock disponible ({available_qty}) de {product.display_name}."}

                move = request.env['stock.move'].sudo().create({
                    'name': f"Compactación: {product.display_name}",
                    'picking_id': picking.id,
                    'product_id': product.id,
                    'product_uom_qty': qty,
                    'product_uom': product.uom_id.id,
                    'location_id': location_src.id,
                    'location_dest_id': picking.location_dest_id.id,
                })
                created_moves |= move

            # Confirm and assign (reserve) the moves
            created_moves._action_confirm()
            created_moves._action_assign()

            # Verify that all moves were successfully reserved
            for move in created_moves:
                reserved_qty = sum(move.move_line_ids.mapped('quantity'))
                if reserved_qty < move.product_uom_qty:
                    # Reservation failed! Clean up all created moves to release resources
                    created_moves._action_cancel()
                    created_moves.unlink()
                    return {
                        "status": "error",
                        "message": f"No se pudo reservar el stock de {move.product_id.display_name}. Posiblemente ya reservado por otra operación."
                    }

            # Log location closure and reservation
            log_msg = f"Ubicación de origen {location_src.display_name} confirmada y cerrada. Reservados {len(created_moves)} productos."
            request.env['wmds.log'].sudo().create({
                'pick': picking.id,
                'log': log_msg,
                'user': request.env.user.id
            })

            return {"status": "ok"}
        except Exception as e:
            logger.error(traceback.format_exc())
            return {"status": "error", "message": str(e)}

    @http.route('/wmds/v2/engine/compactacion/validate_destination_location', type='json', auth='user', methods=['POST'], csrf=True)
    def validate_destination_location(self, **kw):
        try:
            location_barcode = kw.get('location_barcode', '').strip()
            if not location_barcode:
                return {"status": "error", "message": "Código de ubicación destino vacío."}

            location = request.env['stock.location'].sudo().search([('barcode', '=', location_barcode)], limit=1)
            if not location:
                location = request.env['stock.location'].sudo().search([('name', '=', location_barcode)], limit=1)

            if not location:
                return {"status": "error", "message": f"Ubicación destino '{location_barcode}' no encontrada."}

            # Constraint: No permitir ubicación destino bloqueada
            if self._is_blocked(location):
                return {"status": "error", "message": "La ubicación destino está bloqueada."}

            # Note: Destination can have reservations, restriction does not apply.
            return {
                "status": "ok",
                "location_id": location.id,
                "location_name": location.display_name
            }
        except Exception as e:
            logger.error(traceback.format_exc())
            return {"status": "error", "message": str(e)}

    @http.route('/wmds/v2/engine/compactacion/validate_picking', type='json', auth='user', methods=['POST'], csrf=True)
    def validate_picking(self, **kw):
        try:
            picking_id = int(kw.get('picking_id'))
            location_dest_id = int(kw.get('location_dest_id'))
            operator_email = kw.get('operator_email')

            picking = request.env['stock.picking'].sudo().browse(picking_id)
            if not picking.exists():
                return {"status": "error", "message": "Operación de Compactación no encontrada."}

            location_dest = request.env['stock.location'].sudo().browse(location_dest_id)
            if not location_dest.exists():
                return {"status": "error", "message": "Ubicación destino no encontrada."}

            if self._is_blocked(location_dest):
                return {"status": "error", "message": "La ubicación destino está bloqueada."}

            # Update picking and moves destination
            picking.write({'location_dest_id': location_dest.id})
            picking.move_ids.write({'location_dest_id': location_dest.id})
            picking.move_line_ids.write({'location_dest_id': location_dest.id})

            # Ensure all move lines are marked as picked and quantities match
            for line in picking.move_line_ids:
                line.write({
                    'wmds_picked_qty': line.quantity or line.move_id.product_uom_qty,
                    'picked': True,
                    'quantity': line.quantity or line.move_id.product_uom_qty
                })

            # Validate picking
            res = picking.button_validate()

            log_msg = f"Compactación finalizada con éxito. Destino: {location_dest.display_name}."
            request.env['wmds.log'].sudo().create({
                'pick': picking.id,
                'log': log_msg,
                'user': request.env.user.id
            })

            return {
                "status": "ok",
                "message": "Compactación completada exitosamente."
            }
        except Exception as e:
            logger.error(traceback.format_exc())
            return {"status": "error", "message": f"Error al validar Compactación: {str(e)}"}
