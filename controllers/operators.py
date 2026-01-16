from odoo import http
from odoo.http import request

class AvailableOperators(http.Controller):

    @http.route(
        '/wmds/engine/available_operators',
        type='json',
        auth='user',
        methods=['POST'],
        csrf=True
    )
    def available_operators(self, **kw):
        
        term = kw.get('name')

        operator_group = request.env.ref('wmds.group_wmds_operator')

        if term == '*' or not term:
            users = request.env['res.users'].sudo().search([('groups_id', 'in', operator_group.id)])
        else:
            users = request.env['res.users'].sudo().search([
                ('name', 'ilike', term),
                ('groups_id', 'in', operator_group.id),
            ])

        if not users:
            return {
                'results': []
            }

        ret_value = []
        for index, user in enumerate(users):
            if index == 5:
                break
            ret_value.append({
                'id': user.id,
                'name': user.name,
            })
        return {
            'results': [
                {
                    'id': user.id,
                    'name': user.name,
                    'email': user.login,
                }
                for user in users
            ]
        }
