import json
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

    @http.route('/wmds/v2/engine/get/valid_user', type='json', auth='user', methods=['POST'], csrf=True)
    def get_valid_user(self, **kw):
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
        if user.has_group('wmds.group_wmds_operator') or  user.has_group('wmds.group_wmds_manager'):
            return {
                "name": user.name,
                "login": user.login
            }

        return {
                'error': 'User has no access',
                'message': 'User has no permission to access  WMDS app'
            }

    @http.route('/wmds/v2/engine/get/user_role_permissions', type='json', auth='user', methods=['POST'], csrf=True)
    def get_user_role_permissions(self, **kw):
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
        
        groups = [group.name 
                    for group in user.groups_id 
                    if group.name.startswith("WMDs") and 
                    group.name not in ["WMDs Operator", "WMDs Manager"]]

        return {
            "name": user.name,
            "login": user.login,
            "permissions": groups
        }

    @http.route('/wmds/v2/engine/post/skip_log_if_manager', type='json', auth='user', methods=['POST'], csrf=True)
    def skip_log_if_manager(self, **kw):
        user = request.env.user
        if user.has_group('WMDs Manager'):
            return {
                "is_manager": True,
                "json_user":  json.dumps({
                    "email": user.login
                })
            }

        return {
            "is_manager": False,
            "json_user": None
        }