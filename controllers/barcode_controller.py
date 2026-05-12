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
            message = "Esta operación ha sido cancelada."
            if record._name == 'stock.picking.batch':
                message = "El BATCH completo ha sido cancelado."
            return {"status": "error", "message": message}
        
        # Check operator assignment
        assigned_operator = getattr(record, 'operator', False)
        if assigned_operator and assigned_operator.login != operator_email:
            message = "Esta operación ha sido reasignada a otro operador."
            if record._name == 'stock.picking.batch':
                message = "Este BATCH ha sido reasignado a otro operador."
            return {"status": "error", "message": message}
        
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

            # Identify PFUL/DFUL
            is_pful = False
            is_dful = False
            pickings = record if res_model == 'stock.picking' else record.picking_ids
            
            # Check picking type names
            type_names = pickings.mapped('picking_type_id.name')
            if any('Resurtido a Ful: Pick' in name for name in type_names if name):
                is_pful = True
            if any('Resurtido a Ful: Despacho' in name for name in type_names if name):
                is_dful = True

            lines_data = []
            # Filter lines to only include those from active pickings (not cancelled or draft)
            lines = record.move_line_ids.filtered(lambda l: l.picking_id.state not in ['cancel', 'draft'])

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
            picking_type = record.picking_type_id if res_model == 'stock.picking' else pickings[0].picking_type_id if pickings else False
            
            # Use record.pick_type if available (for batches), otherwise infer
            pick_type = getattr(record, 'pick_type', False)
            if not pick_type and is_pful:
                pick_type = 'full'

            return {
                "status": "ok",
                "id": record.id,
                "name": record.name,
                "res_model": res_model,
                "pick_type": pick_type,
                "is_pful": is_pful,
                "is_dful": is_dful,
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
                    source_loc = line.location_id.display_name
                    msg = f"Intento de escaneo excedido en {source_loc}: Producto {line.product_id.display_name}. Recogidos: {line.wmds_picked_qty}, Demanda: {line.quantity}"
                    self._create_log(record, msg, res_model, operator_email)
                    return {"status": "error", "message": "has recogido la cantidad necesaria del SKU para este pedido, no se acpetara en esta operacion "}

            # Update picked
            line.wmds_picked_qty += increment
            
            # Log the pick action with source location at picking level for better granularity
            action_desc = "escaneó" if not kw.get('increment') else ("incrementó" if increment > 0 else "decrementó")
            msg = f"Operador {action_desc} {abs(increment)} unidad(es) de {line.product_id.display_name} desde {line.location_id.display_name}"
            self._create_log(line.picking_id, msg, 'stock.picking', operator_email)
            
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
            user = False
            if operator_email:
                # Use case-insensitive search for login
                user = request.env['res.users'].sudo().search([('login', '=ilike', operator_email.strip())], limit=1)
            
            if not user:
                user = request.env.user

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
            check_empty = kw.get('check_empty', False)

            line = request.env['stock.move.line'].sudo().browse(int(line_id))
            if not line.exists():
                return {"status": "error", "message": "Línea no encontrada."}

            # Find the scanned location
            scanned_location = request.env['stock.location'].sudo().search([
                ('barcode', '=', barcode)
            ], limit=1)

            if not scanned_location:
                return {"status": "error", "message": "Ubicación no encontrada."}

            if check_empty:
                # Si la ubicación termina en N1, no revisamos si está vacía
                is_n1 = scanned_location.name and scanned_location.name.endswith('N1')
                if not is_n1:
                    quants = request.env['stock.quant'].sudo().search([
                        ('location_id', '=', scanned_location.id),
                        ('quantity', '>', 0)
                    ], limit=1)
                    if quants:
                        return {"status": "error", "message": f"La ubicación {scanned_location.display_name} ya contiene productos. Elija una vacía."}

            original_dest = line.location_dest_id
            # Hierarchy check: Accept any valid location as requested
            is_valid = True 
            vobo_message = ""

            # Lógica de COMEX para Rackeos
            picking = line.picking_id or (line.batch_id.picking_ids[0] if line.batch_id and line.batch_id.picking_ids else False)
            logger.info(f"COMEX Check: picking={picking.name if picking else 'None'}, picking_type={picking.picking_type_id.name if picking else 'None'}, origin={picking.origin if picking else 'None'}")
            
            if picking and picking.picking_type_id.name == 'Rackeos':
                # Intentar encontrar la PO. A veces el origin tiene prefijos o múltiples referencias.
                origin = picking.origin or ''
                # Buscar cualquier secuencia que parezca una PO (típicamente empieza con P o PO)
                clean_origin = origin
                
                # Intentar búsqueda exacta primero
                po = request.env['purchase.order'].sudo().search([('name', '=', clean_origin)], limit=1)
                
                
                if po:
                    dest_name = scanned_location.complete_name
                    logger.info(f"COMEX Check: dest_name='{dest_name}', check_commertial={po.check_commertial}")
                    if not po.check_commertial:
                        vobo_message = "La compra NO tiene visto bueno COMEX. "
                        if 'Stock/Almacenaje' in dest_name or 'Stock/A_Pickable' in dest_name:
                            new_dest_name = dest_name.replace('Stock/Almacenaje', 'Cuarentena') if 'Stock/Almacenaje' in dest_name else dest_name.replace('Stock/A_Pickable', 'Cuarentena')
                            quarantine_loc = request.env['stock.location'].sudo().search([('complete_name', '=', new_dest_name)], limit=1)
                            if quarantine_loc:
                                scanned_location = quarantine_loc
                                vobo_message += "Redirigiendo a CUARENTENA."
                            else:
                                vobo_message += "Ubicación destino forzada a CUARENTENA (ubicación equivalente no encontrada)."
                    else:
                        vobo_message = "La compra TIENE visto bueno COMEX. "
                        if 'Cuarentena' in dest_name:
                            if dest_name.endswith('N1'): 
                                new_dest_name = dest_name.replace('Cuarentena', 'Stock/A_Pickable')
                            else:
                                new_dest_name = dest_name.replace('Cuarentena', 'Stock/Almacenaje')
                            logger.info(f"COMEX Check: Attempting redirect to '{new_dest_name}'")
                            storage_loc = request.env['stock.location'].sudo().search([('complete_name', '=', new_dest_name)], limit=1)
                            if storage_loc:
                                scanned_location = storage_loc
                                vobo_message += "Redirigiendo a ubicación ESTÁNDAR."
                            else:
                                vobo_message += "Manteniendo ubicación de Cuarentena (equivalente de almacenaje no encontrado)."
                        else:
                            vobo_message += "Ubicación ESTÁNDAR aceptada."
                    
                    logger.info(f"COMEX Check: Final location ID={scanned_location.id}, name={scanned_location.complete_name}")
                else:
                    logger.info(f"COMEX Check: PO not found for origin '{clean_origin}'")

            if is_valid:
                old_dest_name = original_dest.display_name
                line.write({'location_dest_id': scanned_location.id})
                
                # Sincronizar también el move_id
                if line.move_id:
                    line.move_id.write({'location_dest_id': scanned_location.id})
                
                msg = f"Ubicación de destino cambiada para {line.product_id.display_name}: de {old_dest_name} a {scanned_location.display_name} (Cambio manual por escaneo)"
                if vobo_message:
                    msg += f" - COMEX: {vobo_message}"
                
                self._create_log(line.picking_id or line.batch_id, msg, 'stock.picking' if line.picking_id else 'stock.picking.batch', operator_email)
                
                return {
                    "status": "ok", 
                    "new_location_name": scanned_location.display_name,
                    "new_location_id": scanned_location.id,
                    "vobo_message": vobo_message
                }
            else:
                return {"status": "error", "message": f"La ubicación {scanned_location.display_name} no es válida. Debe ser {original_dest.display_name} o una de sus hijas."}

        except Exception as e:
            logger.error(traceback.format_exc())
            return {"status": "error", "message": str(e)}

    @http.route('/wmds/v2/barcode/check_locations_have_stock', type='json', auth='user', methods=['POST'], csrf=True)
    def check_locations_have_stock(self, **kw):
        try:
            res_id = kw.get('res_id')
            res_model = kw.get('res_model')
            location_ids = kw.get('location_ids', [])
            
            if res_id and res_model:
                record = self._get_record(res_id, res_model)
                # Obtenemos las líneas que tienen picks realizados
                lines = record.move_line_ids.filtered(lambda l: l.wmds_picked_qty > 0)
                location_ids = list(set(location_ids + lines.mapped('location_dest_id').ids))
            
            if not location_ids:
                return {"status": "ok", "has_stock": False, "locations": []}
            
            quants = request.env['stock.quant'].sudo().search([
                ('location_id', 'in', [int(id) for id in location_ids]),
                ('quantity', '>', 0)
            ])
            
            locations_with_stock = list(set(quants.mapped('location_id.display_name')))
            
            return {
                "status": "ok",
                "has_stock": bool(locations_with_stock),
                "locations": locations_with_stock
            }
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

            # Identify if it is DFUL or PFUL
            pickings = record if res_model == 'stock.picking' else record.picking_ids

            # Handle unstarted pickings in a batch: remove them from the batch
            excluded_names = []
            if res_model == 'stock.picking.batch':
                for picking in list(pickings):
                    # A picking is unstarted if ALL its lines have wmds_picked_qty == 0
                    if all(l.wmds_picked_qty == 0 for l in picking.move_line_ids):
                        excluded_names.append(picking.name)
                        logger.info(f"Removing unstarted picking {picking.name} from batch {record.name}")
                        # Log on the picking itself
                        self._create_log(picking, f"Transferencia removida del lote {record.name} durante la validación por falta de recolección.", 'stock.picking', operator_email)
                        picking.sudo().write({'batch_id': False})
                
                # Refresh pickings list after removals
                pickings = record.picking_ids
                if not pickings:
                     return {"status": "error", "message": "No quedan pedidos en el plan de pickeo tras remover los no iniciados."}

            validated_names = pickings.mapped('name')
            type_names = pickings.mapped('picking_type_id.name')
            is_dful = any('Resurtido a Ful: Despacho' in name for name in type_names if name)
            is_pful = any('Resurtido a Ful: Pick' in name for name in type_names if name)

            logger.info(f"Validating {res_model} {record.name}. is_dful: {is_dful}, is_pful: {is_pful}")

            # 1. Proactive stock check (to avoid negative stock bug)
            stock_check = {}
            for line in record.move_line_ids:
                if line.wmds_picked_qty <= 0: continue
                key = (line.product_id.id, line.location_id.id)
                stock_check[key] = stock_check.get(key, 0.0) + line.wmds_picked_qty
            
            for (prod_id, loc_id), qty_needed in stock_check.items():
                product = request.env['product.product'].sudo().browse(prod_id)
                location = request.env['stock.location'].sudo().browse(loc_id)
                
                # Check stock_no_negative flags
                disallowed_by_product = not product.allow_negative_stock and not product.categ_id.allow_negative_stock
                disallowed_by_location = not location.allow_negative_stock
                
                if product.is_storable and location.usage in ['internal', 'transit'] and disallowed_by_product and disallowed_by_location:
                    quants = request.env['stock.quant'].sudo().search([
                        ('product_id', '=', prod_id),
                        ('location_id', '=', loc_id)
                    ])
                    available = sum(quants.mapped('quantity'))
                    if qty_needed > available:
                         return {
                            "status": "error", 
                            "message": f"Stock insuficiente en {location.display_name} para {product.display_name}. Disponible: {available}, Requerido: {qty_needed}. No se puede validar para evitar saldos negativos."
                        }

            # 2. Call Odoo's native validation
            res = None
            try:
                # Synchronize 'picked' to 'quantity' (qty_done) inside the try block
                processed_lines_info = []
                for line in record.move_line_ids:
                    if line.wmds_picked_qty > 0:
                        processed_lines_info.append({
                            'move_id': line.move_id.id,
                            'qty': line.wmds_picked_qty
                        })
                    
                    # En Odoo 19 es quantity
                    line.sudo().write({
                        'quantity': line.wmds_picked_qty,
                        'picked': True if line.wmds_picked_qty > 0 else line.picked
                    })

                if res_model == 'stock.picking':
                    res = record.button_validate()
                else:
                    res = record.action_done()
            except Exception as odoo_e:
                logger.error(f"Odoo Validation Error: {str(odoo_e)}")
                return {"status": "error", "message": f"Error de Odoo: {str(odoo_e)}"}

            # Logistics Update for DFUL: mark origin moves as dispatched
            if is_dful:
                for info in processed_lines_info:
                    move = request.env['stock.move'].sudo().browse(info['move_id'])
                    qty = info['qty']
                    
                    # Find origin moves (PFUL)
                    origin_moves = move.move_orig_ids
                    for orig in origin_moves:
                        if not orig.exists(): continue
                        # Update origin move status in BIN/DOCK
                        new_qty_dispatched = (orig.qty_dispatched or 0.0) + qty
                        orig.write({
                            'qty_dispatched': new_qty_dispatched,
                            'dispatched': True if new_qty_dispatched >= (orig.quantity or 0.0) else False,
                            'on_bin': False if new_qty_dispatched >= (orig.quantity or 0.0) else orig.on_bin,
                            'on_dock': False if new_qty_dispatched >= (orig.quantity or 0.0) else orig.on_dock,
                        })
                        
                        target_log = orig.picking_id or orig.batch_id
                        if target_log:
                            self._create_log(target_log, 
                                            f"Producto {orig.product_id.display_name} despachado (DFUL). Cantidad: {qty}", 
                                            'stock.picking' if orig.picking_id else 'stock.picking.batch', 
                                            operator_email)

            # If Odoo returns a wizard (like backorder confirmation)
            if isinstance(res, dict) and res.get('res_model') == 'stock.backorder.confirmation':
                pickings_to_backorder = record if res_model == 'stock.picking' else record.picking_ids
                wizard = request.env['stock.backorder.confirmation'].with_context(res['context']).sudo().create({
                    'pick_ids': [(4, p.id) for p in pickings_to_backorder]
                })
                wizard.process()

            # Create summary log for the operation
            if res_model == 'stock.picking.batch':
                summary_parts = []
                if validated_names:
                    summary_parts.append(f"Pedidos validados: {', '.join(validated_names)}")
                if excluded_names:
                    summary_parts.append(f"Excluidos (no iniciados): {', '.join(excluded_names)}")
                summary = " | ".join(summary_parts)
                self._create_log(record, summary, res_model, operator_email)
            else:
                self._create_log(record, f"Transferencia {record.name} validada con éxito.", res_model, operator_email)

            return {
                "status": "ok", 
                "message": "Validación exitosa.",
                "pick_type": getattr(record, 'pick_type', False),
                "res_model": res_model,
                "is_pful": is_pful,
                "is_dful": is_dful
            }
        except Exception as e:
            logger.error(traceback.format_exc())
            return {"status": "error", "message": str(e)}
