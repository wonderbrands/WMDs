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
            
            logger.debug("=========================")
            logger.debug(kw)
            logger.debug("=========================")
            parsed_params = {
                "cur_page": kw.get('page'),
                "per_page": kw.get('per_page'),
                "sort_by": None if not kw.get('sort_by') else kw.get('sort_by'),
                "sort_order": None if not kw.get('sort_order') else kw.get('sort_order'),
            }

            for popped_param in ['page', 'per_page', 'sort_by', 'sort_order', 'tz']:
                if popped_param in kw.keys():
                    kw.pop(popped_param)

            col_domain = [("picking_type_id.name", "=", "Pick")]
            if len(list(kw.keys()))>0:
                for key, value in kw.items():
                    col_domain.append(
                        (key, "ilike", value)
                    )

            
            logger.debug("=========================")
            logger.debug(col_domain)

            picks = request.env['stock.picking'].sudo().search(
                col_domain,
                limit=parsed_params.get('per_page'),
                offset=(parsed_params.get('cur_page') - 1) * parsed_params.get('per_page'),
                order= parsed_params.get('sort_by') + ' ' + parsed_params.get('sort_order') if parsed_params.get('sort_by') and parsed_params.get('sort_order') else 'id desc'
            )
            total = request.env['stock.picking'].sudo().search_count(col_domain)

            map_cols = [
                {
                    "name": "ID",
                    "field": "id",
                },
                {
                    "name": "Nombre",
                    "field": "name",
                },
                {
                    "name": "SO",
                    "field": "origin"
                },
                {
                    "name": "Operador",
                    "field": "operator",
                    "type": "one2many",
                    "non_blocked_field": True
                },
                {
                    "name": "Fecha",
                    "field": "scheduled_date"
                },
                {
                    "name": "Estado",
                    "field": "state",
                    "type": "selectable",
                    "options": [
                        {
                            "value": "draft",
                            "label": "Borrador"
                        },
                        {
                            "value": "waiting",
                            "label": "En espera de otra operación"
                        },
                        {
                            "value": "assigned",
                            "label": "Disponible",
                            "default": True
                        },
                        {
                            "value": "confirmed",
                            "label": "En espera"
                        },
                        {
                            "value": "done",
                            "label": "Hecho"
                        },
                        {
                            "value": "cancel",
                            "label": "Cancelado"
                        },
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

            

            return {
                    "map_cols": map_cols,
                    "data": [
                        {
                            "id": pick.id,
                            "name": pick.name,
                            "origin": pick.origin,
                            "operator": None if not pick.operator else {
                                "name": pick.operator.name,
                                "id": pick.operator.id,
                                "email": pick.operator.login
                            },
                            "scheduled_date": pick.scheduled_date,
                            "state": convert_value_in_label(map_cols, pick.state, "state"),
                            "wmds_status": convert_value_in_label(map_cols, pick.wmds_status, "wmds_status")
                        } for pick in picks
                    ],
                    "total_count": len(request.env['stock.picking'].sudo().search(col_domain))
                }
            

        except Exception as e:
            return {
                "error": f"{str(e)}\n{traceback.format_exc()}"
            }

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
            return {
                "title": "Productos del traslado",
                "map_cols": [
                    {
                        "name": "ID",
                        "field": "id",
                    },
                    {
                        "name": "Producto",
                        "field": "product_id",
                    },
                    {
                        "name": "Código de barras",
                        "field": "barcode"
                    },
                    {
                        "name": "SKU",
                        "field": "sku"
                    },	
                    {
                        "name": "Unidades esperadas",
                        "field": "product_uom_qty",
                    },
                    {
                        "name": "Unidades trasladadas",
                        "field": "product_uom",
                    },
                ],
                "data": [
                    {
                        "id": product.id,
                        "product_id": product.product_id.name,
                        "barcode": product.product_id.barcode,
                        "sku": product.product_id.default_code,
                        "product_uom_qty": product.product_uom_qty,
                        "product_uom": product.product_uom.name
                    } for product in picking.move_ids
                ],
                "total_count": len(picking.move_ids)
                }

        except Exception as e:
            return {
                "error": f"{str(e)}\n{traceback.format_exc()}"
            }
          
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
                else:
                    picking = request.env['stock.picking'].sudo().browse(int(kw.get('id')))
                    if picking.exists():
                        picking.operator = responsible["id"]
                return{
                    "saved": True
                }

            operator_mail = kw.get('operator_mail')
            operator = kw.get('operator')
            operation_type = kw.get('operation_type')

            operator_record = None
            if operator_mail:
                operator_record = request.env['res.users'].sudo().search([('login', '=', operator_mail)], limit=1)
            elif operator:
                operator_record = request.env['res.users'].sudo().search([('id', '=', operator["id"])], limit=1)

            target_pickings = request.env['stock.picking'].sudo()

            if is_batch:
                batch = request.env['stock.picking.batch'].sudo().search([('id', '=', kw.get('id'))], limit=1)
                if operation_type == "Pack" and batch:
                    # Find sales orders from the pickings in this batch
                    so_ids = batch.picking_ids.mapped('sale_id.id')
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
                        'user': operator_record.id,
                        'log': f"Se ha asignado el Pack {picking.name} a la mesa {operator_record.name}",
                        'pick': picking.id
                    })

            return{
                "saved": True
            }

        except Exception as e:
            return {
                "error": f"{str(e)}\n{traceback.format_exc()}"
            }

    @http.route(
        '/wmds/v2/engine/get/pack',
        type='json',
        auth='user',
        methods=['POST'],
        csrf=True
    )
    def get_pack(self, **kw):
        try:
            
            logger.debug("=========================")
            logger.debug(kw)
            logger.debug("=========================")
            parsed_params = {
                "cur_page": kw.get('page'),
                "per_page": kw.get('per_page'),
                "sort_by": None if not kw.get('sort_by') else kw.get('sort_by'),
                "sort_order": None if not kw.get('sort_order') else kw.get('sort_order'),
            }

            for popped_param in ['page', 'per_page', 'sort_by', 'sort_order']:
                if popped_param in kw.keys():
                    kw.pop(popped_param)

            col_domain = [("picking_type_id.name", "=", "Pack")]
            if len(list(kw.keys()))>0:
                for key, value in kw.items():
                    col_domain.append(
                        (key, "ilike", value)
                    )

            
            logger.debug("=========================")
            logger.debug(col_domain)

            picks = request.env['stock.picking'].sudo().search(
                col_domain,
                limit=parsed_params.get('per_page'),
                offset=(parsed_params.get('cur_page') - 1) * parsed_params.get('per_page'),
                order= parsed_params.get('sort_by') + ' ' + parsed_params.get('sort_order') if parsed_params.get('sort_by') and parsed_params.get('sort_order') else 'id desc'
            )
            total = request.env['stock.picking'].sudo().search_count(col_domain)

            map_cols = [
                {
                    "name": "ID",
                    "field": "id",
                },
                {
                    "name": "Nombre",
                    "field": "name",
                },
                {
                    "name": "SO",
                    "field": "origin"
                },
                {
                    "name": "Operador",
                    "field": "operator",
                    "type": "one2many",
                    "non_blocked_field": True
                },
                {
                    "name": "Fecha",
                    "field": "scheduled_date"
                },
                {
                    "name": "Estado",
                    "field": "state",
                    "type": "selectable",
                    "options": [
                        {
                            "value": "draft",
                            "label": "Borrador"
                        },
                        {
                            "value": "waiting",
                            "label": "En espera de otra operación"
                        },
                        {
                            "value": "assigned",
                            "label": "Disponible",
                            "default": True
                        },
                        {
                            "value": "confirmed",
                            "label": "En espera"
                        },
                        {
                            "value": "done",
                            "label": "Hecho"
                        },
                        {
                            "value": "cancel",
                            "label": "Cancelado"
                        },
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

            

            return {
                    "map_cols": map_cols,
                    "data": [
                        {
                            "id": pick.id,
                            "name": pick.name,
                            "origin": pick.origin,
                            "operator": None if not pick.operator else {
                                "name": pick.operator.name,
                                "id": pick.operator.id,
                                "email": pick.operator.login
                            },
                            "scheduled_date": pick.scheduled_date,
                            "state": convert_value_in_label(map_cols, pick.state, "state"),
                            "wmds_status": convert_value_in_label(map_cols, pick.wmds_status, "wmds_status")
                        } for pick in picks
                    ],
                    "total_count": len(request.env['stock.picking'].sudo().search(col_domain))
                }
            

        except Exception as e:
            return {
                "error": f"{str(e)}\n{traceback.format_exc()}"
            }

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

            return {
                "id": batch.id,
                "name": batch.name,
                "operator": {"id": batch.operator.id, "name": batch.operator.name} if batch.operator else None,
                "picks": picks_data,
                "logs": logs_data
            }
        except Exception as e:
            return {"error": f"{str(e)}\n{traceback.format_exc()}"}

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
                {
                    "name": "ID",
                    "field": "id",
                },
                {
                    "name": "Referencia",
                    "field": "name",
                },
                {
                    "name": "Operador",
                    "field": "operator",
                    "type": "one2many",
                    "non_blocked_field": True
                },
                {
                    "name": "Fecha Programada",
                    "field": "scheduled_date"
                },
                {
                    "name": "Estado",
                    "field": "state",
                    "type": "selectable",
                    "options": [
                        {
                            "value": "draft",
                            "label": "Borrador"
                        },
                        {
                            "value": "in_progress",
                            "label": "En progreso",
                            "default": True
                        },
                        {
                            "value": "done",
                            "label": "Hecho"
                        },
                        {
                            "value": "cancel",
                            "label": "Cancelado"
                        }
                    ]
                }
            ]

            return {
                "map_cols": map_cols,
                "data": [
                    {
                        "id": batch.id,
                        "name": batch.name,
                        "operator": None if not batch.operator else {
                            "name": batch.operator.name,
                            "id": batch.operator.id,
                            "email": batch.operator.login
                        },
                        "scheduled_date": batch.scheduled_date,
                        "state": convert_value_in_label(map_cols, batch.state, "state")
                    } for batch in batches
                ],
                "total_count": total
            }

        except Exception as e:
            return {
                "error": f"{str(e)}\n{traceback.format_exc()}"
            }