# -*- coding: utf-8 -*-
from odoo import models, fields, api
from datetime import datetime
import logging

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

    def action_sync_sla(self, limit=2000):
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
            
            sql = f"""
                SELECT {self.order_id_field} AS order_ref, {self.sla_date_field} AS sla_dt
                FROM {self.table_name}
                WHERE {self.sla_date_field} IS NOT NULL AND {self.order_id_field} IS NOT NULL
                ORDER BY updated_at DESC
                LIMIT %s;
            """
            cursor.execute(sql, (limit,))
            rows = cursor.fetchall()
            conn.close()

            if not rows:
                msg = "Conexión realizada, pero no se encontraron registros con fecha SLA válida."
                self.write({'last_sync_date': fields.Datetime.now(), 'last_sync_status': msg})
                return {'success': True, 'message': msg, 'updated_count': 0}

            # Map order_ref to datetime
            ref_sla_map = {}
            for r in rows:
                ref = str(r.get('order_ref') or '').strip()
                dt_val = r.get('sla_dt')
                if ref and dt_val:
                    if isinstance(dt_val, datetime):
                        ref_sla_map[ref] = dt_val
                    else:
                        try:
                            ref_sla_map[ref] = fields.Datetime.to_datetime(str(dt_val))
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

            sale_orders = so_model.search(domain)

            updated_pickings_count = 0
            updated_orders_count = 0

            for so in sale_orders:
                target_dt = (
                    ref_sla_map.get(getattr(so, 'marketplace_ref', None)) or
                    ref_sla_map.get(getattr(so, 'channel_order_reference', None)) or
                    ref_sla_map.get(so.channel_order_id) or
                    ref_sla_map.get(so.client_order_ref) or
                    ref_sla_map.get(so.name)
                )

                if target_dt:
                    dt_str = fields.Datetime.to_string(target_dt)
                    pickings = self.env['stock.picking'].sudo().search([
                        ('sale_id', '=', so.id),
                        ('state', 'not in', ('done', 'cancel'))
                    ])

                    if pickings:
                        for pick in pickings:
                            pick.write({
                                'sla_date': dt_str,
                                'priority_date': dt_str
                            })
                            updated_pickings_count += 1
                        updated_orders_count += 1

            # Trigger priority recalculation for active pickings if SLA module method exists
            active_pickings = self.env['stock.picking'].sudo().search([
                ('state', 'not in', ('done', 'cancel')),
                ('sla_date', '!=', False)
            ])
            if active_pickings and hasattr(active_pickings, '_compute_sla_priority'):
                try:
                    active_pickings._compute_sla_priority()
                except Exception as ex:
                    _logger.warning(f"Note on SLA compute priority: {ex}")

            success_msg = f"Sincronización completada exitosamente. Se consultaron {len(rows)} órdenes de MySQL; se actualizaron {updated_orders_count} pedidos y {updated_pickings_count} transferencias."
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
                'updated_pickings': updated_pickings_count
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
