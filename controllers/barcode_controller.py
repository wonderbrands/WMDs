# -*- coding: utf-8 -*-
from odoo import http, fields
from odoo.http import request
import traceback
import logging

logger = logging.getLogger(__name__)

class BarcodeController(http.Controller):

    def _get_record(self, res_id, res_model):
        return request.env[res_model].sudo().browse(int(res_id))

    def _check_status(self, record, operator_email):
        if not record.exists():
            return {"status": "error", "message": "La operación no existe."}
        if record.state == 'cancel':
            return {"status": "error", "message": "Esta operación ha sido cancelada."}
        
        # Check operator assignment
        # Assuming picking and batch models have an 'operator' field which is res.users
        assigned_operator = getattr(record, 'operator', False)
        if assigned_operator and assigned_operator.login != operator_email:
            return {"status": "error", "message": "Esta operación ha sido reasignada a otro operador."}
        
        return {"status": "ok"}

    @http.route('/wmds/v2/barcode/get_operation_data', type='json', auth='user', methods=['POST'], csrf=True)
    def get_operation_data(self, **kw):
        try:
            res_id = kw.get('res_id')
            res_model = kw.get('res_model', 'stock.picking')
            operator_email = kw.get('operator_email')

            record = self._get_record(res_id, res_model)
            status = self._check_status(record, operator_email)
            if status['status'] == 'error':
                return status

            lines_data = []
            if res_model == 'stock.picking':
                lines = record.move_line_ids
            else: # stock.picking.batch
                lines = record.move_line_ids

            for line in lines:
                # En Odoo 19, 'quantity' es el campo principal. 
                # La demanda suele estar en el move, pero en la línea usamos lo reservado o la cantidad total.
                qty_done = getattr(line, 'quantity', getattr(line, 'qty_done', 0.0))
                qty_reserved = getattr(line, 'reserved_uom_qty', getattr(line, 'quantity', 0.0)) # Fallback a quantity si no hay reserva explícita
                
                lines_data.append({
                    'id': line.id,
                    'product_id': line.product_id.id,
                    'product_name': line.product_id.display_name,
                    'sku': line.product_id.default_code,
                    'barcode': line.product_id.barcode,
                    'image_url': f'/web/image/product.product/{line.product_id.id}/image_128',
                    'qty_demand': qty_reserved or qty_done, 
                    'qty_reserved': qty_reserved,
                    'qty_done': qty_done,
                    'picked': getattr(line, 'wmds_picked_qty', 0.0),
                    'location_id': line.location_id.id,
                    'location_name': line.location_id.display_name,
                    'location_barcode': line.location_id.barcode,
                    'location_dest_id': line.location_dest_id.id,
                    'location_dest_name': line.location_dest_id.display_name,
                    'location_dest_barcode': line.location_dest_id.barcode,
                    'picking_id': line.picking_id.id,
                    'picking_name': line.picking_id.name,
                })

            # Get picking type options
            picking_type = record.picking_type_id if res_model == 'stock.picking' else record.picking_type_id 
            pick_type = getattr(record, 'pick_type', False) if res_model == 'stock.picking.batch' else False

            return {
                "status": "ok",
                "id": record.id,
                "name": record.name,
                "res_model": res_model,
                "pick_type": pick_type,
                "lines": lines_data,
                "use_backorder": getattr(picking_type, 'barcode_allow_backorder', True),
                "restrict_scan_source_location": getattr(picking_type, 'restrict_scan_source_location', False),
                "restrict_scan_dest_location": getattr(picking_type, 'restrict_scan_dest_location', False),
            }

        except Exception as e:
            logger.error(traceback.format_exc())
            return {"status": "error", "message": str(e)}

    @http.route('/wmds/v2/barcode/process_scan', type='json', auth='user', methods=['POST'], csrf=True)
    def process_scan(self, **kw):
        try:
            res_id = kw.get('res_id')
            res_model = kw.get('res_model')
            operator_email = kw.get('operator_email')
            barcode = kw.get('barcode')
            location_barcode = kw.get('location_barcode')
            increment = kw.get('increment', 1)
            line_id = kw.get('line_id')

            record = self._get_record(res_id, res_model)
            status = self._check_status(record, operator_email)
            if status['status'] == 'error':
                return status

            # Logic to find the line and update 'picked'
            if line_id:
                line = request.env['stock.move.line'].sudo().browse(int(line_id))
            else:
                # Find lines matching barcode and location
                domain = [('product_id.barcode', '=', barcode)]
                if res_model == 'stock.picking':
                    domain.append(('picking_id', '=', record.id))
                else:
                    domain.append(('batch_id', '=', record.id))
                
                if location_barcode:
                    domain.append(('location_id.barcode', '=', location_barcode))
                
                lines = request.env['stock.move.line'].sudo().search(domain)
                
                if not lines:
                    return {"status": "error", "message": "Producto no encontrado en esta operación o ubicación incorrecta."}
                
                # Strategy: Prioritize the first incomplete line
                incomplete_line = lines.filtered(lambda l: l.wmds_picked_qty < l.quantity)
                if incomplete_line:
                    line = incomplete_line[0]
                else:
                    # If all are complete, take the first one (validation below will handle the error)
                    line = lines[0]

            if not line.exists():
                return {"status": "error", "message": "Línea no encontrada."}

            extra_products = kw.get('extra_products', False)
            
            # Demand validation
            if not extra_products and increment > 0:
                if line.wmds_picked_qty + increment > line.quantity:
                    msg = f"Intento de escaneo excedido: Producto {line.product_id.display_name}. Recogidos: {line.wmds_picked_qty}, Demanda: {line.quantity}"
                    self._create_log(record, msg, res_model, operator_email)
                    return {"status": "error", "message": "has recogido la cantidad necesaria del SKU para este pedido, no se acpetara en esta operacion "}

            # Update picked
            line.wmds_picked_qty += increment
            
            return {
                "status": "ok",
                "line_id": line.id,
                "new_picked": line.wmds_picked_qty
            }

        except Exception as e:
            logger.error(traceback.format_exc())
            return {"status": "error", "message": str(e)}

    def _create_log(self, record, message, res_model, operator_email=None):
        try:
            user = request.env['res.users'].sudo().search([('login', '=', operator_email)], limit=1) if operator_email else request.env.user
            log_vals = {
                'log': message,
                'user': user.id,
            }
            if res_model == 'stock.picking':
                log_vals['pick'] = record.id
            elif res_model == 'stock.picking.batch':
                log_vals['batch_pick'] = record.id

            request.env['wmds.log'].sudo().create(log_vals)
        except Exception as e:
            logger.error(f"Error creating log: {str(e)}")

    @http.route('/wmds/v2/barcode/log_task_start', type='json', auth='user', methods=['POST'], csrf=True)
    def log_task_start(self, **kw):
        try:
            res_id = kw.get('res_id')
            res_model = kw.get('res_model')
            operator_email = kw.get('operator_email')
            task_title = kw.get('task_title')

            record = None
            if res_id and res_model:
                record = self._get_record(res_id, res_model)
            
            msg = f"Operador inició tarea: {task_title}"
            if record:
                msg += f" ({record.name})"
            
            self._create_log(record, msg, res_model, operator_email)
            return {"status": "ok"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    @http.route('/wmds/v2/barcode/process_dest_location_scan', type='json', auth='user', methods=['POST'], csrf=True)
    def process_dest_location_scan(self, **kw):
        try:
            line_id = kw.get('line_id')
            barcode = kw.get('barcode')
            operator_email = kw.get('operator_email')

            line = request.env['stock.move.line'].sudo().browse(int(line_id))
            if not line.exists():
                return {"status": "error", "message": "Línea no encontrada."}

            # Find the scanned location
            scanned_location = request.env['stock.location'].sudo().search([
                '|', '|', ('barcode', '=', barcode), ('name', '=', barcode), ('id', '=', barcode if str(barcode).isdigit() else 0)
            ], limit=1)

            if not scanned_location:
                return {"status": "error", "message": "Ubicación no encontrada."}

            original_dest = line.location_dest_id
            # Hierarchy check: Accept any valid location as requested
            is_valid = True 

            if is_valid:
                old_dest_name = original_dest.display_name
                line.write({'location_dest_id': scanned_location.id})
                
                msg = f"Ubicación de destino cambiada para {line.product_id.display_name}: de {old_dest_name} a {scanned_location.display_name} (Cambio manual por escaneo)"
                self._create_log(line.picking_id or line.batch_id, msg, 'stock.picking' if line.picking_id else 'stock.picking.batch', operator_email)
                
                return {
                    "status": "ok", 
                    "new_location_name": scanned_location.display_name,
                    "new_location_id": scanned_location.id
                }
            else:
                return {"status": "error", "message": f"La ubicación {scanned_location.display_name} no es válida. Debe ser {original_dest.display_name} o una de sus hijas."}

        except Exception as e:
            logger.error(traceback.format_exc())
            return {"status": "error", "message": str(e)}

    @http.route('/wmds/v2/barcode/validate_operation', type='json', auth='user', methods=['POST'], csrf=True)
    def validate_operation(self, **kw):
        try:
            res_id = kw.get('res_id')
            res_model = kw.get('res_model')
            operator_email = kw.get('operator_email')

            record = self._get_record(res_id, res_model)
            status = self._check_status(record, operator_email)
            if status['status'] == 'error':
                return status

            # Synchronize 'picked' to 'quantity' (qty_done)
            for line in record.move_line_ids:
                line.sudo().write({
                    'quantity': line.wmds_picked_qty,
                    'picked': True if line.wmds_picked_qty > 0 else line.picked
                })

            # Call Odoo's native validation
            res = None
            if res_model == 'stock.picking':
                res = record.button_validate()
            else:
                res = record.action_done()

            # Log closure
            try:
                source = record.location_id.display_name if res_model == 'stock.picking' else "Múltiples"
                dest = record.location_dest_id.display_name if res_model == 'stock.picking' else "Múltiples"
                close_msg = f"Traslado {record.name} cerrado de {source} a {dest}"
                self._create_log(record, close_msg, res_model, operator_email)
            except Exception as log_e:
                logger.error(f"Error logging closure: {str(log_e)}")

            # If Odoo returns a wizard (like backorder confirmation)
            if isinstance(res, dict) and res.get('res_model') == 'stock.backorder.confirmation':
                pickings_to_backorder = record if res_model == 'stock.picking' else record.picking_ids
                wizard = request.env['stock.backorder.confirmation'].with_context(res['context']).sudo().create({
                    'pick_ids': [(4, p.id) for p in pickings_to_backorder]
                })
                wizard.process()

                # Log backorder creation
                for p in pickings_to_backorder:
                    backorder = request.env['stock.picking'].sudo().search([('backorder_id', '=', p.id)], limit=1)
                    if backorder:
                        bo_msg = f"Backorder creado: {backorder.name} para el picking {p.name}"
                        self._create_log(p, bo_msg, 'stock.picking', operator_email)

            return {
                "status": "ok", 
                "message": "Validación exitosa.",
                "pick_type": getattr(record, 'pick_type', False),
                "res_model": res_model
            }
        except Exception as e:
            logger.error(traceback.format_exc())
            return {"status": "error", "message": str(e)}
