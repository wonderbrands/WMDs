from odoo import http, fields
from odoo.http import request
import logging

_logger = logging.getLogger(__name__)


class DispatchSessionController(http.Controller):

    # ─────────────────────────────────────────────
    # VALIDATE EI CARRIER — shared by BIN and DISPATCH
    # ─────────────────────────────────────────────
    @http.route('/wmds/v2/engine/post/validate_ei_carrier', type='json', auth='user', methods=['POST'], csrf=True)
    def validate_ei_carrier(self, **kw):
        """
        Valida si la EI (vía so_name) pertenece al carrier indicado.
        Usado por BinComponent y DispatchComponent antes de aceptar un escaneo.
        """
        try:
            so_name = kw.get("so_name")
            carrier_id = kw.get("carrier_id")

            if not so_name or not carrier_id:
                return {"valid": True}

            so = request.env['sale.order'].sudo().search([('name', '=', so_name)], limit=1)
            if not so:
                return {"valid": True}

            so_carrier = so.data_carrier_selection_relational
            if not so_carrier:
                return {"valid": True}

            session_carrier = request.env["carriers.list"].sudo().browse(int(carrier_id))
            if so_carrier.id != session_carrier.id:
                return {
                    "valid": False,
                    "so_carrier": so_carrier.name,
                    "session_carrier": session_carrier.name,
                    "message": f"Carrier no coincide. Seleccionado: {session_carrier.name} — Orden {so_name}: {so_carrier.name}.",
                }

            return {"valid": True}

        except Exception as e:
            _logger.error(f"Error en validate_ei_carrier: {e}")
            return {"valid": True}

    # ─────────────────────────────────────────────
    # GET / RECOVER active session for an operator
    # ─────────────────────────────────────────────
    @http.route('/wmds/v2/engine/post/get_dispatch_session', type='json', auth='user', methods=['POST'], csrf=True)
    def get_dispatch_session(self, **kw):
        """
        Busca una sesión activa para el operador.
        Si existe, devuelve la sesión con todas sus líneas para restaurar el estado.
        """
        try:
            operator_login = kw.get("operator_login")
            if not operator_login:
                return {"active": False}

            operator = request.env["res.users"].sudo().search([('login', '=', operator_login)], limit=1)
            if not operator:
                return {"active": False}

            session = request.env["wmds.dispatch.session"].sudo().search([
                ('operator_id', '=', operator.id),
                ('state', '=', 'active')
            ], limit=1, order='date_start desc')

            if not session:
                return {"active": False}

            lines = []
            for line in session.line_ids:
                # Find the current state of the SO linked to this line
                so_state = 'draft'
                ei_tag = request.env["sale.order.ei"].sudo().search([('display_name_custom', '=', line.ei_name)], limit=1)
                if ei_tag:
                    so_state = ei_tag.so_id.state

                lines.append({
                    "line_id": line.id,
                    "ei_name": line.ei_name,
                    "so_name": line.so_name,
                    "so_state": so_state,
                    "product_name": line.product_name or "",
                    "carrier_name": line.carrier_name or "",
                    "scan_datetime": fields.Datetime.to_string(line.scan_datetime) if line.scan_datetime else "",
                    "total_ei": line.total_ei,
                    "sequence_number": line.sequence_number,
                    "dispatched_count": line.dispatched_count,
                })

            return {
                "active": True,
                "session_id": session.id,
                "date_start": fields.Datetime.to_string(session.date_start),
                "operator_name": session.operator_name,
                "carrier_id": session.carrier_id.id if session.carrier_id else None,
                "carrier_name": session.carrier_id.name if session.carrier_id else None,
                "lines": lines
            }

        except Exception as e:
            _logger.error(f"Error en get_dispatch_session: {e}")
            return {"active": False, "error": str(e)}

    # ─────────────────────────────────────────────
    # SAVE a scanned EI line to the session
    # ─────────────────────────────────────────────
    @http.route('/wmds/v2/engine/post/save_dispatch_session_line', type='json', auth='user', methods=['POST'], csrf=True)
    def save_dispatch_session_line(self, **kw):
        """
        Agrega una línea de escaneo a la sesión activa del operador.
        Si no hay sesión activa, crea una nueva.
        Obtiene producto y carrier de la SO automáticamente.
        """
        try:
            operator_login = kw.get("operator_login")
            carrier_id = kw.get("carrier_id")
            ei_name = kw.get("ei_name")
            so_name = kw.get("so_name")
            total = kw.get("total", 0)
            current = kw.get("current", 0)
            dispatched_count = kw.get("dispatched_count", 0)

            if not operator_login or not ei_name:
                return {"ok": False, "error": "Datos incompletos"}

            operator = request.env["res.users"].sudo().search([('login', '=', operator_login)], limit=1)
            if not operator:
                return {"ok": False, "error": "Operador no encontrado"}

            # Buscar o crear sesión activa
            session = request.env["wmds.dispatch.session"].sudo().search([
                ('operator_id', '=', operator.id),
                ('state', '=', 'active')
            ], limit=1, order='date_start desc')

            if not session:
                if not carrier_id:
                    return {"ok": False, "error": "Debe seleccionar un carrier antes de escanear"}
                session = request.env["wmds.dispatch.session"].sudo().create({
                    'operator_id': operator.id,
                    'state': 'active',
                    'carrier_id': int(carrier_id),
                })
                _logger.info(f"Nueva sesión de despacho creada: {session.id} para {operator_login}")

            # Verificar que no esté duplicado en la sesión
            existing = request.env["wmds.dispatch.session.line"].sudo().search([
                ('session_id', '=', session.id),
                ('ei_name', '=', ei_name)
            ], limit=1)

            if existing:
                return {"ok": True, "session_id": session.id, "duplicate": True}

            # Obtener producto y carrier de la SO
            product_name = ""
            carrier_name = ""

            so = request.env['sale.order'].sudo().search([('name', '=', so_name)], limit=1)

            # Validar carrier — IMPORTANTE: NO usar key "error" para evitar toast genérico de callOdoo
            if so and session.carrier_id:
                so_carrier = so.data_carrier_selection_relational
                if so_carrier and so_carrier.id != session.carrier_id.id:
                    return {
                        "ok": False,
                        "carrier_mismatch": True,
                        "mismatch_message": f"Carrier no coincide. Sesión: {session.carrier_id.name} — Orden: {so_carrier.name}.",
                    }

            if so:
                # Carrier
                if so.data_carrier_selection_relational:
                    carrier_name = so.data_carrier_selection_relational.name
                elif hasattr(so, 'x_carrier') and so.x_carrier:
                    carrier_name = so.x_carrier
                
                # Productos: unir los nombres de las líneas de la orden
                product_names = []
                for line in so.order_line:
                    if line.product_id and not line.is_downpayment:
                        product_names.append(line.product_id.display_name)
                product_name = ", ".join(product_names) if product_names else "Sin producto"

            # Crear la línea
            line = request.env["wmds.dispatch.session.line"].sudo().create({
                'session_id': session.id,
                'ei_name': ei_name,
                'so_name': so_name,
                'product_name': product_name,
                'carrier_name': carrier_name,
                'sequence_number': current,
                'total_ei': total,
                'dispatched_count': dispatched_count,
                'scan_datetime': fields.Datetime.now(),
            })

            return {
                "ok": True,
                "session_id": session.id,
                "line_id": line.id,
                "product_name": product_name,
                "carrier_name": carrier_name,
            }

        except Exception as e:
            _logger.error(f"Error en save_dispatch_session_line: {e}")
            return {"ok": False, "error": str(e)}

    # ─────────────────────────────────────────────
    # REMOVE a line from the session
    # ─────────────────────────────────────────────
    @http.route('/wmds/v2/engine/post/remove_dispatch_session_line', type='json', auth='user', methods=['POST'], csrf=True)
    def remove_dispatch_session_line(self, **kw):
        """Elimina una línea de escaneo de la sesión activa."""
        try:
            operator_login = kw.get("operator_login")
            ei_name = kw.get("ei_name")

            if not operator_login or not ei_name:
                return {"ok": False, "error": "Datos incompletos"}

            operator = request.env["res.users"].sudo().search([('login', '=', operator_login)], limit=1)
            if not operator:
                return {"ok": False, "error": "Operador no encontrado"}

            session = request.env["wmds.dispatch.session"].sudo().search([
                ('operator_id', '=', operator.id),
                ('state', '=', 'active')
            ], limit=1)

            if not session:
                return {"ok": False, "error": "No hay sesión activa"}

            line = request.env["wmds.dispatch.session.line"].sudo().search([
                ('session_id', '=', session.id),
                ('ei_name', '=', ei_name)
            ], limit=1)

            if line:
                line.unlink()
                return {"ok": True}
            
            return {"ok": False, "error": "Línea no encontrada"}

        except Exception as e:
            _logger.error(f"Error en remove_dispatch_session_line: {e}")
            return {"ok": False, "error": str(e)}

    # ─────────────────────────────────────────────
    # CLEAR all lines from the session
    # ─────────────────────────────────────────────
    @http.route('/wmds/v2/engine/post/clear_dispatch_session', type='json', auth='user', methods=['POST'], csrf=True)
    def clear_dispatch_session(self, **kw):
        """Limpia todas las líneas de la sesión activa sin cancelarla."""
        try:
            operator_login = kw.get("operator_login")
            if not operator_login:
                return {"ok": False, "error": "Datos incompletos"}

            operator = request.env["res.users"].sudo().search([('login', '=', operator_login)], limit=1)
            if not operator:
                return {"ok": False, "error": "Operador no encontrado"}

            session = request.env["wmds.dispatch.session"].sudo().search([
                ('operator_id', '=', operator.id),
                ('state', '=', 'active')
            ], limit=1)

            if session and session.line_ids:
                session.line_ids.unlink()

            return {"ok": True}

        except Exception as e:
            _logger.error(f"Error en clear_dispatch_session: {e}")
            return {"ok": False, "error": str(e)}

    # ─────────────────────────────────────────────
    # COMPLETE session
    # ─────────────────────────────────────────────
    @http.route('/wmds/v2/engine/post/complete_dispatch_session', type='json', auth='user', methods=['POST'], csrf=True)
    def complete_dispatch_session(self, **kw):
        """
        Marca la sesión como completada y devuelve todos los datos
        necesarios para generar la hoja de salida imprimible.
        """
        try:
            operator_login = kw.get("operator_login")
            if not operator_login:
                return {"ok": False, "error": "Datos incompletos"}

            operator = request.env["res.users"].sudo().search([('login', '=', operator_login)], limit=1)
            if not operator:
                return {"ok": False, "error": "Operador no encontrado"}

            session = request.env["wmds.dispatch.session"].sudo().search([
                ('operator_id', '=', operator.id),
                ('state', '=', 'active')
            ], limit=1)

            if not session:
                return {"ok": False, "error": "No hay sesión activa"}

            session.write({
                'state': 'completed',
                'date_end': fields.Datetime.now(),
            })

            request.env["wmds.dispatch.sheet"].sudo().create_from_session(session)

            lines_data = []
            so_summary = {}
            for line in session.line_ids.sorted('scan_datetime'):
                lines_data.append({
                    "ei_name": line.ei_name,
                    "so_name": line.so_name,
                    "product_name": line.product_name or "",
                    "carrier_name": line.carrier_name or "",
                    "scan_datetime": fields.Datetime.to_string(line.scan_datetime) if line.scan_datetime else "",
                    "sequence_number": line.sequence_number,
                    "total_ei": line.total_ei,
                })

                #Agrupar por SO para el resumen
                if line.so_name not in so_summary:
                    so_summary[line.so_name] = {
                        "so_name": line.so_name,
                        "carrier_name": line.carrier_name or "",
                        "product_name": line.product_name or "",
                        "total_ei": line.total_ei,
                        "scanned_count": 0,
                        "ei_list": []
                    }
                so_summary[line.so_name]["scanned_count"] += 1
                so_summary[line.so_name]["ei_list"].append(line.ei_name)

            return {
                "ok": True,
                "session_id": session.id,
                "operator_name": session.operator_name,
                "carrier_name": session.carrier_id.name if session.carrier_id else "",
                "date_start": fields.Datetime.to_string(session.date_start),
                "date_end": fields.Datetime.to_string(session.date_end),
                "lines": lines_data,
                "so_summary": list(so_summary.values()),
                "total_lines": len(lines_data),
            }

        except Exception as e:
            _logger.error(f"Error en complete_dispatch_session: {e}")
            return {"ok": False, "error": str(e)}

    # ─────────────────────────────────────────────
    # CANCEL session
    # ─────────────────────────────────────────────
    @http.route('/wmds/v2/engine/post/cancel_dispatch_session', type='json', auth='user', methods=['POST'], csrf=True)
    def cancel_dispatch_session(self, **kw):
        """Cancela la sesión activa del operador."""
        try:
            operator_login = kw.get("operator_login")
            if not operator_login:
                return {"ok": False, "error": "Datos incompletos"}

            operator = request.env["res.users"].sudo().search([('login', '=', operator_login)], limit=1)
            if not operator:
                return {"ok": False, "error": "Operador no encontrado"}

            session = request.env["wmds.dispatch.session"].sudo().search([
                ('operator_id', '=', operator.id),
                ('state', '=', 'active')
            ], limit=1)

            if session:
                session.write({
                    'state': 'cancelled',
                    'date_end': fields.Datetime.now(),
                })
                return {"ok": True}

            return {"ok": True, "message": "No había sesión activa"}

        except Exception as e:
            _logger.error(f"Error en cancel_dispatch_session: {e}")
            return {"ok": False, "error": str(e)}

    # ─────────────────────────────────────────────
    # GET active sessions (Manager)
    # ─────────────────────────────────────────────
    @http.route('/wmds/v2/engine/post/get_active_dispatch_sessions', type='json', auth='user', methods=['POST'], csrf=True)
    def get_active_dispatch_sessions(self, **kw):
        """
        Devuelve todas las sesiones activas de despacho.
        Para uso del Manager, para ver qué operadores están despachando.
        """
        try:
            sessions = request.env["wmds.dispatch.session"].sudo().search([
                ('state', '=', 'active')
            ], order='date_start desc')

            result = []
            for session in sessions:
                so_set = set()
                for line in session.line_ids:
                    so_set.add(line.so_name)

                result.append({
                    "session_id": session.id,
                    "operator_name": session.operator_name,
                    "operator_login": session.operator_login,
                    "date_start": fields.Datetime.to_string(session.date_start),
                    "total_scanned": len(session.line_ids),
                    "orders": list(so_set),
                })

            return {"sessions": result}

        except Exception as e:
            _logger.error(f"Error en get_active_dispatch_sessions: {e}")
            return {"sessions": [], "error": str(e)}

    # ─────────────────────────────────────────────
    # GET carrier list
    # ─────────────────────────────────────────────
    @http.route('/wmds/v2/engine/post/get_carrier_list', type='json', auth='user', methods=['POST'], csrf=True)
    def get_carrier_list(self, **kw):
        try:
            carriers = request.env["carriers.list"].sudo().search([], order="name")
            return {
                "ok": True,
                "carriers": [{"id": c.id, "name": c.name} for c in carriers]
            }
        except Exception as e:
            _logger.error(f"Error en get_carrier_list: {e}")
            return {"ok": False, "carriers": []}