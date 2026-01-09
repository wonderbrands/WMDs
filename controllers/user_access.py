from odoo import http
from odoo.http import request, Response

class UserAccess(http.Controller):
    @http.route('/wmds/engine/user', type='json', auth='user', methods=['POST'], csrf=True)
    def user_access(self, **kw):
        email = kw.get('email')
        if not email:
            return {
                'error': 'Bad request',
                'message': 'Missing required field: email'
            }
        user = request.env['res.users'].sudo().search([('login', '=', email)], limit=1)
        if not user:
            return {
                'error': 'Not found',
                'message': 'User not found'
            }
        is_manager = user.has_group('wmds.group_wmds_manager')
        is_operator = user.has_group('wmds.group_wmds_operator')
        return {
            'role': 'manager' if is_manager else 'operator' if is_operator else 'user',
        }

    @http.route('/wmds/engine/user_validate', type='json', auth='user', methods=['POST'], csrf=True)
    def user_cred(self, **kw):
        user_id = request.uid
        user = request.env['res.users'].sudo().browse(user_id)
        return {
            "name": user.name,
            "login": user.login
        }