from odoo import http
from odoo.http import request

class AvailableOperators(http.Controller):

    @http.route(
        '/wmds/engine/picks',
        type='json',
        auth='user',
        methods=['POST'],
        csrf=True
    )
    def available_operators(self, **kw):
        
        type_of_pick = kw.get('type')
        name = kw.get('name')

        if not type_of_pick or not name:
            return {
                'error': 'Bad request',
                'message': f"Missing required field: {'type' if not type_of_pick else 'name'}"
            }

        if type_of_pick in ["ingreso", "recepcion"]:
            picking_types = request.env['stock.picking.type'].sudo().search([('name', '=', "Recepciones")])

        else:
            return {
                'error': 'Bad request',
                'message': f"Invalid type of pick: {type_of_pick}"
            }

        if name == '*':
            picks = request.env['stock.picking'].sudo().search([
                ('picking_type_id', 'in', [type_id.id for type_id in picking_types]),
                ('state', '=', 'assigned'),
            ], order='scheduled_date desc',
            limit=5)
        else:
            picks = request.env['stock.picking'].sudo().search([
                ('picking_type_id', 'in', [type_id.id for type_id in picking_types]),
                ('state', '=', 'assigned'),
                ('name', 'ilike', name),
            ],
            order='scheduled_date desc',
            limit=5)

        if not picks:
            return {
                'error': 'Not found',
                'message': 'Picking not found'
            }

        return [
            {
                'name': pick.name,
                "code": pick.id
            }
            for pick in picks
        ]
