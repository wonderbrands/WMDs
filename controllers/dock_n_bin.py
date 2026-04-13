from odoo import http, fields
from odoo.http import request
import traceback
import logging

_logger = logging.getLogger(__name__)


class DockNBin(http.Controller):

    @http.route('/wmds/v2/engine/post/validate_attachment_guide', type='json', auth='user', methods=['POST'], csrf=True)
    def validate_attachment_guide(self, **kw):
        try:
            attachment_id = kw.get("attachment_id")
            if not attachment_id:
                return {'error': 'Not found', 'message': 'ID is required'}

            # Buscar si ya existe
            ei_tag = request.env["sale.order.ei"].sudo().search([
                    ('display_name_custom', '=', attachment_id)
                ], limit=1)

            if ei_tag:
                # Contar cuántos paquetes del mismo SO ya están en proceso (en bin, dock o despachados)
                already_processed_count = request.env["sale.order.ei"].sudo().search_count([
                    ('so_id', '=', ei_tag.so_id.id),
                    '|', '|', ('on_bin', '=', True), ('on_dock', '=', True), ('dispatched', '=', True)
                ])

                # Contar específicamente los ya despachados
                dispatched_count = request.env["sale.order.ei"].sudo().search_count([
                    ('so_id', '=', ei_tag.so_id.id),
                    ('dispatched', '=', True)
                ])

                return {
                    "valid": True,
                    "so": ei_tag.so_id.name,
                    "so_state": ei_tag.so_id.state,
                    "name": ei_tag.display_name_custom,
                    "total": ei_tag.so_id.ei_total,
                    "current": ei_tag.sequence_number,
                    "processed_count": already_processed_count,
                    "dispatched_count": dispatched_count,
                    "state": {
                        "on_bin": ei_tag.on_bin,
                        "bin_name": ei_tag.bin_id.name if ei_tag.bin_id else False,
                        "on_dock": ei_tag.on_dock,
                        "dock_name": ei_tag.dock_id.name if ei_tag.dock_id else False,
                        "dispatched": ei_tag.dispatched
                    }
                }

            # Si no existe, validar si es un formato SOXXXX/N válido según ei_total
            if '/' in attachment_id:
                parts = attachment_id.split('/')
                if len(parts) == 2:
                    so_name, seq_str = parts
                    try:
                        seq = int(seq_str)
                        so = request.env['sale.order'].sudo().search([('name', '=', so_name)], limit=1)
                        if so and 0 < seq <= so.ei_total:
                            # Contar cuántos paquetes del mismo SO ya están en proceso
                            already_processed_count = request.env["sale.order.ei"].sudo().search_count([
                                ('so_id', '=', so.id),
                                '|', '|', ('on_bin', '=', True), ('on_dock', '=', True), ('dispatched', '=', True)
                            ])
                            
                            # Contar específicamente los ya despachados
                            dispatched_count = request.env["sale.order.ei"].sudo().search_count([
                                ('so_id', '=', so.id),
                                ('dispatched', '=', True)
                            ])

                            return {
                                "valid": True,
                                "so": so.name,
                                "so_state": so.state,
                                "name": attachment_id,
                                "total": so.ei_total,
                                "current": seq,
                                "processed_count": already_processed_count,
                                "dispatched_count": dispatched_count,
                                "state": {
                                    "on_bin": False,
                                    "on_dock": False,
                                    "dispatched": False
                                }
                            }
                    except ValueError:
                        pass

            return {"valid": False}

        except Exception as e:
            return {"error": f"{str(e)}\n{traceback.format_exc()}"}


    @http.route('/wmds/v2/engine/post/move_to_bin', type='json', auth='user', methods=['POST'], csrf=True)
    def move_to_bin(self, **kw):
        _logger.info(f"Iniciando move_to_bin con datos: {kw}")
        try:
            bin_name = kw.get("bin")
            operator_login = kw.get("operator")
            orders = kw.get("orders")
            batch_id = kw.get("batch_id")
            pick_id = kw.get("pick_id")
            carrier_id = kw.get("carrier_id")

            if not bin_name or not operator_login:
                _logger.error("Faltan datos en move_to_bin")
                return {'error': 'Missing data'}

            operator_orm = request.env["res.users"].sudo().search([('login', '=', operator_login)], limit=1)
            bin_storage = request.env["bin.storage"].sudo().search([('name', '=', bin_name)], limit=1)
            if not bin_storage:
                _logger.error(f"Bin {bin_name} no encontrado")
                return {'error': 'Bin not found'}

            # Guardar el carrier en el BIN
            if carrier_id:
                bin_storage.write({'carrier_id': int(carrier_id)})

            bin_log = request.env["bin.log"].sudo().search([('bin_id', '=', bin_storage.id)], limit=1)
            if not bin_log:
                bin_log = request.env["bin.log"].sudo().create({'bin_id': bin_storage.id})

            operator_name = operator_orm.name if operator_orm else "Desconocido"

            # Validar mezcla de tipos (Full vs Ecommerce)
            has_ei = request.env["sale.order.ei"].sudo().search_count([
                ('bin_id', '=', bin_storage.id),
                ('on_bin', '=', True)
            ]) > 0
            
            has_moves = request.env["stock.move"].sudo().search_count([
                ('bin_id', '=', bin_storage.id),
                ('on_bin', '=', True)
            ]) > 0

            if batch_id or pick_id:
                if has_ei:
                    return {'error': 'El BIN ya contiene pedidos. No se pueden mezclar con fulfillment.'}
                # Caso Full o Picking específico: Procesar por ID
                if batch_id:
                    batch = request.env['stock.picking.batch'].sudo().browse(batch_id)
                    pickings = batch.picking_ids
                    log_target = {"batch_pick": batch.id}
                    log_label = f"Lote {batch.name}"
                else:
                    picking = request.env['stock.picking'].sudo().browse(pick_id)
                    pickings = picking
                    log_target = {"pick": picking.id}
                    log_label = f"Traslado {picking.name}"

                moves = pickings.mapped('move_ids').filtered(lambda m: m.state == 'done' and not m.dispatched)
                
                for move in moves:
                    move.write({
                        'on_bin': True,
                        'bin_id': bin_storage.id,
                        'on_dock': False,
                        'dock_id': False,
                        'dispatched': False
                    })
                    
                    log_msg = f"El operador {operator_name} puso el producto {move.product_id.display_name} (de la orden {move.picking_id.name}) en el bin {bin_storage.name}"
                    
                    request.env["log.line"].sudo().create({
                        "operator_id": operator_orm.id if operator_orm else False,
                        "qty": move.quantity,
                        "message": log_msg,
                        "bin_log_id": bin_log.id
                    })

                # Log General
                log_vals = {
                    "log": f"{log_label} movido a BIN {bin_storage.name} por {operator_name}",
                    "user": operator_orm.id if operator_orm else False,
                }
                log_vals.update(log_target)
                request.env["wmds.log"].sudo().create(log_vals)

                return {"ok": True, "count": len(moves)}

            if orders:
                if has_moves:
                    return {'error': 'El BIN ya contiene productos de fulfillment. No se pueden mezclar con pedidos.'}
                # Caso Ecommerce/Picks: Procesar por etiquetas EI
                for so_custom_name in orders:
                    _logger.info(f"Procesando etiqueta: {so_custom_name}")
                    # Intentar buscar o crear la etiqueta EI
                    ei_tag = request.env["sale.order.ei"].sudo().search([
                        ('display_name_custom', '=', so_custom_name)
                    ], limit=1)

                    if not ei_tag and '/' in so_custom_name:
                        parts = so_custom_name.split('/')
                        if len(parts) == 2:
                            so_name, seq_str = parts
                            so = request.env['sale.order'].sudo().search([('name', '=', so_name)], limit=1)
                            if so:
                                try:
                                    seq = int(seq_str)
                                    if 0 < seq <= so.ei_total:
                                        ei_tag = request.env["sale.order.ei"].sudo().create({
                                            'so_id': so.id,
                                            'sequence_number': seq
                                        })
                                        _logger.info(f"Etiqueta {so_custom_name} creada")
                                except ValueError:
                                    pass

                    if ei_tag:
                        _logger.info(f"Actualizando estado de ei_tag {ei_tag.id}")
                        ei_tag.write({
                            'on_bin': True,
                            'bin_id': bin_storage.id,
                            'on_dock': False,
                            'dock_id': False,
                            'dispatched': False
                        })
                        
                        log_msg = f"El operador {operator_name} puso el paquete {so_custom_name} en el bin {bin_storage.name}"

                        request.env["log.line"].sudo().create({
                            "operator_id": operator_orm.id if operator_orm else False,
                            "qty": 1,
                            "message": log_msg,
                            "bin_log_id": bin_log.id
                        })

                        if ei_tag.so_id:
                            # Propagación automática desde pick -> sale y batch
                            picking = request.env['stock.picking'].sudo().search([
                                ('sale_id', '=', ei_tag.so_id.id),
                                ('state', 'in', ['assigned', 'done']),
                                ('picking_type_id.name', 'ilike', 'Pick')
                            ], order='date_done desc', limit=1)
                            
                            if picking:
                                request.env["wmds.log"].sudo().create({
                                    "pick": picking.id,
                                    "log": log_msg,
                                    "user": operator_orm.id if operator_orm else False,
                                })
                            else:
                                request.env["wmds.log"].sudo().create({
                                    "sale": ei_tag.so_id.id,
                                    "log": log_msg,
                                    "user": operator_orm.id if operator_orm else False,
                                })
                    else:
                        _logger.warning(f"No se pudo encontrar ni crear ei_tag para {so_custom_name}")

            return {"ok": True}

        except Exception as e:
            request.env.cr.rollback()
            _logger.error(f"Error grave en move_to_bin: {str(e)}\n{traceback.format_exc()}")
            return {"error": str(e)}

    @http.route('/wmds/v2/engine/post/validate_bin', type='json', auth='user', methods=['POST'], csrf=True)
    def validate_bin(self, **kw):
        try:
            bin_name = kw.get("bin")
            purpose = kw.get("purpose", "in") # 'in' to add items, 'out' to take items
            
            if not bin_name:
                return {'error': 'El nombre del BIN es requerido', 'valid': False}

            bin_storage = request.env["bin.storage"].sudo().search([('name', '=', bin_name)], limit=1)
            if not bin_storage:
                return {'error': f'El BIN {bin_name} no existe', 'valid': False}

            if purpose == "in" and bin_storage.state == 'blocked':
                return {'error': f'El BIN {bin_name} ya está ocupado', 'valid': False}
            
            ei_tags = request.env["sale.order.ei"].sudo().search([
                ('bin_id', '=', bin_storage.id),
                ('on_bin', '=', True)
            ])

            if purpose == "out" and not ei_tags:
                return {'error': f'El BIN {bin_name} está vacío (o solo contiene Full)', 'valid': False}

            packages = [tag.display_name_custom for tag in ei_tags]
            package_details = [{"name": tag.display_name_custom, "so": tag.so_id.name, "is_full": False} for tag in ei_tags]
            
            return {
                "valid": True,
                "bin": bin_storage.name,
                "packages": packages,
                "package_details": package_details,
                "total_packages": len(packages),
                "has_full": False,
                "has_ecommerce": len(packages) > 0,
                "carrier_name": bin_storage.carrier_id.name if bin_storage.carrier_id else "",
            }
        except Exception as e:
            return {"error": str(e), "valid": False}


    @http.route('/wmds/v2/engine/post/block_bin', type='json', auth='user', methods=['POST'], csrf=True)
    def block_bin(self, **kw):
        try:
            bin_name = kw.get("bin")
            if not bin_name:
                return {'error': 'BIN name is required', 'ok': False}
            
            bin_storage = request.env["bin.storage"].sudo().search([('name', '=', bin_name)], limit=1)
            if not bin_storage:
                return {'error': 'Bin not found', 'ok': False}

            # Check for stock
            ei_tags_count = request.env["sale.order.ei"].sudo().search_count([
                ('bin_id', '=', bin_storage.id),
                ('on_bin', '=', True)
            ])
            
            moves_count = request.env["stock.move"].sudo().search_count([
                ('bin_id', '=', bin_storage.id),
                ('on_bin', '=', True)
            ])

            has_stock = (ei_tags_count + moves_count) > 0

            # If it has stock, anyone can block it.
            # If not, only manager can block it (to reserve it, for example)
            is_manager = request.env.user.has_group('wmds.group_wmds_manager')

            if has_stock or is_manager:
                bin_storage.state = 'blocked'
                return {'ok': True}
            else:
                return {
                    'error': 'El BIN está vacío y no tienes permisos de Manager para bloquearlo.', 
                    'ok': False
                }
        except Exception as e:
            return {'error': str(e), 'ok': False}

    @http.route('/wmds/v2/engine/post/validate_dock', type='json', auth='user', methods=['POST'], csrf=True)
    def validate_dock(self, **kw):
        try:
            dock_name = kw.get("dock")
            if not dock_name:
                return {'error': 'El nombre del DOCK es requerido', 'valid': False}

            dock_storage = request.env["dock.storage"].sudo().search([('name', '=', dock_name)], limit=1)
            if not dock_storage:
                return {'error': f'El DOCK {dock_name} no existe', 'valid': False}

            if dock_storage.state == 'blocked':
                return {'error': f'El DOCK {dock_name} ya está ocupado', 'valid': False}

            # Validar contenido actual del DOCK
            has_ei = request.env["sale.order.ei"].sudo().search_count([
                ('dock_id', '=', dock_storage.id),
                ('on_dock', '=', True)
            ]) > 0
            has_moves = request.env["stock.move"].sudo().search_count([
                ('dock_id', '=', dock_storage.id),
                ('on_dock', '=', True)
            ]) > 0

            return {
                "valid": True,
                "dock": dock_storage.name,
                "has_ecommerce": has_ei,
                "has_full": has_moves
            }
        except Exception as e:
            return {"error": str(e), "valid": False}


    @http.route('/wmds/v2/engine/post/move_bin_to_dock', type='json', auth='user', methods=['POST'], csrf=True)
    def move_bin_to_dock(self, **kw):
        try:
            bin_name = kw.get("bin")
            dock_name = kw.get("dock")
            operator_login = kw.get("operator")
            selected_packages = kw.get("selected_packages", []) # List of {name, is_full, move_id}

            if not bin_name or not dock_name or not operator_login:
                return {'error': 'Faltan datos: bin, dock u operator', 'ok': False}

            operator_orm = request.env["res.users"].sudo().search([('login', '=', operator_login)], limit=1)
            bin_storage = request.env["bin.storage"].sudo().search([('name', '=', bin_name)], limit=1)
            dock_storage = request.env["dock.storage"].sudo().search([('name', '=', dock_name)], limit=1)

            if not dock_storage or not bin_storage:
                return {'error': 'Bin o Dock no existe', 'ok': False}

            # Filter logic for partial movement
            ei_domain = [('bin_id', '=', bin_storage.id), ('on_bin', '=', True)]
            move_domain = [('bin_id', '=', bin_storage.id), ('on_bin', '=', True)]

            if selected_packages:
                ei_names = [p['name'] for p in selected_packages if not p.get('is_full')]
                move_ids = [p['move_id'] for p in selected_packages if p.get('is_full')]
                
                if ei_names:
                    ei_domain.append(('display_name_custom', 'in', ei_names))
                else:
                    ei_domain.append(('id', '=', 0)) # None

                if move_ids:
                    move_domain.append(('id', 'in', move_ids))
                else:
                    move_domain.append(('id', '=', 0)) # None

            # Validar mezcla en el DOCK
            # Solo validar si se va a mover algo de ese tipo
            moving_ei = request.env["sale.order.ei"].sudo().search_count(ei_domain) > 0
            moving_moves = request.env["stock.move"].sudo().search_count(move_domain) > 0

            dock_has_ei = request.env["sale.order.ei"].sudo().search_count([
                ('dock_id', '=', dock_storage.id),
                ('on_dock', '=', True)
            ]) > 0
            dock_has_moves = request.env["stock.move"].sudo().search_count([
                ('dock_id', '=', dock_storage.id),
                ('on_dock', '=', True)
            ]) > 0

            if moving_ei and dock_has_moves:
                return {'error': 'El DOCK ya contiene productos de fulfillment. No se pueden mezclar con pedidos.', 'ok': False}
            if moving_moves and dock_has_ei:
                return {'error': 'El DOCK ya contiene pedidos. No se pueden mezclar con fulfillment.', 'ok': False}

            dock_log = request.env["dock.log"].sudo().search([
                ('dock_id', '=', dock_storage.id), 
                ('bin_id', '=', bin_storage.id)
            ], limit=1)

            if not dock_log:
                dock_log = request.env["dock.log"].sudo().create({
                    'dock_id': dock_storage.id,
                    'bin_id': bin_storage.id
                })

            operator_name = operator_orm.name if operator_orm else "Desconocido"

            # Mover EI Tags
            ei_tags = request.env["sale.order.ei"].sudo().search(ei_domain)

            for tag in ei_tags:
                tag.on_bin = False
                tag.bin_id = False
                tag.on_dock = True
                tag.dock_id = dock_storage.id

                log_msg = f"El operador {operator_name} movió el paquete {tag.display_name_custom} del {bin_storage.name} al DOCK {dock_storage.name}"

                request.env["log.line"].sudo().create({
                    "operator_id": operator_orm.id if operator_orm else False,
                    "qty": 1,
                    "message": log_msg,
                    "dock_log_id": dock_log.id
                })

                if tag.so_id:
                    # Propagación automática desde pick -> sale y batch
                    picking = request.env['stock.picking'].sudo().search([
                        ('sale_id', '=', tag.so_id.id),
                        ('state', 'in', ['assigned', 'done']),
                        ('picking_type_id.name', 'ilike', 'Pick')
                    ], order='date_done desc', limit=1)
                    
                    if picking:
                        request.env["wmds.log"].sudo().create({
                            "pick": picking.id,
                            "log": log_msg,
                            "user": operator_orm.id if operator_orm else False,
                        })
                    else:
                        request.env["wmds.log"].sudo().create({
                            "sale": tag.so_id.id,
                            "log": log_msg,
                            "user": operator_orm.id if operator_orm else False,
                        })

            # Mover Stock Moves
            moves = request.env["stock.move"].sudo().search(move_domain)

            processed_pickings = request.env['stock.picking']
            processed_batches = request.env['stock.picking.batch']

            for move in moves:
                move.on_bin = False
                move.bin_id = False
                move.on_dock = True
                move.dock_id = dock_storage.id

                log_msg = f"El operador {operator_name} movió el producto {move.product_id.display_name} del {bin_storage.name} al DOCK {dock_storage.name}"

                request.env["log.line"].sudo().create({
                    "operator_id": operator_orm.id if operator_orm else False,
                    "qty": move.quantity,
                    "message": log_msg,
                    "dock_log_id": dock_log.id
                })
                
                if move.picking_id:
                    processed_pickings |= move.picking_id
                    if move.picking_id.batch_id:
                        processed_batches |= move.picking_id.batch_id

            # Log en Pickings y Batches de Full
            for batch in processed_batches:
                request.env["wmds.log"].sudo().create({
                    "batch_pick": batch.id,
                    "log": f"Lote movido a DOCK {dock_storage.name} por {operator_name}",
                    "user": operator_orm.id if operator_orm else False,
                })
            
            # Para pickings que no tienen batch
            for picking in processed_pickings.filtered(lambda p: not p.batch_id):
                request.env["wmds.log"].sudo().create({
                    "pick": picking.id,
                    "log": f"Traslado {picking.name} movido a DOCK {dock_storage.name} por {operator_name}",
                    "user": operator_orm.id if operator_orm else False,
                })

            # Verificar si el BIN quedó vacío para liberarlo
            has_remaining = request.env["sale.order.ei"].sudo().search_count([('bin_id', '=', bin_storage.id), ('on_bin', '=', True)]) > 0 or \
                            request.env["stock.move"].sudo().search_count([('bin_id', '=', bin_storage.id), ('on_bin', '=', True)]) > 0
            
            if not has_remaining:
                bin_storage.write({
                    'state': 'available',
                    'carrier_id': False,
                })

            return {"ok": True, "moved_packages": len(ei_tags) + len(moves)}

        except Exception as e:
            request.env.cr.rollback()
            return {"error": str(e), "ok": False}

    @http.route('/wmds/v2/engine/get/active_bins', type='json', auth='user', methods=['POST'], csrf=True)
    def get_active_bins(self, **kw):
        try:
            # Return any bin that has items, regardless of state
            bins = request.env["bin.storage"].sudo().search([])
            res = []
            for b in bins:
                # Contar qué tiene
                move_count = request.env["stock.move"].sudo().search_count([('bin_id', '=', b.id), ('on_bin', '=', True)])
                # Si tiene CUALQUIER move (Full), omitimos este BIN por completo de WMDS screen
                if move_count > 0:
                    continue

                ei_count = request.env["sale.order.ei"].sudo().search_count([('bin_id', '=', b.id), ('on_bin', '=', True)])
                if ei_count > 0:
                    res.append({
                        "id": b.id,
                        "name": b.name,
                        "has_ecommerce": True,
                        "has_full": False,
                        "total_items": ei_count,
                        "carrier_name": b.carrier_id.name if b.carrier_id else "Sin carrier"
                    })
            return res
        except Exception as e:
            return {"error": str(e)}

    @http.route('/wmds/v2/engine/get/active_docks', type='json', auth='user', methods=['POST'], csrf=True)
    def get_active_docks(self, **kw):
        try:
            docks = request.env["dock.storage"].sudo().search([])
            res = []
            for d in docks:
                move_count = request.env["stock.move"].sudo().search_count([('dock_id', '=', d.id), ('on_dock', '=', True)])
                # Si tiene CUALQUIER move (Full), omitimos este DOCK por completo de WMDS screen
                if move_count > 0:
                    continue

                ei_count = request.env["sale.order.ei"].sudo().search_count([('dock_id', '=', d.id), ('on_dock', '=', True)])
                if ei_count > 0:
                    res.append({
                        "id": d.id,
                        "name": d.name,
                        "has_ecommerce": True,
                        "has_full": False,
                        "total_items": ei_count
                    })
            return res
        except Exception as e:
            return {"error": str(e)}

    @http.route('/wmds/v2/engine/get/available_docks', type='json', auth='user', methods=['POST'], csrf=True)
    def get_available_docks(self, **kw):
        try:
            docks = request.env["dock.storage"].sudo().search([('state', '=', 'available')])
            return [{"id": d.id, "name": d.name} for d in docks]
        except Exception as e:
            return {"error": str(e)}

    @http.route('/wmds/v2/engine/get/available_bins', type='json', auth='user', methods=['POST'], csrf=True)
    def get_available_bins(self, **kw):
        try:
            # We can optionally filter by carrier if provided
            carrier_id = kw.get('carrier_id')
            domain = [('state', '=', 'available')]
            if carrier_id:
                domain = ['|', ('carrier_id', '=', int(carrier_id)), ('carrier_id', '=', False), ('state', '=', 'available')]
            
            bins = request.env["bin.storage"].sudo().search(domain)
            return [{"id": b.id, "name": b.name} for b in bins]
        except Exception as e:
            return {"error": str(e)}

    @http.route('/wmds/v2/engine/get/dock_contents', type='json', auth='user', methods=['POST'], csrf=True)
    def get_dock_contents(self, **kw):
        try:
            dock_name = kw.get("dock")
            dock = request.env["dock.storage"].sudo().search([('name', '=', dock_name)], limit=1)
            if not dock:
                return {"error": "Dock no encontrado"}
            
            ei_tags = request.env["sale.order.ei"].sudo().search([
                ('dock_id', '=', dock.id),
                ('on_dock', '=', True)
            ])

            package_details = [{"name": tag.display_name_custom, "so": tag.so_id.name, "is_full": False} for tag in ei_tags]
            
            return {
                "dock": dock.name,
                "package_details": package_details,
                "has_ecommerce": len(ei_tags) > 0,
                "has_full": False
            }
        except Exception as e:
            return {"error": str(e)}
