# -*- coding: utf-8 -*-
from odoo import http, fields
from odoo.http import request
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)


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
            limit = int(kw.get('limit') or 50)
            page = int(kw.get('page') or 1)
            offset = int(kw.get('offset') or ((page - 1) * limit if page > 1 else 0))

            env = request.env
            client_tz = kw.get('tz')
            if client_tz:
                env = env(context=dict(env.context, tz=client_tz))

            picking_model = env['stock.picking']

            now_utc = fields.Datetime.now()
            in_1h_utc = now_utc + timedelta(hours=1)
            in_2h_utc = now_utc + timedelta(hours=2)
            in_6h_utc = now_utc + timedelta(hours=6)
            in_24h_utc = now_utc + timedelta(hours=24)

            # Obtener canales dinámicos únicos existentes en sale_order (Rápido en SQL)
            env.cr.execute("SELECT DISTINCT channel FROM sale_order WHERE channel IS NOT NULL AND channel != '' ORDER BY channel")
            raw_channels = [r[0] for r in env.cr.fetchall() if r[0]]
            available_channels = sorted(list(set(c.strip() for c in raw_channels if c and c.strip())))

            # Base domain: Solo órdenes activas pendientes (no sent, no shipped, no refunded, no canceladas)
            domain = [
                ('sale_id', '!=', False),
                ('sale_id.state', '!=', 'cancel'),
                ('sale_id.order_progress', '!=', 'sent'),
                ('sale_id.order_progress', 'not ilike', 'shipped'),
                ('sale_id.order_progress', 'not ilike', 'refunded'),
                ('sale_id.order_progress', 'not ilike', 'cancel'),
                ('sale_id.yuju_shipping_status', '!=', 'sent'),
                ('state', 'not in', ('done', 'cancel'))
            ]

            # 1. Status Filter (Precisión basada en tiempo real de SLA)
            if status_filter == 'overdue':
                domain.extend([
                    ('sla_date', '!=', False),
                    ('sla_date', '<', now_utc)
                ])
            elif status_filter == 'critical_1h':
                domain.extend([
                    ('sla_date', '!=', False),
                    ('sla_date', '>=', now_utc),
                    ('sla_date', '<=', in_1h_utc)
                ])
            elif status_filter == 'urgent_2h':
                domain.extend([
                    ('sla_date', '!=', False),
                    ('sla_date', '>', in_1h_utc),
                    ('sla_date', '<=', in_2h_utc)
                ])
            elif status_filter == 'warning_6h':
                domain.extend([
                    ('sla_date', '!=', False),
                    ('sla_date', '>', in_2h_utc),
                    ('sla_date', '<=', in_6h_utc)
                ])
            elif status_filter == 'notice_24h':
                domain.extend([
                    ('sla_date', '!=', False),
                    ('sla_date', '>', in_6h_utc),
                    ('sla_date', '<=', in_24h_utc)
                ])
            elif status_filter == 'normal':
                domain.extend([
                    ('sla_date', '!=', False),
                    ('sla_date', '>', in_24h_utc)
                ])
            elif status_filter == 'no_sla':
                domain.append(('sla_date', '=', False))

            # 2. Text Search Query
            if query:
                sub_domain = [
                    '|', '|', '|', '|',
                    ('name', 'ilike', query),
                    ('origin', 'ilike', query),
                    ('partner_id.name', 'ilike', query),
                    ('carrier_tracking_ref', 'ilike', query),
                    ('sale_id.channel_order_id', 'ilike', query)
                ]
                domain.extend(sub_domain)

            # 3. Channel Filter
            if channel_filter and channel_filter != 'all':
                domain.append(('sale_id.channel', 'ilike', channel_filter))

            total_count = picking_model.sudo().search_count(domain)
            pickings = picking_model.sudo().search(domain, order='id desc', limit=limit, offset=offset)

            # Optimización masiva BATCH para logs de WMDS (1 sola consulta SQL para los 50 resultados)
            pick_ids = tuple(p.id for p in pickings if p.id)
            so_ids = tuple(p.sale_id.id for p in pickings if p.sale_id)

            wmds_logs = {}
            if pick_ids or so_ids:
                where_parts = []
                params = []
                if pick_ids:
                    where_parts.append("pick IN %s")
                    params.append(pick_ids)
                if so_ids:
                    where_parts.append("sale IN %s")
                    params.append(so_ids)
                
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
            for pick in pickings:
                so = pick.sale_id
                so_name = so.name if so else (pick.origin.split(',')[0].strip() if pick.origin else '')
                channel = so.channel if so else ''
                fulfillment = so.fulfillment if so else ''
                yuju_due_date = getattr(so, 'yuju_due_date', False) if so else False

                # Determinar fecha SLA efectiva (de pick.sla_date o sale.order.yuju_due_date)
                effective_sla_date = pick.sla_date
                if not effective_sla_date and so and yuju_due_date:
                    try:
                        clean_date_str = str(yuju_due_date).strip().replace('Z', '')
                        if 'T' in clean_date_str:
                            effective_sla_date = datetime.fromisoformat(clean_date_str)
                        else:
                            effective_sla_date = datetime.strptime(clean_date_str, "%Y-%m-%d %H:%M:%S")
                    except Exception:
                        pass

                # Cómputo exacto en tiempo real para evitar valores estancados en BD
                if effective_sla_date:
                    sla_dt_str = fields.Datetime.to_string(effective_sla_date)
                    if effective_sla_date < now_utc:
                        sla_level = 'overdue'
                        sla_label = 'SLA Vencido'
                    elif effective_sla_date <= in_1h_utc:
                        sla_level = 'critical_1h'
                        sla_label = 'Está a punto de llegar la recolecta (< 1h)'
                    else:
                        diff_hours = (effective_sla_date - now_utc).total_seconds() / 3600.0
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

                # Buscar log en dict precargado en memoria
                log_info = wmds_logs.get(('pick', pick.id))
                if not log_info and so:
                    log_info = wmds_logs.get(('sale', so.id))

                latest_log = log_info[0] if log_info else ''
                latest_log_date = log_info[1] if log_info else ''
                latest_log_user = users_map.get(log_info[2], '') if log_info and log_info[2] else ''

                # Paquetería / Carrier y Guía
                carrier_name = ''
                if pick.carrier_id:
                    carrier_name = pick.carrier_id.name
                elif so:
                    if getattr(so, 'data_carrier_selection_relational', False):
                        carrier_name = so.data_carrier_selection_relational.name
                    elif getattr(so, 'carrier_id', False):
                        carrier_name = so.carrier_id.name
                    elif getattr(so, 'yuju_carrier', False):
                        carrier_name = so.yuju_carrier

                tracking_ref = pick.carrier_tracking_ref or (getattr(so, 'yuju_carrier_tracking_ref', '') if so else '') or ''

                results.append({
                    'id': pick.id,
                    'name': pick.name,
                    'sale_order_name': so_name,
                    'partner_name': pick.partner_id.display_name if pick.partner_id else '',
                    'channel': channel,
                    'fulfillment': fulfillment,
                    'carrier': carrier_name,
                    'carrier_tracking_ref': tracking_ref,
                    'state': pick.state,
                    'scheduled_date': fields.Datetime.to_string(pick.scheduled_date) if pick.scheduled_date else False,
                    'sla_date': sla_dt_str,
                    'sla_priority_level': sla_level,
                    'sla_priority_label': sla_label,
                    'yuju_due_date': str(yuju_due_date) if yuju_due_date else False,
                    'latest_wmds_log': latest_log,
                    'latest_wmds_log_user': latest_log_user,
                    'latest_wmds_log_date': latest_log_date,
                })

            return {
                'success': True,
                'count': len(results),
                'total_count': total_count,
                'page': page,
                'limit': limit,
                'available_channels': available_channels,
                'results': results
            }

        except Exception as e:
            _logger.error(f"Error querying order channel: {e}", exc_info=True)
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
