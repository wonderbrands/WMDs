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

            domain = [('sale_id', '!=', False)]

            # 1. Status Filter (Precisión basada en tiempo real de SLA)
            if status_filter == 'overdue':
                domain.extend([
                    ('state', 'not in', ('done', 'cancel')),
                    ('sla_date', '!=', False),
                    ('sla_date', '<', now_utc)
                ])
            elif status_filter == 'critical_1h':
                domain.extend([
                    ('state', 'not in', ('done', 'cancel')),
                    ('sla_date', '!=', False),
                    ('sla_date', '>=', now_utc),
                    ('sla_date', '<=', in_1h_utc)
                ])
            elif status_filter == 'urgent_2h':
                domain.extend([
                    ('state', 'not in', ('done', 'cancel')),
                    ('sla_date', '!=', False),
                    ('sla_date', '>', in_1h_utc),
                    ('sla_date', '<=', in_2h_utc)
                ])
            elif status_filter == 'warning_6h':
                domain.extend([
                    ('state', 'not in', ('done', 'cancel')),
                    ('sla_date', '!=', False),
                    ('sla_date', '>', in_2h_utc),
                    ('sla_date', '<=', in_6h_utc)
                ])
            elif status_filter == 'notice_24h':
                domain.extend([
                    ('state', 'not in', ('done', 'cancel')),
                    ('sla_date', '!=', False),
                    ('sla_date', '>', in_6h_utc),
                    ('sla_date', '<=', in_24h_utc)
                ])
            elif status_filter == 'normal':
                domain.extend([
                    ('state', 'not in', ('done', 'cancel')),
                    ('sla_date', '!=', False),
                    ('sla_date', '>', in_24h_utc)
                ])

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

            pickings = picking_model.sudo().search(domain, order='id desc', limit=limit)

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
                        from extra_addons.wonderbrands2026.wb_SLA_module.SLA_module.models.stock_picking import parse_yuju_date
                        effective_sla_date = parse_yuju_date(yuju_due_date)
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

                results.append({
                    'id': pick.id,
                    'name': pick.name,
                    'sale_order_name': so_name,
                    'partner_name': pick.partner_id.display_name if pick.partner_id else '',
                    'channel': channel,
                    'fulfillment': fulfillment,
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
        Return count of active pickings expiring in < 1h vs overdue.
        """
        try:
            env = request.env
            picking_model = env['stock.picking']

            now_utc = fields.Datetime.now()
            in_1h_utc = now_utc + timedelta(hours=1)

            # 1. Críticos: vencen en los próximos 60 minutos (now <= sla_date <= in_1h)
            critical_count = picking_model.sudo().search_count([
                ('state', 'not in', ('done', 'cancel')),
                ('sale_id', '!=', False),
                ('sla_date', '!=', False),
                ('sla_date', '>=', now_utc),
                ('sla_date', '<=', in_1h_utc)
            ])

            # 2. Vencidos: la fecha límite ya transcurrió (sla_date < now)
            overdue_count = picking_model.sudo().search_count([
                ('state', 'not in', ('done', 'cancel')),
                ('sale_id', '!=', False),
                ('sla_date', '!=', False),
                ('sla_date', '<', now_utc)
            ])

            return {
                'success': True,
                'critical_count': critical_count,
                'overdue_count': overdue_count,
                'total_alerts': critical_count + overdue_count
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
                    'collection_cutoff_time': s.collection_cutoff_time,
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
                'collection_cutoff_time': float(data.get('collection_cutoff_time') or 17.0),
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
