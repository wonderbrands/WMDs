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