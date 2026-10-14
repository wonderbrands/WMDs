# -*- coding: utf-8 -*-
from odoo import http, fields
from odoo.http import request
from datetime import datetime, timedelta
import logging
import io
import base64
import xlsxwriter

_logger = logging.getLogger(__name__)

UTC_LOCAL = -6


def _channel_utc_offset(env, channel):
    """
    Devuelve las horas a SUMAR a un sla_date para obtener hora local.
    - Marketplace config 'utc'  -> sla_date en UTC, sumar UTC_LOCAL (-6).
    - Marketplace config 'local' o sin config -> sla_date ya en hora local, sumar 0.
    Parametrizable por marketplace vía wmds.mysql.config.sla_timezone.
    """
    if not channel:
        return 0
    ch = str(channel).strip()
    try:
        configs = env['wmds.mysql.config'].sudo().search([])
        for c in configs:
            m = (c.marketplace or '').strip()
            if m and (m.lower() == ch.lower() or m.lower() in ch.lower()):
                return UTC_LOCAL if c.sla_timezone == 'utc' else 0
    except Exception:
        pass
    return 0


def _channel_offset_sql(env):
    """
    Expresión SQL (CASE) que resuelve el offset en horas por canal para pasar sla_date a hora local.
    Marketplace 'utc' -> -6, 'local'/sin config -> 0. Parametrizable por wmds.mysql.config.
    Uso: sla_local = sla_date + ({expr} * interval '1 hour')
    """
    cases = []
    defaults = []
    try:
        configs = env['wmds.mysql.config'].sudo().search([])
        for c in configs:
            m = (c.marketplace or '').strip()
            if not m:
                continue
            off = UTC_LOCAL if c.sla_timezone == 'utc' else 0
            cases.append(f"WHEN lower(s.channel) LIKE '%%{m.lower()}%%' THEN {off}")
    except Exception:
        pass
    if cases:
        return "CASE " + " ".join(cases) + " ELSE 0 END"
    return "0"


class OrderChannelController(http.Controller):

    @http.route(
        '/wmds/v2/engine/get/order_channel_query',
        type='json',
        auth='user',
        methods=['POST'],
        csrf=True
    )
    def query_order_channel(self, **kw):
        """
        Query sales orders / pickings by text search, status filter, and channel filter.
        Also returns the dynamic list of available marketplace channels from DB.
        """
        try:
            query = (kw.get('query') or '').strip()
            status_filter = (kw.get('status_filter') or 'all').strip()
            channel_filter = (kw.get('channel_filter') or 'all').strip()
            date_from = (kw.get('date_from') or '').strip()
            date_to = (kw.get('date_to') or '').strip()
            limit = int(kw.get('limit') or 50)
            page = int(kw.get('page') or 1)
            offset = int(kw.get('offset') or ((page - 1) * limit if page > 1 else 0))

            env = request.env
            client_tz = kw.get('tz')
            if client_tz:
                env = env(context=dict(env.context, tz=client_tz))

            picking_model = env['stock.picking']
            sale_model = env['sale.order']

            now_utc = fields.Datetime.now()
            now_local = now_utc + timedelta(hours=UTC_LOCAL)
            in_1h_utc = now_utc + timedelta(hours=1)
            in_2h_utc = now_utc + timedelta(hours=2)
            in_6h_utc = now_utc + timedelta(hours=6)
            in_24h_utc = now_utc + timedelta(hours=24)

            # Obtener canales dinámicos únicos existentes en sale_order (Rápido en SQL)
            env.cr.execute("SELECT DISTINCT channel FROM sale_order WHERE channel IS NOT NULL AND channel != '' ORDER BY channel")
            raw_channels = [r[0] for r in env.cr.fetchall() if r[0]]
            available_channels = sorted(list(set(c.strip() for c in raw_channels if c and c.strip())))

            # Dominio base sobre SALE ORDER (1 fila por SO):
            # La fecha relevante es la del SLA de la ORDEN DE VENTA (no del OUT).
            # Solo órdenes activas pendientes (no sent, no shipped, no refunded, no canceladas)
            domain_so = [
                ('state', '!=', 'cancel'),
                ('order_progress', '!=', 'sent'),
                ('order_progress', 'not ilike', 'shipped'),
                ('order_progress', 'not ilike', 'refunded'),
                ('order_progress', 'not ilike', 'cancel'),
                ('yuju_shipping_status', '!=', 'sent'),
            ]

            # 2. Text Search Query (incluye posible picking/guía/folio)
            if query:
                matching_picks = picking_model.sudo().search([
                    '|', '|',
                    ('name', 'ilike', query),
                    ('carrier_tracking_ref', 'ilike', query),
                    ('origin', 'ilike', query)
                ], limit=100)
                so_ids_from_picks = matching_picks.mapped('sale_id').ids
                domain_so.extend([
                    '|', '|', '|',
                    ('name', 'ilike', query),
                    ('partner_id.name', 'ilike', query),
                    ('channel_order_id', 'ilike', query),
                    ('id', 'in', so_ids_from_picks)
                ])

            # 3. Channel Filter
            if channel_filter and channel_filter != 'all':
                domain_so.append(('channel', 'ilike', channel_filter))

            # 4. Determinar SO candidatas por fecha SLA (del último picking o yuju_due_date),
            #    filtrado en SQL para no truncar por "recientes" y coincidir con las métricas.
            so_where = [
                "s.state != 'cancel'",
                "(s.order_progress != 'sent' OR s.order_progress IS NULL)",
                "(s.order_progress NOT ILIKE '%%shipped%%' OR s.order_progress IS NULL)",
                "(s.order_progress NOT ILIKE '%%refunded%%' OR s.order_progress IS NULL)",
                "(s.order_progress NOT ILIKE '%%cancel%%' OR s.order_progress IS NULL)",
                "(s.yuju_shipping_status != 'sent' OR s.yuju_shipping_status IS NULL)",
                # Lista: solo pedidos NO ENVIADOS (sin OUT cerrado)
                """NOT EXISTS (
                    SELECT 1 FROM stock_picking o
                    JOIN stock_picking_type ot ON ot.id = o.picking_type_id
                    WHERE o.sale_id = s.id AND ot.code = 'outgoing' AND o.state = 'done'
                )""",
            ]
            sql_params = []
            if channel_filter and channel_filter != 'all':
                so_where.append("s.channel ILIKE %s")
                sql_params.append(f"%{channel_filter}%")

            # Filtro de fecha sobre el SLA efectivo (último picking sla_date o yuju_due_date),
            # convertido a hora local con offset por canal (parametrizable por marketplace).
            offset_expr = _channel_offset_sql(env)
            offset_frag = f"({offset_expr} * interval '1 hour')"
            if date_from or date_to:
                clauses = []
                if date_from:
                    clauses.append(f"(COALESCE(lp.sla_date, s.yuju_due_date::timestamp) + {offset_frag}) >= %s")
                if date_to:
                    clauses.append(f"(COALESCE(lp.sla_date, s.yuju_due_date::timestamp) + {offset_frag}) <= %s")
                so_where.append(f"({' AND '.join(clauses)})")
                if date_from:
                    sql_params.append(date_from)
                if date_to:
                    sql_params.append(f"{date_to} 23:59:59")

            # Búsqueda textual (SO o pálido)
            if query:
                pick_hits = picking_model.sudo().search([
                    '|', '|',
                    ('name', 'ilike', query),
                    ('carrier_tracking_ref', 'ilike', query),
                    ('origin', 'ilike', query)
                ], limit=200)
                hit_so_ids = list(dict.fromkeys(pick_hits.mapped('sale_id').ids))
                txt_clauses = ["(s.name ILIKE %s)", "(s.channel_order_id ILIKE %s)"]
                txt_params = [f"%{query}%", f"%{query}%"]
                if hit_so_ids:
                    txt_clauses.append("s.id IN %s")
                    txt_params.append(tuple(hit_so_ids))
                so_where.append(f"({' OR '.join(txt_clauses)})")
                sql_params.extend(txt_params)

            # Inyectar el SLA date del último pick vía LATERAL para el filtro de fecha
            sla_sel = "lp.sla_date" if date_from or date_to else "lp.sla_date"
            base_from = f"""
                FROM sale_order s
                LEFT JOIN LATERAL (
                    SELECT sla_date FROM stock_picking
                    WHERE sale_id = s.id ORDER BY id DESC LIMIT 1
                ) lp ON true
            """

            # Conteo total
            count_sql = f"SELECT COUNT(*) {base_from} WHERE {' AND '.join(so_where)}"
            env.cr.execute(count_sql, sql_params)
            total_count = env.cr.fetchone()[0]

            # Paginación SQL
            page_sql = f"""
                SELECT s.id {base_from}
                WHERE {' AND '.join(so_where)}
                ORDER BY s.id DESC
                LIMIT %s OFFSET %s
            """
            page_params = list(sql_params) + [limit, offset]
            env.cr.execute(page_sql, page_params)
            so_ids_page = [r[0] for r in env.cr.fetchall()]

            sale_orders = sale_model.sudo().browse(so_ids_page)

            # Construir mapa SO -> último picking (más recientemente creado)
            last_picks_by_so = {}
            if so_ids_page:
                picks = picking_model.sudo().search(
                    [('sale_id', 'in', so_ids_page)],
                    order='id desc'
                )
                for p in picks:
                    if p.sale_id and p.sale_id.id not in last_picks_by_so:
                        last_picks_by_so[p.sale_id.id] = p

            # Filas válidas para la página (recalcular SLA efectivo igual que las métricas)
            valid_sos = []
            for so in sale_orders:
                last_pick = last_picks_by_so.get(so.id, False)
                effective = last_pick.sla_date if last_pick else False
                if not effective:
                    yuju_due = getattr(so, 'yuju_due_date', False)
                    if yuju_due:
                        try:
                            clean = str(yuju_due).strip().replace('Z', '')
                            if 'T' in clean:
                                effective = datetime.fromisoformat(clean)
                            else:
                                effective = datetime.strptime(clean, "%Y-%m-%d %H:%M:%S")
                        except Exception:
                            pass

                if date_from or date_to:
                    if not effective:
                        continue
                    off = _channel_utc_offset(env, so.channel)
                    effective_local = effective + timedelta(hours=off)
                    if date_from:
                        try:
                            fd = datetime.fromisoformat(date_from) if 'T' in date_from else datetime.strptime(date_from, "%Y-%m-%d")
                            if effective_local < fd:
                                continue
                        except Exception:
                            pass
                    if date_to:
                        try:
                            td = datetime.fromisoformat(date_to) if 'T' in date_to else datetime.strptime(f"{date_to} 23:59:59", "%Y-%m-%d %H:%M:%S")
                            if effective_local > td:
                                continue
                        except Exception:
                            pass

                if status_filter != 'all':
                    if not effective:
                        if status_filter != 'no_sla':
                            continue
                    else:
                        is_local_ch = (_channel_utc_offset(env, so.channel) == 0)
                        target_now = now_local if is_local_ch else now_utc
                        in_1h = target_now + timedelta(hours=1)
                        in_2h = target_now + timedelta(hours=2)
                        in_6h = target_now + timedelta(hours=6)
                        in_24h = target_now + timedelta(hours=24)

                        if status_filter == 'overdue' and not (effective < target_now):
                            continue
                        elif status_filter == 'critical_1h' and not (target_now <= effective <= in_1h):
                            continue
                        elif status_filter == 'urgent_2h' and not (in_1h < effective <= in_2h):
                            continue
                        elif status_filter == 'warning_6h' and not (in_2h < effective <= in_6h):
                            continue
                        elif status_filter == 'notice_24h' and not (in_6h < effective <= in_24h):
                            continue
                        elif status_filter == 'normal' and not (effective > in_24h):
                            continue
                        elif status_filter == 'no_sla' and effective:
                            continue

                valid_sos.append((so, last_pick, effective))

            # NOTA: total_count NO se sobreescribe; ya vino del COUNT(*) SQL (línea 153).
            # valid_sos solo contiene la página actual.

            # BATCH de logs WMDS para todas las SO/filas válidas
            all_pick_ids = tuple(p.id for p in last_picks_by_so.values() if p and p.id)
            all_so_ids = tuple(s.id for s, _p, _e in valid_sos if s.id)

            wmds_logs = {}
            tmp_pick_ids = tuple(i for i in all_pick_ids if i)
            tmp_so_ids = tuple(i for i in all_so_ids if i)
            if tmp_pick_ids or tmp_so_ids:
                where_parts = []
                params = []
                if tmp_pick_ids:
                    where_parts.append("pick IN %s")
                    params.append(tmp_pick_ids)
                if tmp_so_ids:
                    where_parts.append("sale IN %s")
                    params.append(tmp_so_ids)
                sql_logs = f"""
                    SELECT pick, sale, log, date, "user"
                    FROM wmds_log
                    WHERE {" OR ".join(where_parts)}
                    ORDER BY date DESC, id DESC
                """
                env.cr.execute(sql_logs, params)
                for p_id, s_id, l_text, l_date, u_id in env.cr.fetchall():
                    l_date_str = fields.Datetime.to_string(l_date) if l_date else ''
                    if p_id and ('pick', p_id) not in wmds_logs:
                        wmds_logs[('pick', p_id)] = (l_text, l_date_str, u_id)
                    if s_id and ('sale', s_id) not in wmds_logs:
                        wmds_logs[('sale', s_id)] = (l_text, l_date_str, u_id)

            user_ids = set(v[2] for v in wmds_logs.values() if v[2])
            users_map = {}
            if user_ids:
                users = env['res.users'].sudo().browse(list(user_ids))
                users_map = {u.id: u.name for u in users}

            results = []
            # NOTA: la paginación ya la hace el SQL (LIMIT/OFFSET). valid_sos es la página.
            page_entries = valid_sos[:limit]
            for so, pick, effective in page_entries:
                so_name = so.name or ''
                channel = so.channel or ''
                fulfillment = so.fulfillment if so else ''
                yuju_due_date = getattr(so, 'yuju_due_date', False) or False

                # TZ de esta SO según su canal (parametrizable por marketplace)
                sla_tz_mode = 'local' if _channel_utc_offset(env, channel) == 0 else 'utc'

                has_pick = bool(pick)

                # Cómputo exacto en tiempo real del SLA sobre la fecha efectiva
                if effective:
                    sla_dt_str = fields.Datetime.to_string(effective)
                    target_now = now_local if sla_tz_mode == 'local' else now_utc
                    in_1h = target_now + timedelta(hours=1)
                    if effective < target_now:
                        sla_level = 'overdue'
                        sla_label = 'SLA Vencido'
                    elif effective <= in_1h:
                        sla_level = 'critical_1h'
                        sla_label = 'Está a punto de llegar la recolecta (< 1h)'
                    else:
                        diff_hours = (effective - target_now).total_seconds() / 3600.0
                        if diff_hours <= 2.0:
                            sla_level = 'urgent_2h'
                            sla_label = 'Quedan 2 horas para la recolecta'
                        elif diff_hours <= 6.0:
                            sla_level = 'warning_6h'
                            sla_label = 'Quedan 6 horas para la recolecta'
                        elif diff_hours <= 24.0:
                            sla_level = 'notice_24h'
                            sla_label = 'Queda 1 día para la recolecta'
                        else:
                            sla_level = 'normal'
                            sla_label = 'En tiempo'
                else:
                    sla_level = 'normal'
                    sla_label = ''
                    sla_dt_str = False

                log_info = None
                if pick:
                    log_info = wmds_logs.get(('pick', pick.id))
                if not log_info and so.id:
                    log_info = wmds_logs.get(('sale', so.id))

                latest_log = log_info[0] if log_info else ''
                latest_log_date = log_info[1] if log_info else ''
                latest_log_user = users_map.get(log_info[2], '') if log_info and log_info[2] else ''

                # Paquetería / Carrier y Guía
                carrier_name = ''
                tracking_ref = ''
                if pick:
                    if pick.carrier_id:
                        carrier_name = pick.carrier_id.name
                if so:
                    if not carrier_name and getattr(so, 'data_carrier_selection_relational', False):
                        carrier_name = so.data_carrier_selection_relational.name
                    elif not carrier_name and getattr(so, 'carrier_id', False):
                        carrier_name = so.carrier_id.name
                    elif not carrier_name and getattr(so, 'yuju_carrier', False):
                        carrier_name = so.yuju_carrier
                if pick and pick.carrier_tracking_ref:
                    tracking_ref = pick.carrier_tracking_ref
                elif so and getattr(so, 'yuju_carrier_tracking_ref', ''):
                    tracking_ref = so.yuju_carrier_tracking_ref

                # Fecha de creación en Odoo (create_date) y hora local CDMX
                so_create_date_str = fields.Datetime.to_string(so.create_date) if so and so.create_date else ''
                so_create_date_local = ''
                if so and so.create_date:
                    try:
                        so_create_date_local = (so.create_date - timedelta(hours=6)).strftime('%d/%m/%Y %H:%M')
                    except Exception:
                        so_create_date_local = so_create_date_str

                # Datos de Reasignación Manual de SLA
                is_manual_override = False
                override_reason = ''
                override_note = ''
                override_user = ''
                override_date = ''
                original_sla = ''

                if pick and getattr(pick, 'sla_manual_override', False):
                    is_manual_override = True
                    override_reason = getattr(pick, 'sla_override_reason', '') or ''
                    override_note = getattr(pick, 'sla_override_note', '') or ''
                    if getattr(pick, 'sla_override_user_id', False):
                        override_user = pick.sla_override_user_id.name
                    if getattr(pick, 'sla_override_date', False):
                        override_date = fields.Datetime.to_string(pick.sla_override_date)
                    if getattr(pick, 'sla_original_date', False):
                        original_sla = fields.Datetime.to_string(pick.sla_original_date)
                elif so and getattr(so, 'sla_manual_override', False):
                    is_manual_override = True
                    override_reason = getattr(so, 'sla_override_reason', '') or ''
                    override_note = getattr(so, 'sla_override_note', '') or ''
                    if getattr(so, 'sla_override_user_id', False):
                        override_user = so.sla_override_user_id.name
                    if getattr(so, 'sla_override_date', False):
                        override_date = fields.Datetime.to_string(so.sla_override_date)
                    if getattr(so, 'sla_original_date', False):
                        original_sla = fields.Datetime.to_string(so.sla_original_date)

                REASONS_MAP = {
                    'no_space': 'Falta de espacio en transporte',
                    'carrier_cutoff': 'Corte de paquetería',
                    'platform_rescheduled': 'Reprogramado por plataforma',
                    'customer_request': 'Petición del cliente',
                    'other': 'Otro motivo',
                }
                override_reason_label = REASONS_MAP.get(override_reason, override_reason)

                results.append({
                    'id': so.id,
                    'pick_id': pick.id if pick else False,
                    'name': pick.name if pick else '',
                    'sale_order_name': so_name,
                    'partner_name': so.partner_id.display_name if so.partner_id else '',
                    'channel': channel,
                    'fulfillment': fulfillment,
                    'carrier': carrier_name,
                    'carrier_tracking_ref': tracking_ref,
                    'state': pick.state if pick else '',
                    'has_pick': has_pick,
                    'scheduled_date': fields.Datetime.to_string(pick.scheduled_date) if pick and pick.scheduled_date else False,
                    'sla_date': sla_dt_str,
                    'sla_timezone': sla_tz_mode,
                    'sla_priority_level': sla_level,
                    'sla_priority_label': sla_label,
                    'yuju_due_date': str(yuju_due_date) if yuju_due_date else False,
                    'latest_wmds_log': latest_log,
                    'latest_wmds_log_user': latest_log_user,
                    'latest_wmds_log_date': latest_log_date,
                    'create_date': so_create_date_str,
                    'create_date_local': so_create_date_local,
                    'date_order': fields.Datetime.to_string(so.date_order) if so and so.date_order else '',
                    'sla_manual_override': is_manual_override,
                    'sla_override_reason': override_reason,
                    'sla_override_reason_label': override_reason_label,
                    'sla_override_note': override_note,
                    'sla_override_user': override_user,
                    'sla_override_date': override_date,
                    'sla_original_date': original_sla,
                })

            # Fecha SLA (local) más antigua por canal: pedido más rezagado entre pendientes activos
            channel_oldest = {}
            try:
                off_expr = _channel_offset_sql(env)
                env.cr.execute(f"""
                    SELECT COALESCE(s.channel, 'Directo/Otro') AS channel,
                           MIN(p.sla_date + ({off_expr} * interval '1 hour')) AS oldest
                    FROM stock_picking p
                    JOIN stock_picking_type pt ON pt.id = p.picking_type_id
                    JOIN sale_order s ON s.id = p.sale_id
                    WHERE p.sale_id IS NOT NULL
                      AND pt.code = 'outgoing'
                      AND s.state != 'cancel'
                      AND (s.order_progress != 'sent' OR s.order_progress IS NULL)
                      AND (s.order_progress NOT ILIKE '%%shipped%%' OR s.order_progress IS NULL)
                      AND (s.order_progress NOT ILIKE '%%refunded%%' OR s.order_progress IS NULL)
                      AND (s.order_progress NOT ILIKE '%%cancel%%' OR s.order_progress IS NULL)
                      AND (s.yuju_shipping_status != 'sent' OR s.yuju_shipping_status IS NULL)
                      AND p.state NOT IN ('done', 'cancel')
                      AND p.sla_date IS NOT NULL
                    GROUP BY COALESCE(s.channel, 'Directo/Otro')
                """)
                for ch, oldest in env.cr.fetchall():
                    if oldest:
                        channel_oldest[ch] = fields.Datetime.to_string(oldest)
            except Exception:
                pass

            return {
                'success': True,
                'count': len(results),
                'total_count': total_count,
                'page': page,
                'limit': limit,
                'available_channels': available_channels,
                'channel_oldest_date': channel_oldest,
                'results': results
            }

        except Exception as e:
            _logger.error(f"Error querying order channel: {e}", exc_info=True)
            return {'error': {'message': str(e)}}

    @http.route(
        '/wmds/v2/engine/get/order_sla_metrics',
        type='json',
        auth='user',
        methods=['POST'],
        csrf=True
    )
    def order_sla_metrics(self, **kw):
        """
        Métricas SLA por rango de fechas sobre la ORDEN DE VENTA.
        Universo = SO activas pendientes cuya fecha SLA (último picking sla_date o yuju_due_date)
        cae en el rango (hora local). Enviado = la SO tiene un OUT cerrado (done).
        """
        try:
            env = request.env
            date_from = (kw.get('date_from') or '').strip()
            date_to = (kw.get('date_to') or '').strip()
            channel_filter = (kw.get('channel_filter') or 'all').strip()

            where = [
                "s.state != 'cancel'",
                "(s.order_progress != 'sent' OR s.order_progress IS NULL)",
                "(s.order_progress NOT ILIKE '%%shipped%%' OR s.order_progress IS NULL)",
                "(s.order_progress NOT ILIKE '%%refunded%%' OR s.order_progress IS NULL)",
                "(s.order_progress NOT ILIKE '%%cancel%%' OR s.order_progress IS NULL)",
                "(s.yuju_shipping_status != 'sent' OR s.yuju_shipping_status IS NULL)",
            ]
            params = []
            if channel_filter and channel_filter != 'all':
                where.append("s.channel ILIKE %s")
                params.append(f"%{channel_filter}%")
            offset_expr = _channel_offset_sql(env)
            offset_frag = f"({offset_expr} * interval '1 hour')"
            if date_from:
                where.append(f"(COALESCE(lp.sla_date, s.yuju_due_date::timestamp) + {offset_frag}) >= %s")
                params.append(date_from)
            if date_to:
                where.append(f"(COALESCE(lp.sla_date, s.yuju_due_date::timestamp) + {offset_frag}) <= %s")
                params.append(f"{date_to} 23:59:59")

            from_clause = """
                FROM sale_order s
                LEFT JOIN LATERAL (
                    SELECT sla_date FROM stock_picking
                    WHERE sale_id = s.id ORDER BY id DESC LIMIT 1
                ) lp ON true
            """
            where_sql = " AND ".join(where)

            total_sql = f"SELECT COUNT(*) {from_clause} WHERE {where_sql}"
            env.cr.execute(total_sql, params)
            total_orders = env.cr.fetchone()[0]

            # Enviados = la SO tiene un OUT cerrado (done)
            sent_sql = f"""
                SELECT COUNT(*)
                FROM sale_order s2
                LEFT JOIN LATERAL (
                    SELECT sla_date FROM stock_picking
                    WHERE sale_id = s2.id ORDER BY id DESC LIMIT 1
                ) lp ON true
                WHERE {where_sql.replace('s.', 's2.')}
                  AND EXISTS (
                      SELECT 1 FROM stock_picking o
                      JOIN stock_picking_type ot ON ot.id = o.picking_type_id
                      WHERE o.sale_id = s2.id AND ot.code = 'outgoing' AND o.state = 'done'
                  )
            """
            env.cr.execute(sent_sql, params)
            sent_orders = env.cr.fetchone()[0]
            pending_orders = total_orders - sent_orders

            # En espera / sin stock: de los no enviados, último pick pendiente con moves sin reservar
            waiting_sql = f"""
                SELECT COUNT(*)
                FROM sale_order s3
                LEFT JOIN LATERAL (
                    SELECT id, sla_date FROM stock_picking
                    WHERE sale_id = s3.id ORDER BY id DESC LIMIT 1
                ) lp ON true
                WHERE {where_sql.replace('s.', 's3.')}
                  AND NOT EXISTS (
                      SELECT 1 FROM stock_picking o
                      JOIN stock_picking_type ot ON ot.id = o.picking_type_id
                      WHERE o.sale_id = s3.id AND ot.code = 'outgoing' AND o.state = 'done'
                  )
                  AND EXISTS (
                      SELECT 1 FROM stock_move m
                      WHERE m.picking_id = lp.id
                        AND m.state IN ('waiting', 'confirmed')
                        AND m.product_uom_qty > 0
                  )
            """
            env.cr.execute(waiting_sql, params)
            waiting_orders = env.cr.fetchone()[0]

            return {
                'success': True,
                'date_from': date_from,
                'date_to': date_to,
                'total_orders': total_orders,
                'sent_orders': sent_orders,
                'pending_orders': pending_orders,
                'waiting_orders': waiting_orders,
                'delivered_out_not_closed': 0,
            }

        except Exception as e:
            _logger.error(f"Error computing SLA metrics: {e}", exc_info=True)
            return {'error': {'message': str(e)}}

    @http.route(
        '/wmds/v2/engine/get/executed_operations_metrics',
        type='json',
        auth='user',
        methods=['POST'],
        csrf=True
    )
    def executed_operations_metrics(self, **kw):
        """
        Métricas de operaciones ejecutadas (Pick, Pack, OUT hechos) dentro del rango de fechas local (CDMX UTC-6).
        """
        try:
            env = request.env
            date_from = (kw.get('date_from') or '').strip()
            date_to = (kw.get('date_to') or '').strip()
            channel_filter = (kw.get('channel_filter') or 'all').strip()
            fulfillment_filter = (kw.get('fulfillment_filter') or 'all').strip().lower()

            if not date_from:
                date_from = fields.Date.context_today(env['stock.picking']).strftime('%Y-%m-%d')
            if not date_to:
                date_to = date_from

            where = [
                "p.state = 'done'",
                "p.date_done IS NOT NULL",
                "(p.date_done - interval '6 hour')::date >= %s::date",
                "(p.date_done - interval '6 hour')::date <= %s::date"
            ]
            params = [date_from, date_to]

            if channel_filter and channel_filter != 'all':
                where.append("s.channel ILIKE %s")
                params.append(f"%{channel_filter}%")

            if fulfillment_filter in ('fbm', 'drop'):
                where.append("(s.fulfillment IS NULL OR s.fulfillment NOT IN ('fbc', 'fbf'))")
            elif fulfillment_filter in ('full', 'fbc', 'fbf'):
                where.append("s.fulfillment IN ('fbc', 'fbf')")

            sql_metrics = f"""
                SELECT 
                    COUNT(*) FILTER (WHERE pt.sequence_code = 'PICK') AS picked_count,
                    COUNT(*) FILTER (WHERE pt.sequence_code = 'PACK') AS packed_count,
                    COUNT(*) FILTER (WHERE pt.sequence_code = 'OUT') AS dispatched_count,
                    COUNT(DISTINCT p.sale_id) FILTER (WHERE pt.sequence_code = 'OUT' AND p.sale_id IS NOT NULL) AS orders_dispatched_count,
                    COUNT(DISTINCT p.sale_id) FILTER (WHERE p.sale_id IS NOT NULL) AS total_orders_touched
                FROM stock_picking p
                JOIN stock_picking_type pt ON pt.id = p.picking_type_id
                LEFT JOIN sale_order s ON s.id = p.sale_id
                WHERE {' AND '.join(where)}
            """
            env.cr.execute(sql_metrics, params)
            row = env.cr.dictfetchone() or {}

            return {
                'success': True,
                'date_from': date_from,
                'date_to': date_to,
                'picked_count': row.get('picked_count') or 0,
                'packed_count': row.get('packed_count') or 0,
                'dispatched_count': row.get('dispatched_count') or 0,
                'orders_dispatched_count': row.get('orders_dispatched_count') or 0,
                'total_orders_touched': row.get('total_orders_touched') or 0,
            }
        except Exception as e:
            _logger.error(f"Error computing executed metrics: {e}", exc_info=True)
            return {'error': {'message': str(e)}}

    @http.route(
        '/wmds/v2/engine/get/executed_operations_query',
        type='json',
        auth='user',
        methods=['POST'],
        csrf=True
    )
    def executed_operations_query(self, **kw):
        """
        Detalle de operaciones ejecutadas con matices:
        - matiz_mode == 'by_sale': Órdenes de venta con estado WMDS y pipeline PICK/PACK/OUT.
        - matiz_mode == 'by_stage': Albaranes individuales (PICK, PACK, OUT) completados en el día.
        """
        try:
            env = request.env
            date_from = (kw.get('date_from') or '').strip()
            date_to = (kw.get('date_to') or '').strip()
            channel_filter = (kw.get('channel_filter') or 'all').strip()
            fulfillment_filter = (kw.get('fulfillment_filter') or 'all').strip().lower()
            matiz_mode = (kw.get('matiz_mode') or 'by_sale').strip()
            stage_filter = (kw.get('stage_filter') or 'all').strip().upper()
            query = (kw.get('query') or '').strip()
            limit = int(kw.get('limit') or 50)
            page = int(kw.get('page') or 1)
            offset = (page - 1) * limit if page > 1 else 0

            if not date_from:
                date_from = fields.Date.context_today(env['stock.picking']).strftime('%Y-%m-%d')
            if not date_to:
                date_to = date_from

            if matiz_mode == 'by_stage':
                where = [
                    "p.state = 'done'",
                    "p.date_done IS NOT NULL",
                    "(p.date_done - interval '6 hour')::date >= %s::date",
                    "(p.date_done - interval '6 hour')::date <= %s::date"
                ]
                params = [date_from, date_to]

                if stage_filter in ('PICK', 'PACK', 'OUT'):
                    where.append("pt.sequence_code = %s")
                    params.append(stage_filter)
                else:
                    where.append("pt.sequence_code IN ('PICK', 'PACK', 'OUT')")

                if channel_filter and channel_filter != 'all':
                    where.append("s.channel ILIKE %s")
                    params.append(f"%{channel_filter}%")

                if fulfillment_filter in ('fbm', 'drop'):
                    where.append("(s.fulfillment IS NULL OR s.fulfillment NOT IN ('fbc', 'fbf'))")
                elif fulfillment_filter in ('full', 'fbc', 'fbf'):
                    where.append("s.fulfillment IN ('fbc', 'fbf')")

                if query:
                    where.append("(p.name ILIKE %s OR s.name ILIKE %s OR p.carrier_tracking_ref ILIKE %s OR rp.name ILIKE %s)")
                    params.extend([f"%{query}%", f"%{query}%", f"%{query}%", f"%{query}%"])

                from_clause = """
                    FROM stock_picking p
                    JOIN stock_picking_type pt ON pt.id = p.picking_type_id
                    LEFT JOIN sale_order s ON s.id = p.sale_id
                    LEFT JOIN res_partner rp ON rp.id = s.partner_id
                    LEFT JOIN stock_picking_batch b ON b.id = p.batch_id
                    LEFT JOIN res_users ru_op ON ru_op.id = p.operator
                    LEFT JOIN res_partner u_op ON u_op.id = ru_op.partner_id
                    LEFT JOIN res_users ru_b ON ru_b.id = b.user_id
                    LEFT JOIN res_partner u_b ON u_b.id = ru_b.partner_id
                    LEFT JOIN res_users ru_p ON ru_p.id = p.user_id
                    LEFT JOIN res_partner u_p ON u_p.id = ru_p.partner_id
                    LEFT JOIN delivery_carrier c ON c.id = p.carrier_id
                    LEFT JOIN wmds_stock_status ws ON ws.id = p.wmds_status
                """
                count_sql = f"SELECT COUNT(*) {from_clause} WHERE {' AND '.join(where)}"
                env.cr.execute(count_sql, params)
                total_count = env.cr.fetchone()[0]

                query_sql = f"""
                    SELECT 
                        p.id,
                        p.name AS picking_name,
                        pt.sequence_code AS stage,
                        (p.date_done - interval '6 hour') AS date_done_local,
                        s.id AS sale_id,
                        s.name AS so_name,
                        COALESCE(s.channel, 'Directo/Otro') AS channel,
                        COALESCE(s.fulfillment, '') AS fulfillment,
                        COALESCE(rp.name, '') AS partner_name,
                        COALESCE(b.name, '') AS batch_name,
                        COALESCE(u_op.name, u_b.name, u_p.name, '') AS operator_name,
                        COALESCE(c.name->>'es_MX', c.name->>'en_US', '') AS carrier_name,
                        COALESCE(p.carrier_tracking_ref, '') AS carrier_tracking_ref,
                        COALESCE(ws.name, '') AS wmds_status_name
                    {from_clause}
                    WHERE {' AND '.join(where)}
                    ORDER BY p.date_done DESC, p.id DESC
                    LIMIT %s OFFSET %s
                """
                env.cr.execute(query_sql, params + [limit, offset])
                results = []
                for r in env.cr.dictfetchall():
                    dt_str = fields.Datetime.to_string(r['date_done_local']) if r['date_done_local'] else ''
                    stage_lbl = 'Recolección' if r['stage'] == 'PICK' else ('Empaque' if r['stage'] == 'PACK' else 'Despacho')
                    results.append({
                        'id': r['id'],
                        'name': r['picking_name'],
                        'stage': r['stage'],
                        'stage_label': stage_lbl,
                        'date_done': dt_str,
                        'sale_id': r['sale_id'],
                        'so_name': r['so_name'] or 'Sin SO',
                        'channel': r['channel'],
                        'fulfillment': r['fulfillment'],
                        'partner_name': r['partner_name'],
                        'batch_name': r['batch_name'],
                        'operator_name': r['operator_name'],
                        'carrier_name': r['carrier_name'],
                        'carrier_tracking_ref': r['carrier_tracking_ref'],
                        'wmds_status_name': r['wmds_status_name'],
                    })

                return {
                    'success': True,
                    'matiz_mode': matiz_mode,
                    'count': len(results),
                    'total_count': total_count,
                    'page': page,
                    'limit': limit,
                    'results': results
                }

            else:
                # matiz_mode == 'by_sale'
                where = [
                    "p.state = 'done'",
                    "p.sale_id IS NOT NULL",
                    "p.date_done IS NOT NULL",
                    "(p.date_done - interval '6 hour')::date >= %s::date",
                    "(p.date_done - interval '6 hour')::date <= %s::date"
                ]
                params = [date_from, date_to]

                if channel_filter and channel_filter != 'all':
                    where.append("s.channel ILIKE %s")
                    params.append(f"%{channel_filter}%")

                if fulfillment_filter in ('fbm', 'drop'):
                    where.append("(s.fulfillment IS NULL OR s.fulfillment NOT IN ('fbc', 'fbf'))")
                elif fulfillment_filter in ('full', 'fbc', 'fbf'):
                    where.append("s.fulfillment IN ('fbc', 'fbf')")

                if query:
                    where.append("(s.name ILIKE %s OR s.channel_order_id ILIKE %s OR rp.name ILIKE %s)")
                    params.extend([f"%{query}%", f"%{query}%", f"%{query}%"])

                base_where = " AND ".join(where)

                count_sql = f"""
                    SELECT COUNT(DISTINCT s.id)
                    FROM stock_picking p
                    JOIN sale_order s ON s.id = p.sale_id
                    LEFT JOIN res_partner rp ON rp.id = s.partner_id
                    WHERE {base_where}
                """
                env.cr.execute(count_sql, params)
                total_count = env.cr.fetchone()[0]

                page_sql = f"""
                    SELECT 
                        s.id AS sale_id,
                        s.name AS so_name,
                        COALESCE(s.channel, 'Directo/Otro') AS channel,
                        COALESCE(s.fulfillment, '') AS fulfillment,
                        s.date_order,
                        COALESCE(rp.name, '') AS partner_name,
                        COALESCE(c.name->>'es_MX', c.name->>'en_US', '') AS carrier_name,
                        COALESCE(s.order_progress, '') AS order_progress,
                        COALESCE(ws.value, '') AS wmds_status_value,
                        COALESCE(ws.name, '') AS wmds_status_name,
                        MAX(p.date_done) AS latest_done
                    FROM stock_picking p
                    JOIN sale_order s ON s.id = p.sale_id
                    LEFT JOIN res_partner rp ON rp.id = s.partner_id
                    LEFT JOIN delivery_carrier c ON c.id = s.carrier_id
                    LEFT JOIN wmds_stock_status ws ON ws.id = s.wmds_status
                    WHERE {base_where}
                    GROUP BY s.id, s.name, s.channel, s.fulfillment, s.date_order, rp.name, c.name, s.order_progress, ws.value, ws.name
                    ORDER BY latest_done DESC, s.id DESC
                    LIMIT %s OFFSET %s
                """
                env.cr.execute(page_sql, params + [limit, offset])
                so_rows = env.cr.dictfetchall()
                so_ids = [r['sale_id'] for r in so_rows]

                picks_map = {}
                if so_ids:
                    env.cr.execute("""
                        SELECT 
                            p.id,
                            p.name,
                            p.state,
                            p.sale_id,
                            pt.sequence_code,
                            (p.date_done - interval '6 hour') AS date_done_local,
                            COALESCE(b.name, '') AS batch_name,
                            COALESCE(u_op.name, u_b.name, u_p.name, '') AS operator_name,
                            COALESCE(c.name->>'es_MX', c.name->>'en_US', '') AS carrier_name,
                            COALESCE(p.carrier_tracking_ref, '') AS carrier_tracking_ref
                        FROM stock_picking p
                        JOIN stock_picking_type pt ON pt.id = p.picking_type_id
                        LEFT JOIN stock_picking_batch b ON b.id = p.batch_id
                        LEFT JOIN res_users ru_op ON ru_op.id = p.operator
                        LEFT JOIN res_partner u_op ON u_op.id = ru_op.partner_id
                        LEFT JOIN res_users ru_b ON ru_b.id = b.user_id
                        LEFT JOIN res_partner u_b ON u_b.id = ru_b.partner_id
                        LEFT JOIN res_users ru_p ON ru_p.id = p.user_id
                        LEFT JOIN res_partner u_p ON u_p.id = ru_p.partner_id
                        LEFT JOIN delivery_carrier c ON c.id = p.carrier_id
                        WHERE p.sale_id IN %s
                          AND pt.sequence_code IN ('PICK', 'PACK', 'OUT')
                        ORDER BY p.id ASC
                    """, (tuple(so_ids),))
                    for p_row in env.cr.dictfetchall():
                        s_id = p_row['sale_id']
                        if s_id not in picks_map:
                            picks_map[s_id] = {}
                        sc = p_row['sequence_code']
                        p_row['date_done'] = fields.Datetime.to_string(p_row['date_done_local']) if p_row['date_done_local'] else ''
                        picks_map[s_id][sc] = p_row

                results = []
                for so in so_rows:
                    s_id = so['sale_id']
                    pm = picks_map.get(s_id, {})
                    pick_data = pm.get('PICK', {})
                    pack_data = pm.get('PACK', {})
                    out_data = pm.get('OUT', {})

                    if out_data.get('state') == 'done':
                        summary_step = 'out'
                    elif pack_data.get('state') == 'done':
                        summary_step = 'pack'
                    elif pick_data.get('state') == 'done':
                        summary_step = 'pick'
                    else:
                        summary_step = 'pending'

                    results.append({
                        'sale_id': s_id,
                        'so_name': so['so_name'],
                        'channel': so['channel'],
                        'fulfillment': so.get('fulfillment') or '',
                        'date_order': fields.Datetime.to_string(so['date_order']) if so['date_order'] else '',
                        'partner_name': so['partner_name'],
                        'carrier_name': so['carrier_name'] or out_data.get('carrier_name', ''),
                        'order_progress': so['order_progress'],
                        'wmds_status_value': so['wmds_status_value'],
                        'wmds_status_name': so['wmds_status_name'],
                        'summary_step': summary_step,
                        'stages': {
                            'pick': {
                                'name': pick_data.get('name', ''),
                                'state': pick_data.get('state', ''),
                                'date_done': pick_data.get('date_done', ''),
                                'batch_name': pick_data.get('batch_name', ''),
                                'operator_name': pick_data.get('operator_name', '')
                            },
                            'pack': {
                                'name': pack_data.get('name', ''),
                                'state': pack_data.get('state', ''),
                                'date_done': pack_data.get('date_done', ''),
                                'operator_name': pack_data.get('operator_name', '')
                            },
                            'out': {
                                'name': out_data.get('name', ''),
                                'state': out_data.get('state', ''),
                                'date_done': out_data.get('date_done', ''),
                                'carrier_name': out_data.get('carrier_name', ''),
                                'carrier_tracking_ref': out_data.get('carrier_tracking_ref', '')
                            }
                        }
                    })

                return {
                    'success': True,
                    'matiz_mode': matiz_mode,
                    'count': len(results),
                    'total_count': total_count,
                    'page': page,
                    'limit': limit,
                    'results': results
                }

        except Exception as e:
            _logger.error(f"Error querying executed operations: {e}", exc_info=True)
            return {'error': {'message': str(e)}}

    @http.route(
        '/wmds/v2/engine/get/sla_expiring_alerts',
        type='json',
        auth='user',
        methods=['POST'],
        csrf=True
    )
    def check_sla_expiring_alerts(self, **kw):
        """
        Return count of active pickings expiring in < 1h vs overdue, and pending orders by marketplace.
        Supports optional channel_filter parameter.
        """
        try:
            env = request.env
            channel_filter = (kw.get('channel_filter') or 'all').strip()

            now_utc = fields.Datetime.now()
            in_1h_utc = now_utc + timedelta(hours=1)

            # Query general de conteo de pendientes activos agrupados por marketplace
            env.cr.execute('''
                SELECT 
                    COALESCE(s.channel, 'Directo/Otro') AS channel,
                    COUNT(DISTINCT s.id) AS pending_count
                FROM sale_order s
                JOIN stock_picking p ON p.sale_id = s.id
                WHERE s.state != 'cancel'
                  AND (s.order_progress != 'sent' OR s.order_progress IS NULL)
                  AND (s.order_progress NOT ILIKE '%shipped%' OR s.order_progress IS NULL)
                  AND (s.order_progress NOT ILIKE '%refunded%' OR s.order_progress IS NULL)
                  AND (s.order_progress NOT ILIKE '%cancel%' OR s.order_progress IS NULL)
                  AND (s.yuju_shipping_status != 'sent' OR s.yuju_shipping_status IS NULL)
                  AND p.state NOT IN ('done', 'cancel')
                GROUP BY COALESCE(s.channel, 'Directo/Otro')
                ORDER BY pending_count DESC
            ''')
            marketplace_pending = {row[0]: row[1] for row in env.cr.fetchall()}
            total_pending = sum(marketplace_pending.values())

            # Query con LATERAL para contar críticos y vencidos por último picking de cada SO activa
            filter_clause = ""
            params = []
            if channel_filter and channel_filter != 'all':
                filter_clause = " AND s.channel = %s "
                params.append(channel_filter)

            sql_alerts = f'''
                SELECT p.sla_date
                FROM sale_order s
                JOIN LATERAL (
                    SELECT state, sla_date
                    FROM stock_picking
                    WHERE sale_id = s.id
                    ORDER BY id DESC
                    LIMIT 1
                ) p ON true
                WHERE s.state != 'cancel'
                  AND (s.order_progress != 'sent' OR s.order_progress IS NULL)
                  AND (s.order_progress NOT ILIKE '%shipped%' OR s.order_progress IS NULL)
                  AND (s.order_progress NOT ILIKE '%refunded%' OR s.order_progress IS NULL)
                  AND (s.order_progress NOT ILIKE '%cancel%' OR s.order_progress IS NULL)
                  AND (s.yuju_shipping_status != 'sent' OR s.yuju_shipping_status IS NULL)
                  AND p.state NOT IN ('done', 'cancel')
                  AND p.sla_date IS NOT NULL
                  {filter_clause}
            '''
            env.cr.execute(sql_alerts, params)
            rows = env.cr.fetchall()

            critical_count = 0
            overdue_count = 0
            for (sla_date,) in rows:
                if sla_date < now_utc:
                    overdue_count += 1
                elif now_utc <= sla_date <= in_1h_utc:
                    critical_count += 1

            # Pendientes filtrados para el canal actual
            current_pending = marketplace_pending.get(channel_filter, 0) if channel_filter != 'all' else total_pending

            return {
                'success': True,
                'critical_count': critical_count,
                'overdue_count': overdue_count,
                'total_alerts': critical_count + overdue_count,
                'total_pending': total_pending,
                'current_channel_pending': current_pending,
                'marketplace_pending': marketplace_pending
            }

        except Exception as e:
            _logger.error(f"Error fetching SLA expiring alerts: {e}", exc_info=True)
            return {'error': {'message': str(e)}}

    @http.route(
        '/wmds/v2/engine/get/marketplace_schedules',
        type='json',
        auth='user',
        methods=['POST'],
        csrf=True
    )
    def get_marketplace_schedules(self, **kw):
        """
        Return list of configured marketplace SLA schedules and available marketplace channels from DB.
        """
        try:
            env = request.env
            schedules = env['marketplace.schedule'].sudo().search([])
            res = []
            for s in schedules:
                res.append({
                    'id': s.id,
                    'marketplace': s.marketplace,
                    'sla_source': s.sla_source,
                    'monday_to_friday_': s.monday_to_friday_,
                    'saturday': s.saturday,
                    'sunday': s.sunday,
                    'flex': s.flex,
                    'sameDay_nextDay': s.sameDay_nextDay,
                    'auto_fill_dates': s.auto_fill_dates,
                })

            env.cr.execute("SELECT DISTINCT channel FROM sale_order WHERE channel IS NOT NULL AND channel != '' ORDER BY channel")
            raw_channels = [r[0] for r in env.cr.fetchall() if r[0]]
            available_channels = sorted(list(set(c.strip() for c in raw_channels if c and c.strip())))

            return {
                'success': True,
                'schedules': res,
                'available_channels': available_channels
            }
        except Exception as e:
            _logger.error(f"Error getting marketplace schedules: {e}", exc_info=True)
            return {'error': {'message': str(e)}}

    @http.route(
        '/wmds/v2/engine/save/marketplace_schedule',
        type='json',
        auth='user',
        methods=['POST'],
        csrf=True
    )
    def save_marketplace_schedule(self, **kw):
        """
        Create or update a marketplace SLA schedule rule.
        """
        try:
            env = request.env
            data = kw.get('data') or {}
            m_id = data.get('id')
            marketplace = (data.get('marketplace') or '').strip()
            if not marketplace:
                return {'error': {'message': 'El marketplace es requerido'}}

            vals = {
                'marketplace': marketplace,
                'sla_source': data.get('sla_source', 'auto'),
                'monday_to_friday_': float(data.get('monday_to_friday_') or 0.0),
                'saturday': float(data.get('saturday') or 0.0),
                'sunday': float(data.get('sunday') or 0.0),
                'flex': int(data.get('flex') or 0),
                'sameDay_nextDay': int(data.get('sameDay_nextDay') or 0),
                'auto_fill_dates': bool(data.get('auto_fill_dates')),
            }

            if m_id:
                sch = env['marketplace.schedule'].sudo().browse(int(m_id))
                sch.write(vals)
            else:
                existing = env['marketplace.schedule'].sudo().search([('marketplace', '=', marketplace)], limit=1)
                if existing:
                    existing.write(vals)
                    m_id = existing.id
                else:
                    sch = env['marketplace.schedule'].sudo().create(vals)
                    m_id = sch.id

            return {'success': True, 'id': m_id}
        except Exception as e:
            _logger.error(f"Error saving marketplace schedule: {e}", exc_info=True)
            return {'error': {'message': str(e)}}

    @http.route(
        '/wmds/v2/engine/delete/marketplace_schedule',
        type='json',
        auth='user',
        methods=['POST'],
        csrf=True
    )
    def delete_marketplace_schedule(self, **kw):
        """
        Delete a marketplace SLA schedule rule.
        """
        try:
            env = request.env
            m_id = kw.get('id')
            if m_id:
                env['marketplace.schedule'].sudo().browse(int(m_id)).unlink()
            return {'success': True}
        except Exception as e:
            _logger.error(f"Error deleting marketplace schedule: {e}", exc_info=True)
            return {'error': {'message': str(e)}}

    @http.route(
        '/wmds/v2/engine/reassign_sla',
        type='json',
        auth='user',
        methods=['POST'],
        csrf=True
    )
    def reassign_sla(self, **kw):
        """
        Reasignación manual de SLA desde la interfaz WMDS.
        """
        try:
            env = request.env
            order_id = kw.get('order_id')
            pick_id = kw.get('pick_id')
            new_sla_str = (kw.get('new_sla_date') or '').strip()
            reason = (kw.get('reason') or 'no_space').strip()
            note = (kw.get('note') or '').strip()

            if not new_sla_str:
                return {'error': {'message': 'Debe especificar la nueva fecha y hora para el SLA.'}}

            new_sla_dt = fields.Datetime.to_datetime(new_sla_str)
            now_dt = fields.Datetime.now()
            user_id = env.user.id
            user_name = env.user.name

            REASONS_MAP = {
                'no_space': 'Falta de espacio en transporte / unidad',
                'carrier_cutoff': 'Corte de paquetería / retraso de recolección',
                'platform_rescheduled': 'Reprogramado por marketplace / plataforma',
                'customer_request': 'Petición del cliente',
                'other': 'Otro motivo',
            }
            reason_lbl = REASONS_MAP.get(reason, reason)

            pick = env['stock.picking'].sudo().browse(int(pick_id)) if pick_id else None
            so = env['sale.order'].sudo().browse(int(order_id)) if order_id else None
            if not so and pick and getattr(pick, 'sale_id', False):
                so = pick.sale_id

            picks = [pick] if pick and pick.exists() else []
            if so and not picks:
                picks = list(env['stock.picking'].sudo().search([
                    ('sale_id', '=', so.id),
                    ('state', 'not in', ('done', 'cancel'))
                ]))

            msg = (
                f"<b>SLA Reasignado Manualmente por {user_name}</b><br/>"
                f"<b>Nueva Fecha SLA:</b> {new_sla_str}<br/>"
                f"<b>Motivo:</b> {reason_lbl}<br/>"
            )
            if note:
                msg += f"<b>Notas:</b> {note}<br/>"

            for p in picks:
                vals = {
                    'sla_date': new_sla_dt,
                    'priority_date': new_sla_dt,
                    'sla_manual_override': True,
                    'sla_override_reason': reason,
                    'sla_override_note': note,
                    'sla_override_date': now_dt,
                    'sla_override_user_id': user_id,
                }
                if not getattr(p, 'sla_original_date', False) and p.sla_date:
                    vals['sla_original_date'] = p.sla_date
                p.write(vals)
                try:
                    p.message_post(body=msg)
                except Exception:
                    pass

            if picks and hasattr(picks[0], '_compute_sla_priority'):
                for p in picks:
                    p._compute_sla_priority()

            if so and so.exists():
                so_vals = {
                    'sla_manual_override': True,
                    'sla_override_reason': reason,
                    'sla_override_note': note,
                    'sla_override_date': now_dt,
                    'sla_override_user_id': user_id,
                }
                so.write(so_vals)
                try:
                    so.message_post(body=msg)
                except Exception:
                    pass

            # Crear log WMDS
            if 'wmds.log' in env:
                try:
                    for p in (picks or [None]):
                        env['wmds.log'].sudo().create({
                            'stock_picking': p.id if p else False,
                            'sale_order': so.id if so else False,
                            'user': user_id,
                            'date': now_dt,
                            'log': f"SLA Empujado/Reasignado a {new_sla_str}. Motivo: {reason_lbl}."
                        })
                except Exception:
                    pass

            return {'success': True, 'message': f"SLA actualizado exitosamente a {new_sla_str}"}
        except Exception as e:
            _logger.error(f"Error reassigning SLA: {e}", exc_info=True)
            return {'error': {'message': str(e)}}

    @http.route(
        '/wmds/v2/engine/export_order_channel_excel',
        type='json',
        auth='user',
        methods=['POST'],
        csrf=True
    )
    def export_order_channel_excel(self, **kw):
        """
        Exporta a Excel los datos actuales de la pestaña SLA o de Ejecución de Almacén.
        """
        try:
            env = request.env
            tab = kw.get('tab') or 'sla'
            date_from = (kw.get('date_from') or '').strip()
            date_to = (kw.get('date_to') or '').strip()
            channel_filter = (kw.get('channel_filter') or 'all').strip()
            status_filter = (kw.get('status_filter') or 'all').strip()
            fulfillment_filter = (kw.get('fulfillment_filter') or 'all').strip()
            matiz_mode = (kw.get('matiz_mode') or 'by_sale').strip()
            stage_filter = (kw.get('stage_filter') or 'all').strip().upper()
            query = (kw.get('query') or '').strip()

            output_stream = io.BytesIO()
            wb = xlsxwriter.Workbook(output_stream, {'in_memory': True})

            fmt_title = wb.add_format({'bold': True, 'font_size': 14, 'font_color': '#1e293b'})
            fmt_subtitle = wb.add_format({'font_size': 10, 'font_color': '#64748b'})
            fmt_header = wb.add_format({'bold': True, 'bg_color': '#1e3a8a', 'font_color': '#ffffff', 'border': 1, 'align': 'center', 'valign': 'vcenter', 'font_size': 10})
            fmt_cell = wb.add_format({'border': 1, 'align': 'left', 'valign': 'vcenter', 'font_size': 9})
            fmt_cell_center = wb.add_format({'border': 1, 'align': 'center', 'valign': 'vcenter', 'font_size': 9})

            if tab == 'sla':
                ws = wb.add_worksheet('SLA Pedidos')
                ws.write(0, 0, "REPORTE DE SLA DE PEDIDOS - WMDS", fmt_title)
                ws.write(1, 0, f"Generado: {fields.Datetime.now().strftime('%d/%m/%Y %H:%M:%S')} (UTC) | Canal: {channel_filter} | Estatus: {status_filter}", fmt_subtitle)

                headers = [
                    "Orden de Venta", "Albarán", "Canal", "Fulfillment", "Paquetería", 
                    "No. Guía", "Estado Albarán", "Ingreso a Odoo (CDMX)", "Fecha SLA Límite", 
                    "Nivel SLA", "Aviso SLA", "SLA Reasignado", "Motivo Reasignación", "Último Log WMDS"
                ]
                for col_idx, h in enumerate(headers):
                    ws.write(3, col_idx, h, fmt_header)

                res_query = self.order_channel_query(
                    page=1, limit=5000,
                    date_from=date_from, date_to=date_to,
                    channel_filter=channel_filter, status_filter=status_filter,
                    query=query
                )
                rows = res_query.get('results', [])
                for row_idx, r in enumerate(rows, start=4):
                    ws.write(row_idx, 0, r.get('sale_order_name') or '', fmt_cell)
                    ws.write(row_idx, 1, r.get('name') or '', fmt_cell)
                    ws.write(row_idx, 2, r.get('channel') or '', fmt_cell_center)
                    ws.write(row_idx, 3, (r.get('fulfillment') or 'FBM').upper(), fmt_cell_center)
                    ws.write(row_idx, 4, r.get('carrier') or '', fmt_cell)
                    ws.write(row_idx, 5, r.get('carrier_tracking_ref') or '', fmt_cell)
                    ws.write(row_idx, 6, r.get('state') or '', fmt_cell_center)
                    ws.write(row_idx, 7, r.get('create_date_local') or '', fmt_cell_center)
                    ws.write(row_idx, 8, r.get('sla_date') or '', fmt_cell_center)
                    ws.write(row_idx, 9, r.get('sla_priority_level') or '', fmt_cell_center)
                    ws.write(row_idx, 10, r.get('sla_priority_label') or '', fmt_cell)
                    ws.write(row_idx, 11, 'SÍ' if r.get('sla_manual_override') else 'NO', fmt_cell_center)
                    ws.write(row_idx, 12, r.get('sla_override_reason_label') or '', fmt_cell)
                    ws.write(row_idx, 13, r.get('latest_wmds_log') or '', fmt_cell)

                col_widths = [18, 18, 16, 12, 18, 20, 14, 20, 20, 14, 28, 14, 25, 40]
                for c_i, w in enumerate(col_widths):
                    ws.set_column(c_i, c_i, w)

                filename = f"WMDs_SLA_Pedidos_{fields.Date.today()}.xlsx"

            else:
                res_exec = self.executed_operations_query(
                    page=1, limit=5000,
                    date_from=date_from, date_to=date_to,
                    channel_filter=channel_filter,
                    fulfillment_filter=fulfillment_filter,
                    matiz_mode=matiz_mode,
                    stage_filter=stage_filter,
                    query=query
                )
                rows = res_exec.get('results', [])

                if matiz_mode == 'by_stage':
                    ws = wb.add_worksheet('Operaciones Por Etapa')
                    ws.write(0, 0, "OPERACIONES DE ALMACÉN (POR ETAPA)", fmt_title)
                    ws.write(1, 0, f"Rango: {date_from} a {date_to} | Canal: {channel_filter} | Etapa: {stage_filter} | Fulfillment: {fulfillment_filter}", fmt_subtitle)
                    headers = ["Albarán", "Etapa", "Fecha Hecho (CDMX)", "Orden Venta", "Canal", "Fulfillment", "Cliente", "Ola / Batch", "Operador", "Paquetería", "Guía"]
                    for col_idx, h in enumerate(headers):
                        ws.write(3, col_idx, h, fmt_header)
                    for row_idx, r in enumerate(rows, start=4):
                        ws.write(row_idx, 0, r.get('name') or '', fmt_cell)
                        ws.write(row_idx, 1, r.get('stage_label') or r.get('stage') or '', fmt_cell_center)
                        ws.write(row_idx, 2, r.get('date_done') or '', fmt_cell_center)
                        ws.write(row_idx, 3, r.get('so_name') or '', fmt_cell)
                        ws.write(row_idx, 4, r.get('channel') or '', fmt_cell_center)
                        ws.write(row_idx, 5, (r.get('fulfillment') or 'FBM').upper(), fmt_cell_center)
                        ws.write(row_idx, 6, r.get('partner_name') or '', fmt_cell)
                        ws.write(row_idx, 7, r.get('batch_name') or '', fmt_cell)
                        ws.write(row_idx, 8, r.get('operator_name') or '', fmt_cell)
                        ws.write(row_idx, 9, r.get('carrier_name') or '', fmt_cell)
                        ws.write(row_idx, 10, r.get('carrier_tracking_ref') or '', fmt_cell)
                    col_widths = [18, 14, 20, 18, 16, 12, 24, 16, 20, 18, 20]
                    for c_i, w in enumerate(col_widths):
                        ws.set_column(c_i, c_i, w)
                else:
                    ws = wb.add_worksheet('Operaciones Por Venta')
                    ws.write(0, 0, "OPERACIONES DE ALMACÉN (POR VENTA)", fmt_title)
                    ws.write(1, 0, f"Rango: {date_from} a {date_to} | Canal: {channel_filter} | Fulfillment: {fulfillment_filter}", fmt_subtitle)
                    headers = ["Orden de Venta", "Canal", "Fulfillment", "Fecha Venta", "Cliente", "Progreso", "Estado WMDS", "Paso Actual", "PICK Albarán", "PICK Hecho", "PACK Albarán", "PACK Hecho", "OUT Albarán", "OUT Hecho", "Paquetería", "Guía"]
                    for col_idx, h in enumerate(headers):
                        ws.write(3, col_idx, h, fmt_header)
                    for row_idx, r in enumerate(rows, start=4):
                        stg = r.get('stages', {})
                        p_stg = stg.get('pick', {})
                        pk_stg = stg.get('pack', {})
                        o_stg = stg.get('out', {})
                        ws.write(row_idx, 0, r.get('so_name') or '', fmt_cell)
                        ws.write(row_idx, 1, r.get('channel') or '', fmt_cell_center)
                        ws.write(row_idx, 2, (r.get('fulfillment') or 'FBM').upper(), fmt_cell_center)
                        ws.write(row_idx, 3, r.get('date_order') or '', fmt_cell_center)
                        ws.write(row_idx, 4, r.get('partner_name') or '', fmt_cell)
                        ws.write(row_idx, 5, r.get('order_progress') or '', fmt_cell_center)
                        ws.write(row_idx, 6, r.get('wmds_status_name') or '', fmt_cell_center)
                        ws.write(row_idx, 7, (r.get('summary_step') or '').upper(), fmt_cell_center)
                        ws.write(row_idx, 8, p_stg.get('name') or '', fmt_cell)
                        ws.write(row_idx, 9, p_stg.get('date_done') or '', fmt_cell_center)
                        ws.write(row_idx, 10, pk_stg.get('name') or '', fmt_cell)
                        ws.write(row_idx, 11, pk_stg.get('date_done') or '', fmt_cell_center)
                        ws.write(row_idx, 12, o_stg.get('name') or '', fmt_cell)
                        ws.write(row_idx, 13, o_stg.get('date_done') or '', fmt_cell_center)
                        ws.write(row_idx, 14, r.get('carrier_name') or '', fmt_cell)
                        ws.write(row_idx, 15, o_stg.get('carrier_tracking_ref') or '', fmt_cell)
                    col_widths = [18, 16, 12, 18, 24, 14, 18, 12, 16, 18, 16, 18, 16, 18, 18, 20]
                    for c_i, w in enumerate(col_widths):
                        ws.set_column(c_i, c_i, w)

                filename = f"WMDs_Operaciones_Almacen_{fields.Date.today()}.xlsx"

            wb.close()
            output_stream.seek(0)
            xlsx_base64 = base64.b64encode(output_stream.read()).decode('utf-8')

            return {
                'ok': True,
                'xlsx_file': xlsx_base64,
                'filename': filename,
                'message': f"Reporte Excel generado exitosamente ({filename})"
            }
        except Exception as e:
            _logger.error(f"Error generando reporte Excel WMDS: {e}", exc_info=True)
            return {'error': {'message': str(e)}}

