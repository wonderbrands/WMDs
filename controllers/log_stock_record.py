from odoo import http
from odoo.http import request
import traceback
import logging
from datetime import datetime

logger = logging.getLogger(__name__)



class LogStockRecord(http.Controller):

    @http.route(
        '/wmds/v2/engine/post/log_stock_record',
        type='json',
        auth='user',
        methods=['POST'],
        csrf=True
    )
    def log_stock_record(self, **kw):
        pick_id = kw.get('pick_id')
        pick_name = kw.get('pick_name')
        operator_mail = kw.get('operator_mail')
        message = kw.get('message')

        operator_id = request.env['res.users'].sudo().search([('login', '=', operator_mail)], limit=1)

        try:
            if pick_id:
                picking = request.env['stock.picking'].sudo().search([('id', '=', pick_id)], limit=1)
            if pick_name:
                picking = request.env['stock.picking'].sudo().search([('name', '=', pick_name)], limit=1)
            picking.wmds_log.create({
                'log': message,
                'user': operator_id,
                'date': datetime.now()
            })
            return {
                "saved": True
            }
        except Exception as e:
            return {
                "error": f"{str(e)}\n{traceback.format_exc()}"
            }

    @http.route(
        '/wmds/v2/engine/post/change_wmds_status',
        type='json',
        auth='user',
        methods=['POST'],
        csrf=True
    )
    def change_wmds_status(self, **kw):
        pick_id = kw.get('pick_id')
        pick_name = kw.get('pick_name')
        status = kw.get('status')

        try:
            if pick_id:
                picking = request.env['stock.picking'].sudo().search([('id', '=', pick_id)], limit=1)
            if pick_name:
                picking = request.env['stock.picking'].sudo().search([('name', '=', pick_name)], limit=1)
            picking.wmds_status = request.env['wmds.stock.status'].search([('value', '=', status)], limit=1)
            return {
                "saved": True
            }
        except Exception as e:
            return {
                "error": f"{str(e)}\n{traceback.format_exc()}"
            }
    
