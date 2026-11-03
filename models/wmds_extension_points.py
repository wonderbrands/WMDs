# -*- coding: utf-8 -*-
"""Puntos de extensión del núcleo WMDs.

Los complementos de WMDs (`wmds_<funcionalidad>`) heredan estos modelos y sobrescriben
estos métodos para engancharse al despacho y a la sesión de despacho sin tocar los
controladores del núcleo. Cada método devuelve aquí su valor neutro: sin complementos,
WMDs se comporta exactamente igual que sin ellos.

Al sobrescribir, combinar siempre con `super()` para no anular a otros complementos.
"""
from odoo import models


class SaleOrderEIExtensionPoints(models.Model):
    _inherit = "sale.order.ei"

    def _wmds_dispatch_prefilter(self, operator=None):
        """Antes de las validaciones de `dispatch_packet` (solo despacho síncrono).

        :param operator: res.users del despachador (puede estar vacío).
        :return: (EI que siguen en el despacho, mensaje de error o False). Un error
            detiene el despacho y se devuelve tal cual al front.
        """
        return self, False

    def _wmds_dispatch_handle(self, operator=None):
        """Las EI que un complemento resuelve por su cuenta, fuera del flujo normal.

        Se llama en `dispatch_packet` y en la tarea en cola (`_execute_dispatch_package`).

        :return: dict con
            - ``consumed``: EI que el núcleo ya no debe procesar.
            - ``handled``: EI resueltas con éxito (el núcleo marca `dispatch_status`).
            - ``errors``: mensajes; en el despacho síncrono detienen el despacho,
              en la cola se registran como advertencia.
            - ``log``: líneas para el detalle de la tarea en cola.
        """
        empty = self.browse()
        return {'consumed': empty, 'handled': empty, 'errors': [], 'log': []}

    def _wmds_scan_extra_values(self):
        """Datos extra para la respuesta de `validate_attachment_guide` (una EI).

        :return: dict que se agrega a la respuesta.
        """
        return {}


class SaleOrderExtensionPoints(models.Model):
    _inherit = "sale.order"

    def _wmds_dispatch_allows_cancelled(self):
        """True si esta SO cancelada puede pasar por `dispatch_packet` porque un
        complemento la resuelve (ver `_wmds_dispatch_handle`)."""
        self.ensure_one()
        return False


class WmdsDispatchSessionExtensionPoints(models.Model):
    _inherit = "wmds.dispatch.session"

    def _wmds_after_line_removed(self, ei_name, so_name, cancelled_removal=False, operator=None):
        """Después de quitar una línea de la sesión (`remove_dispatch_session_line`)."""
        return None

    def _wmds_on_session_released(self, lines):
        """Las líneas de la sesión se liberan sin despacharse: sesión limpiada
        (`clear_dispatch_session`, antes de borrar las líneas) o cancelada
        (`cancel_dispatch_session`, después de cancelarla)."""
        return None


class WmdsDispatchSessionLineExtensionPoints(models.Model):
    _inherit = "wmds.dispatch.session.line"

    def _wmds_extra_values(self):
        """Datos extra por línea para `get_dispatch_session`.

        :return: {line.id: dict} con lo que se agrega a cada línea de la respuesta.
        """
        return {line.id: {} for line in self}


class WmdsFeatures(models.AbstractModel):
    _name = "wmds.features"
    _description = "Funcionalidades de complementos WMDs activas"

    def _wmds_features(self):
        """Funcionalidades que el front puede mostrar (`/wmds/v2/features`).

        Cada complemento agrega su clave: ``res = super()._wmds_features(); res['x'] = True``.

        :return: dict {clave: True}. Una clave ausente = complemento no instalado.
        """
        return {}
