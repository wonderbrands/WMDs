# -*- coding: utf-8 -*-
from odoo import models, fields, api
from datetime import datetime
import logging
import re

_logger = logging.getLogger(__name__)

try:
    import pymysql
    import pymysql.cursors
    PYMYSQL_AVAILABLE = True
except ImportError:
    PYMYSQL_AVAILABLE = False


class WmdsMysqlConfig(models.Model):
    _name = 'wmds.mysql.config'
    _description = 'WMDs MySQL SLA Data Connection'

    name = fields.Char(string='Nombre de Conexión', required=True, default='Amazon RDS SLA')
    active = fields.Boolean(string='Activo', default=True)
    marketplace = fields.Char(string='Marketplace / Canal', required=True, default='Amazon')
    sla_timezone = fields.Selection([
        ('utc', 'UTC'),
        ('local', 'Hora Local'),
    ], string='Zona horaria del SLA', default='utc',
       help='Si el sla_date de este marketplace se guarda en UTC o en hora local (México). Determinante al filtrar por fecha.')
    
    host = fields.Char(string='Host MySQL', required=True, default='wonderbrands1.cuwd36ifbz5t.us-east-1.rds.amazonaws.com')
    port = fields.Integer(string='Puerto MySQL', default=3306, required=True)
    user = fields.Char(string='Usuario MySQL', required=True, default='demian')
    password = fields.Char(string='Contraseña MySQL', required=True, default='z54u5ChHNpF8')
    database = fields.Char(string='Base de Datos MySQL', required=True, default='somos_reyes')
    table_name = fields.Char(string='Tabla MySQL', required=True, default='amazon_orders')
    
    order_id_field = fields.Char(string='Campo ID Orden MySQL', default='AmazonOrderId', required=True)
    sla_date_field = fields.Char(string='Campo Fecha SLA MySQL', default='LatestShipDate', required=True)
    
    last_sync_date = fields.Datetime(string='Última Sincronización', readonly=True)
    last_sync_status = fields.Text(string='Estado de Última Sincronización', readonly=True)

    def action_test_connection(self):
        self.ensure_one()
        if not PYMYSQL_AVAILABLE:
            return {'success': False, 'message': 'El paquete Python pymysql no está instalado en el servidor.'}
        
        try:
            conn = pymysql.connect(
                host=self.host,
                port=self.port or 3306,
                user=self.user,
                password=self.password,
                database=self.database,
                connect_timeout=10
            )
            cursor = conn.cursor()
            cursor.execute(f"SELECT COUNT(*) FROM {self.table_name};")
            count = cursor.fetchone()[0]
            conn.close()
            
            msg = f"Conexión exitosa. Tabla '{self.table_name}' contiene {count} registros."
            self.write({
                'last_sync_status': f"Test exitoso ({fields.Datetime.now()}): {msg}"
            })
            return {'success': True, 'message': msg, 'count': count}
        except Exception as e:
            err_msg = f"Error al conectar con MySQL ({self.host}): {str(e)}"
            _logger.error(err_msg, exc_info=True)
            self.write({
                'last_sync_status': f"Error de test ({fields.Datetime.now()}): {err_msg}"
            })
            return {'success': False, 'message': err_msg}

    def action_sync_sla(self, limit=20000):
        self.ensure_one()
        if not PYMYSQL_AVAILABLE:
            return {'success': False, 'message': 'El paquete Python pymysql no está instalado.'}

        try:
            conn = pymysql.connect(
                host=self.host,
                port=self.port or 3306,
                user=self.user,
                password=self.password,
                database=self.database,
                connect_timeout=15,
                cursorclass=pymysql.cursors.DictCursor
            )
            cursor = conn.cursor()
            
            order_col = f"`{self.order_id_field.strip('`')}`"
            sla_col = f"`{self.sla_date_field.strip('`')}`"
            table_col = f"`{self.table_name.strip('`')}`"

            is_walmart = (self.table_name == 'wm_orders')
            if is_walmart:
                # Walmart: promiseDeliveryDate column is often 0000-00-00, but present in orderLines or shipments JSON
                sql_default = f"""
                    SELECT purchaseOrderId, customerOrderId, promiseDeliveryDate, shipments, orderLines
                    FROM {table_col}
                    WHERE updated_at IS NOT NULL
                    ORDER BY updated_at DESC
                    LIMIT %s;
                """
                cursor.execute(sql_default, (limit,))
                rows = list(cursor.fetchall())
            else:
                sql_default = f"""
                    SELECT {order_col} AS order_ref, {sla_col} AS sla_dt
                    FROM {table_col}
                    WHERE {sla_col} IS NOT NULL AND {order_col} IS NOT NULL
                      AND {sla_col} != '0000-00-00 00:00:00'
                    ORDER BY updated_at DESC
                    LIMIT %s;
                """
                cursor.execute(sql_default, (limit,))
                rows = list(cursor.fetchall())
            
            # 2. Insist on active sale orders missing SLA (filtradas por canal y excluyendo Full según marketplace.schedule)
            so_model = self.env['sale.order'].sudo()
            exclude_full = True
            if hasattr(so_model, '_should_exclude_full_for_channel'):
                exclude_full = so_model._should_exclude_full_for_channel(self.marketplace)

            missing_domain = [
                ('state', '!=', 'cancel'),
                ('sla_date', '=', False),
            ]
            if self.marketplace and self.marketplace.strip():
                missing_domain.append(('channel', 'ilike', self.marketplace.strip()))
            if exclude_full and hasattr(so_model, '_get_non_full_domain'):
                missing_domain += so_model._get_non_full_domain()

            missing_sla_orders = so_model.search(missing_domain, order='date_order desc, id desc', limit=5000)
            
            missing_refs = set()
            for so in missing_sla_orders:
                if getattr(so, 'marketplace_ref', None): missing_refs.add(str(so.marketplace_ref).strip())
                if getattr(so, 'channel_order_reference', None): missing_refs.add(str(so.channel_order_reference).strip())
                if so.channel_order_id: missing_refs.add(str(so.channel_order_id).strip())
                if so.client_order_ref: missing_refs.add(str(so.client_order_ref).strip())
                if so.name: missing_refs.add(str(so.name).strip())
                
            missing_refs = [r for r in missing_refs if r]
            
            if missing_refs:
                chunk_size = 1000
                for i in range(0, len(missing_refs), chunk_size):
                    chunk = missing_refs[i:i + chunk_size]
                    format_strings = ','.join(['%s'] * len(chunk))
                    if is_walmart:
                        sql_missing = f"""
                            SELECT purchaseOrderId, customerOrderId, promiseDeliveryDate, shipments, orderLines
                            FROM {table_col}
                            WHERE (purchaseOrderId IN ({format_strings}) OR customerOrderId IN ({format_strings}))
                        """
                        cursor.execute(sql_missing, tuple(chunk) + tuple(chunk))
                    else:
                        sql_missing = f"""
                            SELECT {order_col} AS order_ref, {sla_col} AS sla_dt
                            FROM {table_col}
                            WHERE {sla_col} IS NOT NULL 
                              AND {sla_col} != '0000-00-00 00:00:00'
                              AND {order_col} IN ({format_strings})
                        """
                        cursor.execute(sql_missing, tuple(chunk))
                    rows.extend(cursor.fetchall())

            conn.close()

            if not rows:
                msg = "Conexión realizada, pero no se encontraron registros con fecha SLA válida."
                self.write({'last_sync_date': fields.Datetime.now(), 'last_sync_status': msg})
                return {'success': True, 'message': msg, 'updated_count': 0}

            # Map order_ref to datetime
            ref_sla_map = {}
            for r in rows:
                if is_walmart:
                    dt_val = None
                    raw_pdd = r.get('promiseDeliveryDate')
                    if raw_pdd and str(raw_pdd) != '0000-00-00 00:00:00':
                        dt_val = raw_pdd
                    else:
                        txt = (r.get('orderLines') or '') + (r.get('shipments') or '')
                        m = re.search(r'promiseDeliveryDate[\'"]?\s*:\s*[\'"]?([^\'",]+)', txt)
                        if not m:
                            m = re.search(r'expectedShipmentShippedDate[\'"]?\s*:\s*[\'"]?([^\'",]+)', txt)
                        if m:
                            dt_val = m.group(1).strip()
                    if dt_val:
                        dt_parsed = None
                        if isinstance(dt_val, datetime):
                            dt_parsed = dt_val
                        else:
                            try:
                                dt_str_clean = str(dt_val).replace('T', ' ').replace('Z', '').split('.')[0]
                                dt_parsed = fields.Datetime.to_datetime(dt_str_clean)
                            except Exception:
                                pass
                        if dt_parsed:
                            p_id = str(r.get('purchaseOrderId') or '').strip()
                            c_id = str(r.get('customerOrderId') or '').strip()
                            if p_id: ref_sla_map[p_id] = dt_parsed
                            if c_id: ref_sla_map[c_id] = dt_parsed
                else:
                    ref = str(r.get('order_ref') or '').strip()
                    dt_val = r.get('sla_dt')
                    if ref and dt_val:
                        if isinstance(dt_val, datetime):
                            ref_sla_map[ref] = dt_val
                        else:
                            try:
                                # Handle epoch milliseconds (Walmart) or seconds
                                if isinstance(dt_val, (int, float)) or (isinstance(dt_val, str) and dt_val.isdigit()):
                                    val_int = float(dt_val)
                                    if val_int > 1e11: # likely milliseconds
                                        val_int = val_int / 1000.0
                                    ref_sla_map[ref] = datetime.fromtimestamp(val_int)
                                else:
                                    dt_str_clean = str(dt_val).replace('T', ' ').replace('Z', '').split('.')[0]
                                    ref_sla_map[ref] = fields.Datetime.to_datetime(dt_str_clean)
                            except Exception:
                                pass

            if not ref_sla_map:
                msg = "No se pudieron procesar las fechas de las órdenes consultadas."
                self.write({'last_sync_date': fields.Datetime.now(), 'last_sync_status': msg})
                return {'success': True, 'message': msg, 'updated_count': 0}

            # Search sale_orders matching marketplace_ref, channel_order_reference, channel_order_id, client_order_ref, or name
            order_refs = list(ref_sla_map.keys())
            
            so_model = self.env['sale.order'].sudo()
            domain = [
                '|', '|', '|',
                ('channel_order_reference', 'in', order_refs),
                ('channel_order_id', 'in', order_refs),
                ('client_order_ref', 'in', order_refs),
                ('name', 'in', order_refs)
            ]
            if 'marketplace_ref' in so_model._fields:
                domain = ['|'] + domain + [('marketplace_ref', 'in', order_refs)]

            if 'order_progress' in so_model._fields:
                domain += ['|', ('order_progress', '!=', 'sent'), ('order_progress', '=', False)]

            if exclude_full and hasattr(so_model, '_get_non_full_domain'):
                domain += so_model._get_non_full_domain()

            sale_orders = so_model.search(domain)

            updated_orders_count = 0

            for so in sale_orders:
                if exclude_full and hasattr(so, '_is_full_order') and so._is_full_order():
                    continue

                target_dt = (
                    ref_sla_map.get(getattr(so, 'marketplace_ref', None)) or
                    ref_sla_map.get(getattr(so, 'channel_order_reference', None)) or
                    ref_sla_map.get(so.channel_order_id) or
                    ref_sla_map.get(so.client_order_ref) or
                    ref_sla_map.get(so.name)
                )

                if target_dt:
                    dt_str = fields.Datetime.to_string(target_dt)

                    # IDEMPOTENCIA: Si ya tiene ajuste manual/empuje, NO sobreescribir sla_date
                    if getattr(so, 'sla_manual_override', False):
                        if not getattr(so, 'sla_original_date', False):
                            so.write({'sla_original_date': dt_str})
                        continue

                    vals = {'sla_date': dt_str}
                    if not getattr(so, 'sla_original_date', False):
                        vals['sla_original_date'] = dt_str
                    so.write(vals)
                    updated_orders_count += 1

            # 3. Para órdenes Drop/No-Full del canal que sigan sin SLA tras sincronizar, calcular SLA según marketplace.schedule
            still_missing_drop = missing_sla_orders.filtered(lambda o: not o.sla_date)
            if still_missing_drop and hasattr(still_missing_drop, 'calculate_and_assign_sla'):
                for drop_so in still_missing_drop:
                    try:
                        drop_so.calculate_and_assign_sla()
                        if drop_so.sla_date:
                            updated_orders_count += 1
                    except Exception as ex:
                        _logger.warning(f"Error calculando SLA post-sync para {drop_so.name}: {ex}")

            # Trigger priority recalculation for active sale orders if SLA module method exists
            active_orders = self.env['sale.order'].sudo().search([
                ('state', '!=', 'cancel'),
                ('sla_date', '!=', False)
            ])
            if active_orders and hasattr(active_orders, '_compute_sla_priority'):
                try:
                    active_orders._compute_sla_priority()
                except Exception as ex:
                    _logger.warning(f"Note on SLA compute priority: {ex}")

            success_msg = f"Sincronización completada exitosamente. Se consultaron {len(rows)} órdenes de MySQL; se actualizaron {updated_orders_count} pedidos de venta."
            _logger.info(f"WMDs MySQL Sync: {success_msg}")
            
            self.write({
                'last_sync_date': fields.Datetime.now(),
                'last_sync_status': success_msg
            })

            return {
                'success': True,
                'message': success_msg,
                'scanned_rows': len(rows),
                'updated_orders': updated_orders_count,
                'updated_pickings': 0
            }

        except Exception as e:
            err_msg = f"Error en sincronización MySQL: {str(e)}"
            _logger.error(err_msg, exc_info=True)
            self.write({
                'last_sync_date': fields.Datetime.now(),
                'last_sync_status': err_msg
            })
            return {'success': False, 'message': err_msg}

    @api.model
    def _cron_sync_mysql_sla(self):
        """ Executed every 2 hours via cron job """
        configs = self.search([('active', '=', True)])
        _logger.info(f"Cron WMDs MySQL SLA Sync: Iniciando para {len(configs)} configuraciones.")
        for config in configs:
            try:
                config.action_sync_sla()
            except Exception as e:
                _logger.error(f"Error procesando cron para MySQL config {config.name}: {e}")
