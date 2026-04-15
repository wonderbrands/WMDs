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
                    'packer_uuid': user.packer_uuid,
                    'packer_barcode_image': user.packer_barcode_image if user.packer_barcode_image else False,
                    'is_packer': user.has_group('wmds.role_wmds_packer')
                }
                for user in users
            ]
        }

    @http.route(
        '/wmds/v2/engine/get/operators',
        type='json',
        auth='user',
        methods=['POST'],
        csrf=True
    )
    def get_operators(self, **kw):
        try:
            parsed_params = {
                "cur_page": kw.get('page', 1),
                "per_page": kw.get('per_page', 30),
                "sort_by": kw.get('sort_by'),
                "sort_order": kw.get('sort_order'),
            }

            for popped_param in ['page', 'per_page', 'sort_by', 'sort_order']:
                if popped_param in kw:
                    kw.pop(popped_param)

            operator_group = request.env.ref('wmds.group_wmds_operator')
            col_domain = [('groups_id', 'in', operator_group.id)]
            
            if len(kw) > 0:
                for key, value in kw.items():
                    col_domain.append((key, "ilike", value))

            offset_val = (parsed_params['cur_page'] - 1) * parsed_params['per_page'] if parsed_params['cur_page'] and parsed_params['per_page'] else 0
            order_val = f"{parsed_params['sort_by']} {parsed_params['sort_order']}" if parsed_params['sort_by'] and parsed_params['sort_order'] else 'id desc'

            users = request.env['res.users'].sudo().search(
                col_domain,
                limit=parsed_params['per_page'],
                offset=offset_val,
                order=order_val
            )
            total = request.env['res.users'].sudo().search_count(col_domain)

            map_cols = [
               { "name": "ID", "field": "id" },
               { "name": "Nombre", "field": "name" },
               { "name": "Correo", "field": "login" },
               { "name": "Packer UUID", "field": "packer_uuid" },
            ]

            return {
               "map_cols": map_cols,
               "data": [
                   {
                       "id": user.id,
                       "name": user.name,
                       "login": user.login,
                       "packer_uuid": user.packer_uuid,
                       "role_ids": [g.id for g in user.groups_id if g.name.startswith('WMDs Operator - ')],
                       "qr_image": user.qr_image if user.qr_image else False,
                       "packer_barcode_image": user.packer_barcode_image if user.packer_barcode_image else False,
                       "is_packer": user.has_group('wmds.role_wmds_packer')
                   } for user in users
               ],                "total_count": total
            }
        except Exception as e:
            import traceback
            return { "error": f"{str(e)}\n{traceback.format_exc()}" }

    @http.route(
        '/wmds/v2/engine/post/save_operator',
        type='json',
        auth='user',
        methods=['POST'],
        csrf=True
    )
    def save_operator(self, **kw):
        try:
            user_id = kw.get('id')
            name = kw.get('name')
            login = kw.get('login')
            role_ids = kw.get('role_ids', [])

            if not name or not login:
                return {"error": "Name and login are required"}

            if user_id:
                user = request.env['res.users'].sudo().browse(user_id)
                if user.exists():
                    user.write({
                        'name': name,
                        'login': login,
                    })
                    groups_to_remove = [(3, g.id) for g in user.groups_id if g.name.startswith('WMDs Operator - ')]
                    if groups_to_remove:
                        user.write({'groups_id': groups_to_remove})
                    if role_ids:
                        user.write({'groups_id': [(4, r_id) for r_id in role_ids]})
            else:
                operator_group = request.env.ref('wmds.group_wmds_operator')
                portal_group = request.env.ref('base.group_portal')
                groups_to_add = [(4, operator_group.id), (4, portal_group.id)]
                if role_ids:
                    groups_to_add += [(4, r_id) for r_id in role_ids]

                request.env['res.users'].sudo().create({
                    'name': name,
                    'login': login,
                    'groups_id': groups_to_add
                })
            
            return {
                "saved": True
            }
        except Exception as e:
            import traceback
            return { "error": f"{str(e)}\n{traceback.format_exc()}" }

    @http.route(
        '/wmds/v2/engine/post/recompute_operators_data',
        type='json',
        auth='user',
        methods=['POST'],
        csrf=True
    )
    def recompute_operators_data(self, **kw):
        try:
            operator_group = request.env.ref('wmds.group_wmds_operator')
            users = request.env['res.users'].sudo().search([('groups_id', 'in', operator_group.id)])
            
            # Resetting to force recompute
            for user in users:
                user.packer_uuid = False
                user._compute_packer_uuid()
                user._compute_packer_barcode_image()
            
            return {"status": "ok", "count": len(users)}
        except Exception as e:
            return {"error": str(e)}

    @http.route(
        '/wmds/v2/engine/get/operator_roles',
        type='json',
        auth='user',
        methods=['POST'],
        csrf=True
    )
    def get_operator_roles(self, **kw):
        try:
            groups = request.env['res.groups'].sudo().search([('name', '=like', 'WMDs Operator - %')])
            return {
                "results": [{"id": g.id, "name": g.name.replace('WMDs Operator - ', '')} for g in groups]
            }
        except Exception as e:
            import traceback
            return {"error": f"{str(e)}\n{traceback.format_exc()}"}
