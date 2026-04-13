from odoo import http
from odoo.http import request
import traceback
import logging

logger = logging.getLogger(__name__)


def convert_value_in_label(map_cols, value, key, return_severity=False):
    if not value:
        return "" if not return_severity else None

    for col in map_cols:
        if col.get('field') == key:
            for opt in col.get('options', []):
                if opt['value'] == value:
                    if return_severity:
                        return opt.get('severity', 'secondary')
                    return opt['label']
    return value if not return_severity else None


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

            fields_to_read = ["id", "name", "origin", "operator", "bin_id", "scheduled_date", "state", "wmds_status"]
            
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
                {"name": "Operador", "field": "operator", "type": "one2many", "non_blocked_field": True, "source": "operadores"},
                {"name": "BIN", "field": "bin_id", "type": "one2many", "non_blocked_field": True, "source": "get_available_bins"},
                {"name": "Fecha", "field": "scheduled_date"},
                {
                    "name": "Estado",
                    "field": "state",
                    "type": "selectable",
                    "options": [
                        {"value": "draft", "label": "Borrador", "severity": "secondary"},
                        {"value": "waiting", "label": "En espera de otra operación", "severity": "warning"},
                        {"value": "assigned", "label": "Disponible", "default": True, "severity": "info"},
                        {"value": "confirmed", "label": "En espera", "severity": "info"},
                        {"value": "done", "label": "Hecho", "severity": "success"},
                        {"value": "cancel", "label": "Cancelado", "severity": "danger"},
                    ]
                },
                {
                    "name": "Estado en WMDS",
                    "field": "wmds_status",
                    "type": "selectable",
                    "options": [
                        { "label": "No asignado", "value": "not_assigned", "default": True, "severity": "secondary" }, 
                        { "label": "No iniciado", "value": "not_started", "severity": "warning" },
                        { "label": "En progreso", "value": "in_progress", "severity": "info" },
                        { "label": "Completado", "value": "completed", "severity": "success" },
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
                
                bin_data = None
                if p.get('bin_id'):
                    bin_id, bin_name = p['bin_id']
                    bin_data = {
                        "name": bin_name,
                        "id": bin_id
                    }
                
                data.append({
                    "id": p['id'],
                    "name": p['name'],
                    "origin": p['origin'],
                    "operator": operator_data,
                    "bin_id": bin_data,
                    "scheduled_date": p['scheduled_date'],
                    "state": {
                        "label": convert_value_in_label(map_cols, p['state'], "state"),
                        "severity": convert_value_in_label(map_cols, p['state'], "state", return_severity=True)
                    },
                    "wmds_status": {
                        "label": convert_value_in_label(map_cols, p['wmds_status'], "wmds_status"),
                        "severity": convert_value_in_label(map_cols, p['wmds_status'], "wmds_status", return_severity=True)
                    }
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

            bin_data = kw.get('bin_id')
            bin_record = None
            if bin_data:
                bin_record = request.env['bin.storage'].sudo().search([('id', '=', bin_data["id"])], limit=1)

            for picking in target_pickings:
                if operator_record or (operator and not operator_mail):
                    picking.operator = operator_record.id if operator_record else operator["id"]
                
                if bin_record:
                    picking.bin_id = bin_record.id
                    # Propagate to moves (essential for Full/Wholesale)
                    picking.move_ids.write({
                        'bin_id': bin_record.id,
                        'on_bin': True,
                        'on_dock': False,
                        'dock_id': False
                    })
                    # Also update EI tags for ecommerce
                    if picking.sale_id:
                        ei_tags = request.env['sale.order.ei'].sudo().search([
                            ('so_id', '=', picking.sale_id.id),
                            ('dispatched', '=', False)
                        ])
                        ei_tags.write({
                            'bin_id': bin_record.id,
                            'on_bin': True,
                            'on_dock': False,
                            'dock_id': False
                        })

                if operation_type == "Pack" and operator_record:
                    request.env["wmds.log"].sudo().create({
                        'user': request.env.user.id,
                        'log': f"Se ha asignado el Pack {picking.name} a la mesa {operator_record.name}",
                        'pick': picking.id
                    })

            if batch_record:
                if operator_record:
                    batch_record.operator = operator_record.id
                if bin_record:
                    batch_record.bin_id = bin_record.id
                    # Update all moves in the batch
                    batch_record.picking_ids.mapped('move_ids').write({
                        'bin_id': bin_record.id,
                        'on_bin': True,
                        'on_dock': False,
                        'dock_id': False
                    })
                    # Update EI tags for all pickings in batch
                    so_ids = batch_record.picking_ids.mapped('sale_id.id')
                    if so_ids:
                        ei_tags = request.env['sale.order.ei'].sudo().search([
                            ('so_id', 'in', so_ids),
                            ('dispatched', '=', False)
                        ])
                        ei_tags.write({
                            'bin_id': bin_record.id,
                            'on_bin': True,
                            'on_dock': False,
                            'dock_id': False
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

            fields_to_read = ["id", "name", "origin", "operator", "bin_id", "scheduled_date", "state", "wmds_status"]
            
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
                {"name": "Operador", "field": "operator", "type": "one2many", "non_blocked_field": True, "source": "operadores"},
                {"name": "BIN", "field": "bin_id", "type": "one2many", "non_blocked_field": True, "source": "get_available_bins"},
                {"name": "Fecha", "field": "scheduled_date"},
                {
                    "name": "Estado",
                    "field": "state",
                    "type": "selectable",
                    "options": [
                        {"value": "draft", "label": "Borrador", "severity": "secondary"},
                        {"value": "waiting", "label": "En espera de otra operación", "severity": "warning"},
                        {"value": "assigned", "label": "Disponible", "default": True, "severity": "info"},
                        {"value": "confirmed", "label": "En espera", "severity": "info"},
                        {"value": "done", "label": "Hecho", "severity": "success"},
                        {"value": "cancel", "label": "Cancelado", "severity": "danger"},
                    ]
                },
                {
                    "name": "Estado en WMDS",
                    "field": "wmds_status",
                    "type": "selectable",
                    "options": [
                        { "label": "No asignado", "value": "not_assigned", "default": True, "severity": "secondary" }, 
                        { "label": "No iniciado", "value": "not_started", "severity": "warning" },
                        { "label": "En progreso", "value": "in_progress", "severity": "info" },
                        { "label": "Completado", "value": "completed", "severity": "success" },
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
                
                bin_data = None
                if p.get('bin_id'):
                    bin_id, bin_name = p['bin_id']
                    bin_data = {
                        "name": bin_name,
                        "id": bin_id
                    }
                
                data.append({
                    "id": p['id'],
                    "name": p['name'],
                    "origin": p['origin'],
                    "operator": operator_data,
                    "bin_id": bin_data,
                    "scheduled_date": p['scheduled_date'],
                    "state": {
                        "label": convert_value_in_label(map_cols, p['state'], "state"),
                        "severity": convert_value_in_label(map_cols, p['state'], "state", return_severity=True)
                    },
                    "wmds_status": {
                        "label": convert_value_in_label(map_cols, p['wmds_status'], "wmds_status"),
                        "severity": convert_value_in_label(map_cols, p['wmds_status'], "wmds_status", return_severity=True)
                    }
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
                "bin": {"id": batch.bin_id.id, "name": batch.bin_id.name} if batch.bin_id else None,
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
                "sort_order": kw.get('sort_order', 'desc'),
            }

            # Validar campos de ordenamiento que existen en el modelo
            valid_sort_fields = ['id', 'name', 'pick_type', 'operator', 'scheduled_date', 'state']
            if parsed_params['sort_by'] and parsed_params['sort_by'] not in valid_sort_fields:
                parsed_params['sort_by'] = 'id'
                parsed_params['sort_order'] = 'desc'

            # Eliminar parámetros de control y campos virtuales que no están en el modelo para el filtrado
            for popped_param in ['page', 'per_page', 'sort_by', 'sort_order', 'tz', 'picks', 'so_list']:
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
                {
                    "name": "Tipo", 
                    "field": "pick_type", 
                    "type": "selectable",
                    "options": [
                        {"value": "sale", "label": "Pedido", "severity": "info"},
                        {"value": "full", "label": "Fulfillment", "severity": "warning"},
                        {"value": "mix", "label": "Mixto", "severity": "secondary"},
                        {"value": "wholesale", "label": "Mayoreo", "severity": "contrast"}
                    ]
                },
                {"name": "Picks", "field": "picks", "sortable": False, "filterable": False},
                {"name": "Pedidos SO", "field": "so_list", "sortable": False, "filterable": False},
                {"name": "Operador", "field": "operator", "type": "one2many", "non_blocked_field": True, "source": "operadores"},
                {"name": "BIN", "field": "bin_id", "type": "one2many", "non_blocked_field": True, "source": "get_available_bins"},
                {"name": "Fecha Programada", "field": "scheduled_date"},
                {
                    "name": "Estado",
                    "field": "state",
                    "type": "selectable",
                    "options": [
                        {"value": "draft", "label": "Borrador", "severity": "secondary"},
                        {"value": "in_progress", "label": "En progreso", "default": True, "severity": "info"},
                        {"value": "done", "label": "Hecho", "severity": "success"},
                        {"value": "cancel", "label": "Cancelado", "severity": "danger"}
                    ]
                }
            ]

            data = []
            for b in batches:
                # Obtener picks y SOs únicos
                picks = ", ".join(list(dict.fromkeys(b.picking_ids.mapped('name'))))
                so_list = ", ".join(list(dict.fromkeys(filter(None, b.picking_ids.mapped('origin')))))

                data.append({
                    "id": b.id,
                    "name": b.name,
                    "pick_type": {
                        "label": convert_value_in_label(map_cols, b.pick_type, "pick_type"),
                        "severity": convert_value_in_label(map_cols, b.pick_type, "pick_type", return_severity=True)
                    },
                    "picks": picks,
                    "so_list": so_list,
                    "operator": None if not b.operator else {
                        "name": b.operator.name,
                        "id": b.operator.id,
                        "email": b.operator.login
                    },
                    "bin_id": None if not b.bin_id else {
                        "name": b.bin_id.name,
                        "id": b.bin_id.id
                    },
                    "scheduled_date": b.scheduled_date,
                    "state": {
                        "label": convert_value_in_label(map_cols, b.state, "state"),
                        "severity": convert_value_in_label(map_cols, b.state, "state", return_severity=True)
                    }
                })

            return {
                "map_cols": map_cols,
                "data": data,
                "total_count": total
            }

        except Exception as e:
            return {"error": f"{str(e)}\n{traceback.format_exc()}"}
