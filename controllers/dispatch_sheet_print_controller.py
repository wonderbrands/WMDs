from odoo import http
from odoo.http import request
import logging

_logger = logging.getLogger(__name__)

class DispatchSheetPrintController(http.Controller):

    @http.route('/wmds/v2/engine/post/print_dispatch_sheet', type='json', auth='user', methods=['POST'], csrf=True)
    def print_dispatch_sheet(self, **kw):
        try:
            session_id = kw.get("session_id")
            if not session_id:
                return {"ok": False, "error": "session_id requerido"}

            session = request.env["wmds.dispatch.session"].sudo().browse(int(session_id))
            if not session.exists():
                return {"ok": False, "error": "Sesión no encontrada"}

            # Guardar PDF
            sheet = request.env["wmds.dispatch.sheet"].sudo().create_from_session(session)

            # Impresion IoT
            report = request.env.ref('wmds.action_report_dispatch_sheet')
            action = report.sudo().report_action(session.id)

            return {
                "ok": True,
                "action": action,
                "sheet_id": sheet.id,  # opcional, por si Vue lo necesita
            }

        except Exception as e:
            _logger.error(f"Error en print_dispatch_sheet: {e}")
            return {"ok": False, "error": str(e)}