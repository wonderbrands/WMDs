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
                return {
                    'error': 'Not found',
                    'message': 'Attachment_id is required'
                }

            attachment = request.env["sale.order.attachment"].sudo().search([
                    ('display_name_custom', '=', attachment_id),
                    ("on_bin", "=", False)
                ], limit =1)

            if attachment:
                return {
                    "valid": True,
                    "so": attachment.so_id.name,
                    "name": attachment.display_name_custom
                }
            
            else:
                return {
                    "valid": False,
                }
            
        except Exception as e:
            return {
                "error": f"{str(e)}\n{traceback.format_exc()}"
            }

    
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
                so_attach = request.env["sale.order.attachment"].sudo().search([
                    ('display_name_custom', '=', so_custom_name)
                ], limit=1)
                
                if so_attach:
                    so_attach.on_bin = True
                    so_attach.bin_id = bin_storage.id
                    operator_name = operator_orm.name if operator_orm else "Desconocido"
                    
                    log_msg = f"El operador {operator_name} puso el paquete {so_custom_name} en el bin {bin_storage.name}"

                    request.env["log.line"].sudo().create({
                        "operator_id": operator_orm.id if operator_orm else False,
                        "qty": 1,
                        "message": log_msg,
                        "bin_log_id": bin_log.id
                    })

                    if so_attach.so_id:
                        request.env["wmds.log"].sudo().create({
                            "sale": so_attach.so_id.id,
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
            _logger.info("Iniciando validate_bin")
            bin_name = kw.get("bin")
            
            if not bin_name:
                _logger.info("Error: Nombre de BIN no proporcionado")
                return {'error': 'El nombre del BIN es requerido', 'valid': False}

            bin_storage = request.env["bin.storage"].sudo().search([('name', '=', bin_name)], limit=1)
            
            if not bin_storage:
                _logger.info(f"Error: El BIN {bin_name} no existe")
                return {'error': f'El BIN {bin_name} no existe', 'valid': False}

            _logger.info(f"BIN encontrado: {bin_storage.name}, buscando paquetes...")
            attachments = request.env["sale.order.attachment"].sudo().search([
                ('bin_id', '=', bin_storage.id),
                ('on_bin', '=', True)
            ])

            packages = [attach.display_name_custom for attach in attachments]
            _logger.info(f"Paquetes encontrados en BIN: {len(packages)}")

            return {
                "valid": True,
                "bin": bin_storage.name,
                "packages": packages,
                "total_packages": len(packages)
            }

        except Exception as e:
            _logger.error(f"Excepcion en validate_bin: {str(e)}")
            return {"error": str(e), "valid": False}


    @http.route('/wmds/v2/engine/post/move_bin_to_dock', type='json', auth='user', methods=['POST'], csrf=True)
    def move_bin_to_dock(self, **kw):
        try:
            _logger.info("Iniciando move_bin_to_dock")
            bin_name = kw.get("bin")
            dock_name = kw.get("dock")
            operator_login = kw.get("operator")

            if not bin_name or not dock_name or not operator_login:
                _logger.info("Error: Faltan datos requeridos (bin, dock, operator)")
                return {'error': 'Faltan datos: bin, dock u operator', 'ok': False}

            operator_orm = request.env["res.users"].sudo().search([('login', '=', operator_login)], limit=1)
            bin_storage = request.env["bin.storage"].sudo().search([('name', '=', bin_name)], limit=1)
            dock_storage = request.env["dock.storage"].sudo().search([('name', '=', dock_name)], limit=1)

            if not dock_storage:
                _logger.info(f"Error: El DOCK {dock_name} no existe")
                return {'error': f'El DOCK {dock_name} no existe', 'ok': False}
                
            if not bin_storage:
                _logger.info(f"Error: El BIN {bin_name} no existe")
                return {'error': f'El BIN {bin_name} no existe', 'ok': False}

            _logger.info("Buscando o creando dock.log...")
            dock_log = request.env["dock.log"].sudo().search([
                ('dock_id', '=', dock_storage.id), 
                ('bin_id', '=', bin_storage.id)
            ], limit=1)
            
            if not dock_log:
                dock_log = request.env["dock.log"].sudo().create({
                    'dock_id': dock_storage.id,
                    'bin_id': bin_storage.id
                })

            _logger.info("Buscando paquetes asignados al BIN...")
            attachments = request.env["sale.order.attachment"].sudo().search([
                ('bin_id', '=', bin_storage.id),
                ('on_bin', '=', True)
            ])

            operator_name = operator_orm.name if operator_orm else "Desconocido"

            _logger.info(f"Moviendo {len(attachments)} paquetes al DOCK {dock_storage.name}")
            for attach in attachments:
                attach.on_bin = False
                attach.bin_id = False
                attach.on_dock = True
                attach.dock_id = dock_storage.id
                
                log_msg = f"El operador {operator_name} movió el paquete {attach.display_name_custom} del {bin_storage.name} al DOCK {dock_storage.name}"

                request.env["log.line"].sudo().create({
                    "operator_id": operator_orm.id if operator_orm else False,
                    "qty": 1,
                    "message": log_msg,
                    "dock_log_id": dock_log.id
                })

                if attach.so_id:
                    request.env["wmds.log"].sudo().create({
                        "sale": attach.so_id.id,
                        "log": log_msg,
                        "user": operator_orm.id if operator_orm else False,
                    })
                    
            _logger.info("Movimiento finalizado con exito")
            return {"ok": True, "moved_packages": len(attachments)}

        except Exception as e:
            request.env.cr.rollback()
            _logger.error(f"Excepcion en move_bin_to_dock: {str(e)}")
            return {"error": str(e), "ok": False}