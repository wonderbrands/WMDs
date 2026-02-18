from odoo import http
from odoo.http import request

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
            bin = kw.get("bin")
            if not bin:
                return {
                    'error': 'Bin is needed',
                    'message': 'Bin is needed'
                }
            operator = kw.get("operator")
            operator_orm = request.env["res.users"].sudo().search([
                    ('login', '=', operator),
                ], limit =1)
            if not operator:
                 return {
                    'error': 'Operator needed',
                    'message': "Can't do move if not logged it"
                }
            
            orders = kw.get("orders")
            if not orders:
                return {
                    'error': 'No orders',
                    'message': 'Nothing to move'
                }

            bin_orm = request.env["bin.storage"].sudo().search([
                    ('name', '=', bin),
            ], limit =1)
            if not bin_orm:
                return {
                    'error': 'Bin does not exist',
                    'message': 'Bin does not exist'
                }
            
            for so in orders:
                request.env["log.line"].sudo().create(
                    {
                        "operator_id": operator_orm.id,
                        "qty": 1,
                        "message": f"Paquete {so} movido a {bin_orm.name}",
                        "bin_log_id": bin_orm.id
                    }
                )
            
            return {
                "ok": True
            }




        except Exception as e:
            return {
                "error": f"{str(e)}\n{traceback.format_exc()}"
            }