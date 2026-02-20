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
                return {'error': 'Missing data', 'message': 'Bin, Operator and Orders are required'}

            # Buscamos al operador
            operator_orm = request.env["res.users"].sudo().search([('login', '=', operator_login)], limit=1)
            if not operator_orm:
                return {'error': 'Operator not found', 'message': f'User {operator_login} not found'}

            # Buscamos el bin
            bin_orm = request.env["bin.storage"].sudo().search([('name', '=', bin_name)], limit=1)
            if not bin_orm:
                return {'error': 'Bin not found', 'message': f'Bin {bin_name} does not exist'}

            # Procesamos cada orden
            for so_name in orders:
                so_attach = request.env["sale.order.attachment"].sudo().search([
                    ('display_name_custom', '=', so_name)
                ], limit=1)
                
                if so_attach:
                    so_attach.on_bin = True
                    request.env["log.line"].sudo().create({
                        "operator_id": operator_orm.id,
                        "qty": 1,
                        "message": f"Paquete {so_name} movido a {bin_orm.name}",
                        "bin_log_id": bin_orm.id
                    })

            return {"ok": True}

        except Exception as e:
            request.env.cr.rollback()
            _logger.error(f"Error en move_to_bin: {str(e)}")
            return {
                "error": "Error interno del servidor",
                "debug": f"{str(e)}\n{traceback.format_exc()}"
            }