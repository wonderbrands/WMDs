# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
import logging

_logger = logging.getLogger(__name__)


class MysqlDriverController(http.Controller):

    def _check_developer_access(self):
        user = request.env.user
        if not (user.has_group('wmds.group_wmds_developer') or user.has_group('wmds.group_wmds_manager') or user.id == 1):
            return False
        return True

    @http.route(
        '/wmds/v2/engine/get/mysql_configs',
        type='json',
        auth='user',
        methods=['POST'],
        csrf=True
    )
    def get_mysql_configs(self, **kw):
        """ Return list of configured MySQL driver data sources. Ensure default Amazon entry exists. """
        if not self._check_developer_access():
            return {'error': {'message': 'Acceso denegado. Se requieren permisos de WMDs Developer.'}}

        try:
            config_model = request.env['wmds.mysql.config'].sudo()
            configs = config_model.search([])

            # Auto-create default Amazon RDS entry if table is empty
            if not configs:
                default_config = config_model.create({
                    'name': 'Amazon RDS SLA',
                    'active': True,
                    'marketplace': 'Amazon',
                    'host': 'wonderbrands1.cuwd36ifbz5t.us-east-1.rds.amazonaws.com',
                    'port': 3306,
                    'user': 'demian',
                    'password': 'z54u5ChHNpF8',
                    'database': 'somos_reyes',
                    'table_name': 'amazon_orders',
                    'order_id_field': 'AmazonOrderId',
                    'sla_date_field': 'LatestShipDate',
                })
                configs = [default_config]

            res = []
            for c in configs:
                res.append({
                    'id': c.id,
                    'name': c.name,
                    'active': c.active,
                    'marketplace': c.marketplace,
                    'host': c.host,
                    'port': c.port,
                    'user': c.user,
                    'password': c.password,
                    'database': c.database,
                    'table_name': c.table_name,
                    'order_id_field': c.order_id_field,
                    'sla_date_field': c.sla_date_field,
                    'last_sync_date': c.last_sync_date.strftime('%Y-%m-%d %H:%M:%S') if c.last_sync_date else False,
                    'last_sync_status': c.last_sync_status or ''
                })

            return {
                'success': True,
                'configs': res
            }
        except Exception as e:
            _logger.error(f"Error fetching MySQL configs: {e}", exc_info=True)
            return {'error': {'message': str(e)}}

    @http.route(
        '/wmds/v2/engine/save/mysql_config',
        type='json',
        auth='user',
        methods=['POST'],
        csrf=True
    )
    def save_mysql_config(self, **kw):
        """ Create or update MySQL driver configuration """
        if not self._check_developer_access():
            return {'error': {'message': 'Acceso denegado. Se requieren permisos de WMDs Developer.'}}

        try:
            data = kw.get('data') or {}
            c_id = data.get('id')
            vals = {
                'name': (data.get('name') or 'MySQL SLA Connection').strip(),
                'active': bool(data.get('active', True)),
                'marketplace': (data.get('marketplace') or 'Amazon').strip(),
                'host': (data.get('host') or '').strip(),
                'port': int(data.get('port') or 3306),
                'user': (data.get('user') or '').strip(),
                'password': (data.get('password') or '').strip(),
                'database': (data.get('database') or '').strip(),
                'table_name': (data.get('table_name') or '').strip(),
                'order_id_field': (data.get('order_id_field') or 'AmazonOrderId').strip(),
                'sla_date_field': (data.get('sla_date_field') or 'LatestShipDate').strip(),
            }

            if c_id:
                cfg = request.env['wmds.mysql.config'].sudo().browse(int(c_id))
                cfg.write(vals)
            else:
                cfg = request.env['wmds.mysql.config'].sudo().create(vals)
                c_id = cfg.id

            return {'success': True, 'id': c_id}
        except Exception as e:
            _logger.error(f"Error saving MySQL config: {e}", exc_info=True)
            return {'error': {'message': str(e)}}

    @http.route(
        '/wmds/v2/engine/test/mysql_connection',
        type='json',
        auth='user',
        methods=['POST'],
        csrf=True
    )
    def test_mysql_connection(self, **kw):
        """ Test connection to MySQL database """
        if not self._check_developer_access():
            return {'error': {'message': 'Acceso denegado. Se requieren permisos de WMDs Developer.'}}

        try:
            c_id = kw.get('id')
            if not c_id:
                return {'error': {'message': 'ID de configuración requerido.'}}

            cfg = request.env['wmds.mysql.config'].sudo().browse(int(c_id))
            res = cfg.action_test_connection()
            return res
        except Exception as e:
            _logger.error(f"Error testing MySQL connection: {e}", exc_info=True)
            return {'error': {'message': str(e)}}

    @http.route(
        '/wmds/v2/engine/sync/mysql_sla',
        type='json',
        auth='user',
        methods=['POST'],
        csrf=True
    )
    def sync_mysql_sla(self, **kw):
        """ Trigger manual SLA sync from external MySQL database """
        if not self._check_developer_access():
            return {'error': {'message': 'Acceso denegado. Se requieren permisos de WMDs Developer.'}}

        try:
            c_id = kw.get('id')
            if not c_id:
                return {'error': {'message': 'ID de configuración requerido.'}}

            cfg = request.env['wmds.mysql.config'].sudo().browse(int(c_id))
            res = cfg.action_sync_sla()
            return res
        except Exception as e:
            _logger.error(f"Error executing MySQL SLA sync: {e}", exc_info=True)
            return {'error': {'message': str(e)}}
