from odoo import http
from odoo.http import request
import traceback
import logging

logger = logging.getLogger(__name__)


def convert_value_in_label(map_cols, value, key):
    if not value:
        return ""

    for pick_state in map_cols:
        if pick_state['field'] == key:
            for state_translate in pick_state['options']:
                if state_translate['value'] == value:
                    return state_translate['label']


class GetPicks(http.Controller):

    @http.route(
        '/wmds/v2/engine/get/picks',
        type='json',
        auth='user',
        methods=['POST'],
        csrf=True
    )
    def get_picks(self, **kw):
        try:
            parsed_params = {
                "cur_page": kw.get('page', 1),
                "per_page": kw.get('per_page', 30),
                "sort_by": kw.get('sort_by'),
                "sort_order": kw.get('sort_order'),
            }

            for popped_param in ['page', 'per_page', 'sort_by', 'sort_order', 'tz']:
                if popped_param in kw.keys():
                    kw.pop(popped_param)

            col_domain = [("picking_type_id.name", "=", "Pick")]
            if len(list(kw.keys()))>0:
                for key, value in kw.items():
                    col_domain.append((key, "ilike", value))

            fields_to_read = ["id", "name", "origin", "operator", "scheduled_date", "state", "wmds_status"]
            
            picks_raw = request.env['stock.picking'].sudo().search_read(
                col_domain,
                fields=fields_to_read,
                limit=parsed_params.get('per_page'),
                offset=(parsed_params.get('cur_page') - 1) * parsed_params.get('per_page'),
                order=parsed_params.get('sort_by') + ' ' + parsed_params.get('sort_order') if parsed_params.get('sort_by') and parsed_params.get('sort_order') else 'id desc'
            )
            
            total = request.env['stock.picking'].sudo().search_count(col_domain)

            map_cols = [
                {"name": "ID", "field": "id"},
                {"name": "Nombre", "field": "name"},
                {"name": "SO", "field": "origin"},
                {"name": "Operador", "field": "operator", "type": "one2many", "non_blocked_field": True},
                {"name": "Fecha", "field": "scheduled_date"},
                {
                    "name": "Estado",
                    "field": "state",
                    "type": "selectable",
                    "options": [
                        {"value": "draft", "label": "Borrador"},
                        {"value": "waiting", "label": "En espera de otra operación"},
                        {"value": "assigned", "label": "Disponible", "default": True},
                        {"value": "confirmed", "label": "En espera"},
                        {"value": "done", "label": "Hecho"},
                        {"value": "cancel", "label": "Cancelado"},
                    ]
                },
                {
                    "name": "Estado en WMDS",
                    "field": "wmds_status",
                    "type": "selectable",
                    "options": [
                        { "label": "No asignado", "value": "not_assigned", "default": True }, 
                        { "label": "No iniciado", "value": "not_started" },
                        { "label": "En progreso", "value": "in_progress" },
                        { "label": "Completado", "value": "completed" },
                    ]
                }
            ]

            data = []
            for p in picks_raw:
                operator_data = None
                if p.get('operator'):
                    op_id, op_name = p['operator']
                    user = request.env['res.users'].sudo().browse(op_id)
                    operator_data = {
                        "name": op_name,
                        "id": op_id,
                        "email": user.login
                    }
                
                data.append({
                    "id": p['id'],
                    "name": p['name'],
                    "origin": p['origin'],
                    "operator": operator_data,
                    "scheduled_date": p['scheduled_date'],
                    "state": convert_value_in_label(map_cols, p['state'], "state"),
                    "wmds_status": convert_value_in_label(map_cols, p['wmds_status'], "wmds_status")
                })

            return {
                "map_cols": map_cols,
                "data": data,
                "total_count": total
            }

        except Exception as e:
            return {"error": f"{str(e)}\n{traceback.format_exc()}"}

    @http.route(
        '/wmds/v2/engine/get/pick_products',
        type='json',
        auth='user',
        methods=['POST'],
        csrf=True
    )
    def get_pick_products(self, **kw):
        try:
            picking = request.env['stock.picking'].sudo().search([('id', '=', kw.get('id'))], limit=1)
            # picking.move_ids access might trigger load of picking columns!
            # Let's use search_read for moves instead
            moves_raw = request.env['stock.move'].sudo().search_read(
                [('picking_id', '=', picking.id)],
                fields=["id", "product_id", "product_uom_qty", "quantity", "product_uom"]
            )
            
            return {
                "title": "Productos del traslado",
                "map_cols": [
                    {"name": "ID", "field": "id"},
                    {"name": "Producto", "field": "product_id"},
                    {"name": "SKU", "field": "sku"},	
                    {"name": "Stock Disponible", "field": "stock_qty"},
                    {"name": "Esperado", "field": "product_uom_qty"},
                    {"name": "Trasladado", "field": "quantity"},
                    {"name": "U.M.", "field": "product_uom"},
                ],
                "data": [
                    {
                        "id": m['id'],
                        "product_id": m['product_id'][1],
                        "barcode": False, # Would need more reads
                        "sku": False,     # Would need more reads
                        "stock_qty": 0,   # Would need more reads
                        "product_uom_qty": m['product_uom_qty'],
                        "quantity": m['quantity'],
                        "product_uom": m['product_uom'][1]
                    } for m in moves_raw
                ],
                "total_count": len(moves_raw)
            }

        except Exception as e:
            return {"error": f"{str(e)}\n{traceback.format_exc()}"}
          
    @http.route(
        '/wmds/v2/engine/post/pick_assign_operator',
        type='json',
        auth='user',
        methods=['POST'],
        csrf=True
    )
    def post_pick_assign_operator(self, **kw):
        try:
            operation_type = kw.get('operation_type')
            operator = kw.get('operator')
            operator_mail = kw.get('operator_mail')
            responsible = kw.get('responsible')
            is_batch = kw.get('is_batch')
            
            if responsible:
                if is_batch:
                    batch = request.env['stock.picking.batch'].sudo().browse(int(kw.get('id')))
                    if batch.exists():
                        batch.operator = responsible["id"]
                        batch.picking_ids.write({'operator': responsible["id"]})
                        request.env["wmds.log"].sudo().create({
                            'user': request.env.user.id,
                            'log': f"Se ha reasignado el plan de pickeo {batch.name} al operador {request.env['res.users'].browse(responsible['id']).name}",
                            'batch_pick': batch.id
                        })
                else:
                    picking = request.env['stock.picking'].sudo().browse(int(kw.get('id')))
                    if picking.exists():
                        picking.operator = responsible["id"]
                        request.env["wmds.log"].sudo().create({
                            'user': request.env.user.id,
                            'log': f"Se ha reasignado el pick {picking.name} al operador {request.env['res.users'].browse(responsible['id']).name}",
                            'pick': picking.id
                        })
                return{"saved": True}

            operator_record = None
            if operator_mail:
                operator_record = request.env['res.users'].sudo().search([('login', '=', operator_mail)], limit=1)
            elif operator:
                operator_record = request.env['res.users'].sudo().search([('id', '=', operator["id"])], limit=1)

            target_pickings = request.env['stock.picking'].sudo()
            batch_record = None

            if is_batch:
                batch_record = request.env['stock.picking.batch'].sudo().search([('id', '=', kw.get('id'))], limit=1)
                if operation_type == "Pack" and batch_record:
                    # Find sales orders from the pickings in this batch
                    so_ids = batch_record.picking_ids.mapped('sale_id.id')
                    target_pickings = request.env['stock.picking'].sudo().search([
                        ('sale_id', 'in', so_ids),
                        ('picking_type_id.name', '=', 'Pack'),
                        ('state', '!=', 'cancel')
                    ])
            else:
                base_pick = request.env['stock.picking'].sudo().search([('id', '=', kw.get('id'))], limit=1)
                if operation_type == "Pack" and base_pick.sale_id:
                    target_pickings = request.env['stock.picking'].sudo().search([
                        ('sale_id', '=', base_pick.sale_id.id),
                        ('picking_type_id.name', '=', 'Pack'),
                        ('state', '!=', 'cancel')
                    ])
                else:
                    target_pickings = base_pick

            for picking in target_pickings:
                picking.operator = operator_record.id if operator_record else (operator["id"] if operator else False)
                if operation_type == "Pack" and operator_record:
                    request.env["wmds.log"].sudo().create({
                        'user': request.env.user.id,
                        'log': f"Se ha asignado el Pack {picking.name} a la mesa {operator_record.name}",
                        'pick': picking.id
                    })

            if batch_record and operation_type == "Pack" and operator_record:
                request.env["wmds.log"].sudo().create({
                    'user': request.env.user.id,
                    'log': f"Se ha asignado la mesa de empaque {operator_record.name} a todos los pedidos del lote {batch_record.name}",
                    'batch_pick': batch_record.id
                })

            return{"saved": True}

        except Exception as e:
            return {"error": f"{str(e)}\n{traceback.format_exc()}"}

    @http.route(
        '/wmds/v2/engine/get/pack',
        type='json',
        auth='user',
        methods=['POST'],
        csrf=True
    )
    def get_pack(self, **kw):
        try:
            parsed_params = {
                "cur_page": kw.get('page', 1),
                "per_page": kw.get('per_page', 30),
                "sort_by": kw.get('sort_by'),
                "sort_order": kw.get('sort_order'),
            }

            for popped_param in ['page', 'per_page', 'sort_by', 'sort_order']:
                if popped_param in kw.keys():
                    kw.pop(popped_param)

            col_domain = [("picking_type_id.name", "=", "Pack")]
            if len(list(kw.keys()))>0:
                for key, value in kw.items():
                    col_domain.append((key, "ilike", value))

            fields_to_read = ["id", "name", "origin", "operator", "scheduled_date", "state", "wmds_status"]
            
            picks_raw = request.env['stock.picking'].sudo().search_read(
                col_domain,
                fields=fields_to_read,
                limit=parsed_params.get('per_page'),
                offset=(parsed_params.get('cur_page') - 1) * parsed_params.get('per_page'),
                order=parsed_params.get('sort_by') + ' ' + parsed_params.get('sort_order') if parsed_params.get('sort_by') and parsed_params.get('sort_order') else 'id desc'
            )
            
            total = request.env['stock.picking'].sudo().search_count(col_domain)

            map_cols = [
                {"name": "ID", "field": "id"},
                {"name": "Nombre", "field": "name"},
                {"name": "SO", "field": "origin"},
                {"name": "Operador", "field": "operator", "type": "one2many", "non_blocked_field": True},
                {"name": "Fecha", "field": "scheduled_date"},
                {
                    "name": "Estado",
                    "field": "state",
                    "type": "selectable",
                    "options": [
                        {"value": "draft", "label": "Borrador"},
                        {"value": "waiting", "label": "En espera de otra operación"},
                        {"value": "assigned", "label": "Disponible", "default": True},
                        {"value": "confirmed", "label": "En espera"},
                        {"value": "done", "label": "Hecho"},
                        {"value": "cancel", "label": "Cancelado"},
                    ]
                },
                {
                    "name": "Estado en WMDS",
                    "field": "wmds_status",
                    "type": "selectable",
                    "options": [
                        { "label": "No asignado", "value": "not_assigned", "default": True }, 
                        { "label": "No iniciado", "value": "not_started" },
                        { "label": "En progreso", "value": "in_progress" },
                        { "label": "Completado", "value": "completed" },
                    ]
                }
            ]

            data = []
            for p in picks_raw:
                operator_data = None
                if p.get('operator'):
                    op_id, op_name = p['operator']
                    user = request.env['res.users'].sudo().browse(op_id)
                    operator_data = {
                        "name": op_name,
                        "id": op_id,
                        "email": user.login
                    }
                
                data.append({
                    "id": p['id'],
                    "name": p['name'],
                    "origin": p['origin'],
                    "operator": operator_data,
                    "scheduled_date": p['scheduled_date'],
                    "state": convert_value_in_label(map_cols, p['state'], "state"),
                    "wmds_status": convert_value_in_label(map_cols, p['wmds_status'], "wmds_status")
                })

            return {
                "map_cols": map_cols,
                "data": data,
                "total_count": total
            }

        except Exception as e:
            return {"error": f"{str(e)}\n{traceback.format_exc()}"}

    @http.route(
        '/wmds/v2/engine/get/batch_details',
        type='json',
        auth='user',
        methods=['POST'],
        csrf=True
    )
    def get_batch_details(self, **kw):
        try:
            batch_id = kw.get('id')
            batch = request.env['stock.picking.batch'].sudo().browse(int(batch_id))
            if not batch.exists():
                return {"error": "Batch not found"}

            picks_data = []
            for pick in batch.picking_ids:
                picks_data.append({
                    "id": pick.id,
                    "name": pick.name,
                    "origin": pick.origin or ""
                })

            logs_data = []
            for log in batch.wmds_log.sorted('date', reverse=True):
                logs_data.append({
                    "id": log.id,
                    "user": log.user.name,
                    "date": log.date,
                    "log": log.log
                })

            # Try to find if a packer is already assigned to the related packs
            packer_data = None
            so_ids = batch.picking_ids.mapped('sale_id.id')
            if so_ids:
                pack_pick = request.env['stock.picking'].sudo().search([
                    ('sale_id', 'in', so_ids),
                    ('picking_type_id.name', '=', 'Pack'),
                    ('state', '!=', 'cancel'),
                    ('operator', '!=', False)
                ], limit=1)
                if pack_pick:
                    packer_data = {"id": pack_pick.operator.id, "name": pack_pick.operator.name}

            return {
                "id": batch.id,
                "name": batch.name,
                "pick_type": batch.pick_type,
                "state": batch.state,
                "operator": {"id": batch.operator.id, "name": batch.operator.name} if batch.operator else None,
                "packer": packer_data,
                "picks": picks_data,
                "logs": logs_data
            }
        except Exception as e:
            return {"error": f"{str(e)}\n{traceback.format_exc()}"}

    @http.route(
        '/wmds/v2/engine/post/check_pack_assigned',
        type='json',
        auth='user',
        methods=['POST'],
        csrf=False
    )
    def check_pack_assigned(self, **kw):
        try:
            pick_id = kw.get('pick_id')
            is_batch = kw.get('is_batch')
            
            domain = [
                ('picking_type_id.name', '=', 'Pack'),
                ('state', '!=', 'cancel'),
                ('operator', '!=', False)
            ]
            
            if is_batch:
                batch = request.env['stock.picking.batch'].sudo().browse(int(pick_id))
                if batch.exists():
                    so_ids = batch.picking_ids.mapped('sale_id.id')
                    domain.append(('sale_id', 'in', so_ids))
                else:
                    return {"assigned": False}
            else:
                picking = request.env['stock.picking'].sudo().browse(int(pick_id))
                if picking.exists() and picking.sale_id:
                    domain.append(('sale_id', '=', picking.sale_id.id))
                else:
                    return {"assigned": False}
            
            assigned_count = request.env['stock.picking'].sudo().search_count(domain)
            return {"assigned": assigned_count > 0}

        except Exception as e:
            return {"error": str(e)}

    @http.route(
        '/wmds/v2/engine/post/check_bin_assigned',
        type='json',
        auth='user',
        methods=['POST'],
        csrf=False
    )
    def check_bin_assigned(self, **kw):
        try:
            pick_id = kw.get('pick_id')
            is_batch = kw.get('is_batch')
            
            domain = [('on_bin', '=', True)]
            
            if is_batch:
                batch = request.env['stock.picking.batch'].sudo().browse(int(pick_id))
                if batch.exists():
                    picking_ids = batch.picking_ids.ids
                    domain.append(('picking_id', 'in', picking_ids))
                else:
                    return {"assigned": False}
            else:
                domain.append(('picking_id', '=', int(pick_id)))
            
            assigned_count = request.env['stock.move'].sudo().search_count(domain)
            return {"assigned": assigned_count > 0}

        except Exception as e:
            return {"error": str(e)}

    @http.route(
        '/wmds/v2/engine/get/batch_pick',
        type='json',
        auth='user',
        methods=['POST'],
        csrf=True
    )
    def get_batch_pick(self, **kw):
        try:
            parsed_params = {
                "cur_page": kw.get('page', 1),
                "per_page": kw.get('per_page', 30),
                "sort_by": kw.get('sort_by'),
                "sort_order": kw.get('sort_order'),
            }

            for popped_param in ['page', 'per_page', 'sort_by', 'sort_order', 'tz']:
                if popped_param in kw:
                    kw.pop(popped_param)

            col_domain = []
            if len(kw) > 0:
                for key, value in kw.items():
                    col_domain.append((key, "ilike", value))

            offset_val = (parsed_params['cur_page'] - 1) * parsed_params['per_page'] if parsed_params['cur_page'] and parsed_params['per_page'] else 0
            order_val = f"{parsed_params['sort_by']} {parsed_params['sort_order']}" if parsed_params['sort_by'] and parsed_params['sort_order'] else 'id desc'

            batches = request.env['stock.picking.batch'].sudo().search(
                col_domain,
                limit=parsed_params['per_page'],
                offset=offset_val,
                order=order_val
            )
            total = request.env['stock.picking.batch'].sudo().search_count(col_domain)

            map_cols = [
                {"name": "ID", "field": "id"},
                {"name": "Referencia", "field": "name"},
                {"name": "Operador", "field": "operator", "type": "one2many", "non_blocked_field": True},
                {"name": "Fecha Programada", "field": "scheduled_date"},
                {
                    "name": "Estado",
                    "field": "state",
                    "type": "selectable",
                    "options": [
                        {"value": "draft", "label": "Borrador"},
                        {"value": "in_progress", "label": "En progreso", "default": True},
                        {"value": "done", "label": "Hecho"},
                        {"value": "cancel", "label": "Cancelado"}
                    ]
                }
            ]

            return {
                "map_cols": map_cols,
                "data": [
                    {
                        "id": b.id,
                        "name": b.name,
                        "operator": None if not b.operator else {
                            "name": b.operator.name,
                            "id": b.operator.id,
                            "email": b.operator.login
                        },
                        "scheduled_date": b.scheduled_date,
                        "state": convert_value_in_label(map_cols, b.state, "state")
                    } for b in batches
                ],
                "total_count": total
            }

        except Exception as e:
            return {"error": f"{str(e)}\n{traceback.format_exc()}"}
