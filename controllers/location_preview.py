# -*- coding: utf-8 -*-
import logging
from datetime import datetime
import pytz
from odoo import http, fields
from odoo.http import request

logger = logging.getLogger(__name__)


def _human_relative_duration(from_dt, to_dt=None):
    """Calcula duración relativa legible en español entre from_dt y to_dt."""
    if not from_dt:
        return ""
    if not to_dt:
        to_dt = datetime.utcnow()
    
    # Asegurar que ambos son naive en UTC para la resta
    if hasattr(from_dt, 'tzinfo') and from_dt.tzinfo:
        from_dt = from_dt.astimezone(pytz.utc).replace(tzinfo=None)
    if hasattr(to_dt, 'tzinfo') and to_dt.tzinfo:
        to_dt = to_dt.astimezone(pytz.utc).replace(tzinfo=None)

    delta = to_dt - from_dt
    total_seconds = int(delta.total_seconds())
    if total_seconds < 0:
        return "hace unos instantes"

    if total_seconds < 60:
        return f"hace {total_seconds} segundo(s)"
    minutes = total_seconds // 60
    if minutes < 60:
        return f"hace {minutes} minuto(s)"
    hours = minutes // 60
    rem_minutes = minutes % 60
    if hours < 24:
        if rem_minutes > 0:
            return f"hace {hours} h y {rem_minutes} min"
        return f"hace {hours} hora(s)"
    days = hours // 24
    rem_hours = hours % 24
    if days < 30:
        if rem_hours > 0:
            return f"hace {days} día(s) y {rem_hours} h"
        return f"hace {days} día(s)"
    months = days // 30
    rem_days = days % 30
    if months < 12:
        if rem_days > 0:
            return f"hace {months} mes(es) y {rem_days} día(s)"
        return f"hace {months} mes(es)"
    years = days // 365
    return f"hace más de {years} año(s)"


class LocationPreviewController(http.Controller):

    @http.route('/wmds/v2/engine/get/location_preview', type='json', auth='user', methods=['POST'], csrf=True)
    def get_location_preview(self, **kw):
        """Devuelve información completa de una ubicación para el operador WMDS:
        - Stock teórico (stock.quant)
        - Estado de bloqueo (motivo, fecha desde cuándo, expiración)
        - Conteo cíclico activo
        - Reservas pendientes (stock.move.line)
        - Antigüedad de vacío si no contiene stock
        """
        barcode = (kw.get('barcode') or kw.get('location_barcode') or '').strip()
        client_tz = kw.get('tz') or request.env.user.tz or 'America/Mexico_City'

        if not barcode:
            return {
                "status": "error",
                "message": "Debe escanear o ingresar el código de una ubicación."
            }

        env = request.env['stock.location'].sudo()

        # 1. Búsqueda de ubicación
        location = env.search([('barcode', '=', barcode)], limit=1)
        if not location:
            location = env.search([('complete_name', '=', barcode)], limit=1)
        if not location:
            location = env.search([('name', '=', barcode)], limit=1)

        if not location:
            return {
                "status": "error",
                "message": f"Ubicación '{barcode}' no encontrada."
            }

        # Manejo de timezone para formateo de fechas
        try:
            tz = pytz.timezone(client_tz)
        except Exception:
            tz = pytz.timezone('UTC')

        def format_dt(dt_val):
            if not dt_val:
                return False
            # dt_val está en UTC en BD
            if not getattr(dt_val, 'tzinfo', None):
                utc_dt = pytz.utc.localize(dt_val)
            else:
                utc_dt = dt_val.astimezone(pytz.utc)
            local_dt = utc_dt.astimezone(tz)
            return local_dt.strftime('%Y-%m-%d %H:%M:%S')

        now_utc = datetime.utcnow()

        # 2. Stock Teórico (stock.quant)
        quants = request.env['stock.quant'].sudo().search([
            ('location_id', '=', location.id),
            ('quantity', '>', 0)
        ])

        stock_items = []
        total_units = 0.0
        total_reserved = 0.0

        for q in quants:
            p = q.product_id
            qty = q.quantity or 0.0
            reserved = q.reserved_quantity or 0.0
            avail = qty - reserved
            total_units += qty
            total_reserved += reserved

            stock_items.append({
                "quant_id": q.id,
                "product_id": p.id,
                "product_name": p.display_name,
                "default_code": p.default_code or '',
                "barcode": p.barcode or '',
                "image_url": f"/web/image/product.product/{p.id}/image_128",
                "lot_id": q.lot_id.id if q.lot_id else False,
                "lot_name": q.lot_id.name if q.lot_id else 'Sin lote',
                "quantity": qty,
                "reserved_quantity": reserved,
                "available_quantity": avail,
                "uom": q.product_uom_id.name if q.product_uom_id else ''
            })

        # 3. Estado de Bloqueo
        is_blocked = False
        if hasattr(location, 'is_location_blocked'):
            try:
                is_blocked = bool(location.is_location_blocked())
            except Exception:
                is_blocked = False

        if not is_blocked:
            is_blocked = bool(
                getattr(location, 'original_parent_id', False) or
                getattr(location, 'block_reason_type', False) or
                getattr(location, 'block_reason', False) or
                (location.location_id and any(w in (location.location_id.complete_name or '').lower() for w in ['bloquead', 'cuarentena'])) or
                any(w in (location.complete_name or '').lower() for w in ['bloquead', 'cuarentena'])
            )

        block_reason_type_code = getattr(location, 'block_reason_type', False)
        block_reason_type_label = False
        if block_reason_type_code and hasattr(location, '_fields') and 'block_reason_type' in location._fields:
            selection = dict(location._fields['block_reason_type'].selection or [])
            block_reason_type_label = selection.get(block_reason_type_code, block_reason_type_code)

        block_date_val = getattr(location, 'block_date', False)
        block_date_str = format_dt(block_date_val) if block_date_val else False
        block_date_rel = _human_relative_duration(block_date_val, now_utc) if block_date_val else False

        block_exp_val = getattr(location, 'block_expiration_date', False)
        block_exp_str = str(block_exp_val) if block_exp_val else False

        # Expiración de bloqueo
        is_block_expired = False
        if hasattr(location, 'is_block_expired'):
            is_block_expired = bool(location.is_block_expired)
        elif block_exp_val:
            today = fields.Date.context_today(location)
            is_block_expired = bool(block_exp_val < today)

        block_info = {
            "is_blocked": is_blocked,
            "block_reason_type": block_reason_type_label,
            "block_reason_type_code": block_reason_type_code,
            "block_reason": getattr(location, 'block_reason', False) or '',
            "block_user": location.block_user_id.name if getattr(location, 'block_user_id', False) else False,
            "block_ticket": getattr(location, 'block_ticket', False) or '',
            "block_date": block_date_str,
            "block_date_relative": block_date_rel,
            "block_expiration_date": block_exp_str,
            "is_block_expired": is_block_expired
        }

        # 4. Conteo Cíclico
        active_counts = request.env['scheduled.cycle.count'].sudo().search([
            ('state', 'in', ['created', 'in_progress'])
        ])

        cycle_count_matches = []
        if active_counts:
            # Buscar en selected_location_ids
            for ac in active_counts:
                matching_loc = ac.selected_location_ids.filtered(lambda sl: sl.location_id.id == location.id)
                if matching_loc:
                    state_selection = dict(ac._fields['state'].selection or [])
                    state_lbl = state_selection.get(ac.state, ac.state)

                    # Buscar olas asociadas
                    wave_names = []
                    operators = []
                    for wave in ac.wave_ids:
                        if wave.line_ids.filtered(lambda l: l.stock_location_id.id == location.id):
                            wave_names.append(wave.name)
                            if wave.operator_id and wave.operator_id.name not in operators:
                                operators.append(wave.operator_id.name)

                    cycle_count_matches.append({
                        "id": ac.id,
                        "name": ac.name,
                        "state": ac.state,
                        "state_label": state_lbl,
                        "wave_names": ", ".join(wave_names) if wave_names else "Sin ola asignada",
                        "operators": ", ".join(operators) if operators else "Sin operador asignado"
                    })

        cycle_info = {
            "in_cycle_count": bool(cycle_count_matches),
            "cycle_counts": cycle_count_matches
        }

        # 5. Reservas Pendientes (stock.move.line)
        pending_move_lines = request.env['stock.move.line'].sudo().search([
            ('location_id', '=', location.id),
            ('state', 'not in', ['done', 'cancel']),
            ('quantity', '>', 0)
        ])

        reservations = []
        for line in pending_move_lines:
            pick = line.picking_id
            reservations.append({
                "line_id": line.id,
                "picking_id": pick.id if pick else False,
                "picking_name": pick.name if pick else (line.move_id.reference or "Movimiento Interno"),
                "origin": pick.origin if pick and pick.origin else '',
                "picking_type": pick.picking_type_id.name if pick and pick.picking_type_id else '',
                "product_id": line.product_id.id,
                "product_name": line.product_id.display_name,
                "default_code": line.product_id.default_code or '',
                "image_url": f"/web/image/product.product/{line.product_id.id}/image_128",
                "quantity": line.quantity,
                "uom": line.product_uom_id.name if line.product_uom_id else '',
                "scheduled_date": format_dt(pick.scheduled_date) if pick and pick.scheduled_date else False
            })

        reservation_info = {
            "has_pending_reservations": bool(reservations),
            "reservations_count": len(reservations),
            "reservations": reservations
        }

        # 6. Antigüedad de Vacío
        is_empty = (len(stock_items) == 0 or total_units <= 0)
        empty_info = {
            "is_empty": is_empty,
            "empty_since": False,
            "empty_duration": False,
            "empty_reason": False,
            "last_product": False,
            "last_product_image_url": False
        }

        if is_empty:
            # Buscar último stock.move.line de salida o vaciado
            last_move = request.env['stock.move.line'].sudo().search([
                ('location_id', '=', location.id),
                ('state', '=', 'done')
            ], order='date desc, id desc', limit=1)

            if last_move and last_move.date:
                empty_since_dt = last_move.date
                empty_info["empty_since"] = format_dt(empty_since_dt)
                empty_info["empty_duration"] = _human_relative_duration(empty_since_dt, now_utc)
                ref = last_move.picking_id.name if last_move.picking_id else (last_move.move_id.reference or "Movimiento interno")
                empty_info["empty_reason"] = f"Última salida registrada en {ref}"
                empty_info["last_product"] = last_move.product_id.display_name
                empty_info["last_product_image_url"] = f"/web/image/product.product/{last_move.product_id.id}/image_128" if last_move.product_id else False
            else:
                create_dt = location.create_date
                empty_info["empty_since"] = format_dt(create_dt)
                empty_info["empty_duration"] = _human_relative_duration(create_dt, now_utc)
                empty_info["empty_reason"] = "Sin movimientos históricos de salida (vacía desde su creación)"
                empty_info["last_product"] = None
                empty_info["last_product_image_url"] = False

        return {
            "status": "ok",
            "location": {
                "id": location.id,
                "name": location.name,
                "complete_name": location.complete_name,
                "barcode": location.barcode or ''
            },
            "stock_summary": {
                "products_count": len(stock_items),
                "total_units": total_units,
                "total_reserved": total_reserved,
                "total_available": total_units - total_reserved,
                "items": stock_items
            },
            "blocking": block_info,
            "cycle_count": cycle_info,
            "reservations": reservation_info,
            "empty_status": empty_info
        }
