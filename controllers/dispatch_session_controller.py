from odoo import http, fields
from odoo.http import request
import logging

_logger = logging.getLogger(__name__)


class DispatchSessionController(http.Controller):

    @staticmethod
    def _so_cancel_held(so_name, cache=None):
        """True si la SO está cancelada con su OUT retenido por despacho
        (requiere el módulo wb_so_cancel_guarderia)."""
        if cache is not None and so_name in cache:
            return cache[so_name]
        so = request.env['sale.order'].sudo().search([('name', '=', so_name)], limit=1) if so_name else False
        held = bool(so) and so._wmds_is_cancel_held()
        if cache is not None:
            cache[so_name] = held
        return held

    # ─────────────────────────────────────────────
    # MARK a cancelled EI as already shipped (in the carrier's container)
    # ─────────────────────────────────────────────
    @http.route('/wmds/v2/engine/post/mark_cancelled_shipped', type='json', auth='user', methods=['POST'], csrf=True)
    def mark_cancelled_shipped(self, **kw):
        """
        El despachador indica que la EI de una orden cancelada YA está dentro del
        contenedor/carrier y no se puede sacar. Si la orden tiene varios productos,
        debe indicarse cuál (product_id); si falta, se devuelve la lista de opciones.
        """
        try:
            operator_login = kw.get("operator_login")
            ei_name = kw.get("ei_name")
            product_id = kw.get("product_id")
            if not operator_login or not ei_name:
                return {"ok": False, "message": "Datos incompletos"}

            tag = request.env["sale.order.ei"].sudo().search([('display_name_custom', '=', ei_name)], limit=1)
            if not tag or not tag.so_id:
                return {"ok": False, "message": f"La guía {ei_name} no existe."}
            so = tag.so_id
            if not so._wmds_is_cancel_held():
                return {"ok": False, "message": f"La orden {so.name} no admite marcar paquetes como embarcados: "
                                              f"se canceló antes de entrar al despacho. Retírala físicamente."}

            products = so._wmds_cancel_hold_products()
            # Si ya tenía producto asignado, liberar esa pieza para recalcular
            if tag.wmds_cancel_decision == 'shipped' and tag.wmds_cancel_product_id:
                for p in products:
                    if p['id'] == tag.wmds_cancel_product_id.id:
                        p['remaining'] += 1
            available = [p for p in products if p['remaining'] >= 1]

            if len({p['id'] for p in products}) > 1:
                if not product_id:
                    return {"ok": True, "need_product": True, "products": available}
                if int(product_id) not in [p['id'] for p in available]:
                    return {"ok": False, "message": "El producto seleccionado no tiene piezas pendientes en esta orden.",
                            "need_product": True, "products": available}
                product = int(product_id)
            else:
                if not available:
                    return {"ok": False, "message": "Ya se marcaron como embarcadas todas las piezas de esta orden."}
                product = available[0]['id']

            tag.write({'wmds_cancel_decision': 'shipped', 'wmds_cancel_product_id': product})
            operator = request.env["res.users"].sudo().search([('login', '=', operator_login)], limit=1)
            request.env["wmds.log"].sudo().create({
                "sale": so.id,
                "user": operator.id if operator else request.env.user.id,
                "log": f"Operador {operator.name if operator else operator_login} confirmó que el paquete "
                       f"{ei_name} de la orden cancelada ya está embarcado en el carrier.",
            })
            return {"ok": True, "need_product": False}

        except Exception as e:
            _logger.error(f"Error en mark_cancelled_shipped: {e}")
            return {"ok": False, "message": str(e)}

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
            hold_by_so = {}
            for line in session.line_ids:
                # Find the current state of the SO linked to this line
                so_state = 'draft'
                ei_tag = request.env["sale.order.ei"].sudo().search([('display_name_custom', '=', line.ei_name)], limit=1)
                if ei_tag:
                    so_state = ei_tag.so_id.state
                elif line.so_name:
                    so = request.env['sale.order'].sudo().search([('name', '=', line.so_name)], limit=1)
                    if so:
                        so_state = so.state

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
                    "cancel_hold": self._so_cancel_held(line.so_name, hold_by_so),
                    "cancel_decision": ei_tag.wmds_cancel_decision if ei_tag else False,
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
            cancelled_removal = kw.get("cancelled_removal", False)

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
                so_name = line.so_name

                # Si se remueve por cancelación, registrar en wmds.log de la SO
                if cancelled_removal and so_name:
                    so = request.env["sale.order"].sudo().search([('name', '=', so_name)], limit=1)
                    if so:
                        request.env["wmds.log"].sudo().create({
                            "sale": so.id,
                            "user": operator.id,
                            "log": (
                                f"Operador {operator.name} removió el paquete {ei_name} "
                                f"por cancelación en la etapa de despacho."
                            ),
                        })

                if cancelled_removal:
                    tag = request.env["sale.order.ei"].sudo().search([('display_name_custom', '=', ei_name)], limit=1)
                    if tag:
                        tag.write({'wmds_cancel_decision': 'removed', 'wmds_cancel_product_id': False})
                line.unlink()

                # Si ya no queda ninguna EI de esa orden retenida en despacho, se resuelve:
                # lo retirado (y no entregado) va a Guardería.
                if cancelled_removal and so_name and self._so_cancel_held(so_name):
                    remaining = request.env["wmds.dispatch.session.line"].sudo().search_count([
                        ('so_name', '=', so_name),
                        ('session_id.state', '=', 'active'),
                    ])
                    if not remaining:
                        request.env['sale.order'].sudo().search([('name', '=', so_name)], limit=1) \
                            ._wmds_release_cancel_hold(operator=operator)
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
                session._wmds_release_cancel_holds()
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
                # Las órdenes canceladas que esperaban este despacho ya no se embarcarán.
                lines = session.line_ids
                session.write({
                    'state': 'cancelled',
                    'date_end': fields.Datetime.now(),
                })
                session._wmds_release_cancel_holds(lines)
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