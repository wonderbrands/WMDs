from odoo import http
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

            if not bin_name or not operator_login or not orders:
                _logger.error("Faltan datos en move_to_bin")
                return {'error': 'Missing data'}

            operator_orm = request.env["res.users"].sudo().search([('login', '=', operator_login)], limit=1)
            if not operator_orm:
                _logger.warning(f"Operador {operator_login} no encontrado")

            bin_storage = request.env["bin.storage"].sudo().search([('name', '=', bin_name)], limit=1)
            if not bin_storage:
                _logger.error(f"Bin {bin_name} no encontrado")
                return {'error': 'Bin not found'}

            bin_log = request.env["bin.log"].sudo().search([('bin_id', '=', bin_storage.id)], limit=1)
            if not bin_log:
                bin_log = request.env["bin.log"].sudo().create({'bin_id': bin_storage.id})

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
                    
                    operator_name = operator_orm.name if operator_orm else "Desconocido"
                    log_msg = f"El operador {operator_name} puso el paquete {so_custom_name} en el bin {bin_storage.name}"

                    request.env["log.line"].sudo().create({
                        "operator_id": operator_orm.id if operator_orm else False,
                        "qty": 1,
                        "message": log_msg,
                        "bin_log_id": bin_log.id
                    })

                    if ei_tag.so_id:
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
            if not bin_name:
                return {'error': 'El nombre del BIN es requerido', 'valid': False}

            bin_storage = request.env["bin.storage"].sudo().search([('name', '=', bin_name)], limit=1)
            if not bin_storage:
                return {'error': f'El BIN {bin_name} no existe', 'valid': False}

            ei_tags = request.env["sale.order.ei"].sudo().search([
                ('bin_id', '=', bin_storage.id),
                ('on_bin', '=', True)
            ])

            packages = [tag.display_name_custom for tag in ei_tags]
            package_details = [{"name": tag.display_name_custom, "so": tag.so_id.name} for tag in ei_tags]
            return {
                "valid": True,
                "bin": bin_storage.name,
                "packages": packages,
                "package_details": package_details,
                "total_packages": len(packages)
            }
        except Exception as e:
            return {"error": str(e), "valid": False}


    @http.route('/wmds/v2/engine/post/validate_dock', type='json', auth='user', methods=['POST'], csrf=True)
    def validate_dock(self, **kw):
        try:
            dock_name = kw.get("dock")
            if not dock_name:
                return {'error': 'El nombre del DOCK es requerido', 'valid': False}

            dock_storage = request.env["dock.storage"].sudo().search([('name', '=', dock_name)], limit=1)
            if not dock_storage:
                return {'error': f'El DOCK {dock_name} no existe', 'valid': False}

            return {
                "valid": True,
                "dock": dock_storage.name
            }
        except Exception as e:
            return {"error": str(e), "valid": False}


    @http.route('/wmds/v2/engine/post/move_bin_to_dock', type='json', auth='user', methods=['POST'], csrf=True)
    def move_bin_to_dock(self, **kw):
        try:
            bin_name = kw.get("bin")
            dock_name = kw.get("dock")
            operator_login = kw.get("operator")

            if not bin_name or not dock_name or not operator_login:
                return {'error': 'Faltan datos: bin, dock u operator', 'ok': False}

            operator_orm = request.env["res.users"].sudo().search([('login', '=', operator_login)], limit=1)
            bin_storage = request.env["bin.storage"].sudo().search([('name', '=', bin_name)], limit=1)
            dock_storage = request.env["dock.storage"].sudo().search([('name', '=', dock_name)], limit=1)

            if not dock_storage or not bin_storage:
                return {'error': 'Bin o Dock no existe', 'ok': False}

            dock_log = request.env["dock.log"].sudo().search([
                ('dock_id', '=', dock_storage.id), 
                ('bin_id', '=', bin_storage.id)
            ], limit=1)

            if not dock_log:
                dock_log = request.env["dock.log"].sudo().create({
                    'dock_id': dock_storage.id,
                    'bin_id': bin_storage.id
                })

            ei_tags = request.env["sale.order.ei"].sudo().search([
                ('bin_id', '=', bin_storage.id),
                ('on_bin', '=', True)
            ])

            operator_name = operator_orm.name if operator_orm else "Desconocido"

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
                    request.env["wmds.log"].sudo().create({
                        "sale": tag.so_id.id,
                        "log": log_msg,
                        "user": operator_orm.id if operator_orm else False,
                    })

            return {"ok": True, "moved_packages": len(ei_tags)}

        except Exception as e:
            request.env.cr.rollback()
            return {"error": str(e), "ok": False}