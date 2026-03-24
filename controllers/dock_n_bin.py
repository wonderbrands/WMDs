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
                return {
                    "valid": True,
                    "so": ei_tag.so_id.name,
                    "name": ei_tag.display_name_custom,
                    "total": ei_tag.so_id.ei_total,
                    "current": ei_tag.sequence_number,
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
                            return {
                                "valid": True,
                                "so": so.name,
                                "name": attachment_id,
                                "total": so.ei_total,
                                "current": seq,
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
        try:
            bin_name = kw.get("bin")
            operator_login = kw.get("operator")
            orders = kw.get("orders")

            if not bin_name or not operator_login or not orders:
                return {'error': 'Missing data'}

            operator_orm = request.env["res.users"].sudo().search([('login', '=', operator_login)], limit=1)

            bin_storage = request.env["bin.storage"].sudo().search([('name', '=', bin_name)], limit=1)
            if not bin_storage:
                return {'error': 'Bin not found'}

            bin_log = request.env["bin.log"].sudo().search([('bin_id', '=', bin_storage.id)], limit=1)
            if not bin_log:
                bin_log = request.env["bin.log"].sudo().create({'bin_id': bin_storage.id})

            for so_custom_name in orders:
                # Intentar buscar o crear la etiqueta EI
                ei_tag = request.env["sale.order.ei"].sudo().search([
                    ('display_name_custom', '=', so_custom_name)
                ], limit=1)

                if not ei_tag and '/' in so_custom_name:
                    so_name, seq_str = so_custom_name.split('/')
                    so = request.env['sale.order'].sudo().search([('name', '=', so_name)], limit=1)
                    if so:
                        try:
                            seq = int(seq_str)
                            if 0 < seq <= so.ei_total:
                                ei_tag = request.env["sale.order.ei"].sudo().create({
                                    'so_id': so.id,
                                    'sequence_number': seq
                                })
                        except ValueError:
                            pass

                if ei_tag:
                    ei_tag.on_bin = True
                    ei_tag.bin_id = bin_storage.id
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

            return {"ok": True}

        except Exception as e:
            request.env.cr.rollback()
            _logger.error(f"Error en move_to_bin: {str(e)}")
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
            return {
                "valid": True,
                "bin": bin_storage.name,
                "packages": packages,
                "total_packages": len(packages)
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