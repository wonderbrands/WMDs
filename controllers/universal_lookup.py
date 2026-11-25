# -*- coding: utf-8 -*-
import logging
import json
from odoo import http, fields
from odoo.http import request
from .location_preview import LocationPreviewController

logger = logging.getLogger(__name__)


class UniversalLookupController(http.Controller):

    @http.route('/wmds/v2/engine/scan/universal_lookup', type='json', auth='user', methods=['POST'], csrf=True)
    def universal_lookup(self, **kw):
        """Universal scanner lookup for WMDs Operator.
        Detects barcode as:
        1. stock.location
        2. product.product / product.template
        3. bin.storage
        4. dock.storage
        Supports JSON-encoded QR codes (e.g. {"name": "10"} used by BIN and DOCK).
        """
        raw_barcode = (kw.get('barcode') or kw.get('code') or kw.get('raw_barcode') or '').strip()
        client_tz = kw.get('tz') or request.env.user.tz or 'America/Mexico_City'

        if not raw_barcode:
            return {
                "status": "error",
                "message": "Debe escanear o ingresar un código."
            }

        # Extraer candidatos de búsqueda si viene formateado en JSON (QR de BIN/DOCK)
        search_terms = []
        trimmed = raw_barcode.strip()
        
        if (trimmed.startswith('{') and trimmed.endswith('}')) or (trimmed.startswith('[') and trimmed.endswith(']')):
            try:
                parsed = json.loads(trimmed)
                if isinstance(parsed, dict):
                    for key in ['name', 'bin', 'dock', 'location', 'barcode', 'code']:
                        val = parsed.get(key)
                        if val is not None and str(val).strip() and str(val).strip() not in search_terms:
                            search_terms.append(str(val).strip())
                elif isinstance(parsed, list):
                    for item in parsed:
                        if isinstance(item, (str, int)) and str(item).strip() and str(item).strip() not in search_terms:
                            search_terms.append(str(item).strip())
            except Exception:
                pass

        if raw_barcode not in search_terms:
            search_terms.append(raw_barcode)

        # 1. Intentar Ubicación (stock.location)
        loc_env = request.env['stock.location'].sudo()
        location = False
        for term in search_terms:
            location = loc_env.search([('barcode', '=', term)], limit=1)
            if not location:
                location = loc_env.search([('complete_name', '=', term)], limit=1)
            if not location:
                location = loc_env.search([('name', '=', term)], limit=1)
            if location:
                break

        if location:
            loc_controller = LocationPreviewController()
            preview_res = loc_controller.get_location_preview(barcode=location.barcode or location.name, tz=client_tz)
            if preview_res.get('status') == 'ok':
                return {
                    "status": "success",
                    "type": "location",
                    "data": preview_res
                }

        # 2. Intentar Producto (product.product)
        prod_env = request.env['product.product'].sudo()
        product = False
        for term in search_terms:
            product = prod_env.search([('barcode', '=', term)], limit=1)
            if not product:
                product = prod_env.search([('default_code', '=', term)], limit=1)
            if not product:
                tmpl = request.env['product.template'].sudo().search([
                    '|', ('barcode', '=', term), ('default_code', '=', term)
                ], limit=1)
                if tmpl:
                    product = tmpl.product_variant_id or prod_env.search([('product_tmpl_id', '=', tmpl.id)], limit=1)
            if product:
                break

        if product:
            p_len = getattr(product, 'packing_length', 0.0) or 0.0
            p_wid = getattr(product, 'packing_width', 0.0) or 0.0
            p_hei = getattr(product, 'packing_height', 0.0) or 0.0
            p_wei = getattr(product, 'packing_weight', 0.0) or getattr(product, 'weight', 0.0) or 0.0
            p_vol = getattr(product, 'volume', 0.0) or 0.0

            quants = request.env['stock.quant'].sudo().search([
                ('product_id', '=', product.id),
                ('quantity', '>', 0),
                ('location_id.usage', '=', 'internal')
            ], order='quantity desc')

            locations_stock = []
            total_qty = 0.0
            total_reserved = 0.0

            for q in quants:
                qty = q.quantity or 0.0
                reserved = q.reserved_quantity or 0.0
                avail = qty - reserved
                total_qty += qty
                total_reserved += reserved

                locations_stock.append({
                    "quant_id": q.id,
                    "location_id": q.location_id.id,
                    "location_name": q.location_id.display_name,
                    "barcode": q.location_id.barcode or '',
                    "lot_name": q.lot_id.name if q.lot_id else False,
                    "quantity": qty,
                    "reserved_quantity": reserved,
                    "available_quantity": avail,
                    "uom": q.product_uom_id.name if q.product_uom_id else ''
                })

            return {
                "status": "success",
                "type": "product",
                "data": {
                    "product": {
                        "id": product.id,
                        "name": product.display_name,
                        "default_code": product.default_code or '',
                        "barcode": product.barcode or '',
                        "image_url": f"/web/image/product.product/{product.id}/image_256",
                        "uom": product.uom_id.name if product.uom_id else 'Unidades',
                        "dimensions": {
                            "length": round(float(p_len), 2),
                            "width": round(float(p_wid), 2),
                            "height": round(float(p_hei), 2),
                            "weight": round(float(p_wei), 3),
                            "volume": round(float(p_vol), 4),
                        }
                    },
                    "stock_summary": {
                        "total_quantity": total_qty,
                        "total_reserved": total_reserved,
                        "total_available": total_qty - total_reserved,
                        "locations_count": len(locations_stock),
                        "locations": locations_stock
                    }
                }
            }

        # 3. Intentar BIN (bin.storage)
        bin_env = request.env['bin.storage'].sudo()
        bin_record = False
        for term in search_terms:
            bin_record = bin_env.search([('name', '=', term)], limit=1)
            if bin_record:
                break

        if bin_record:
            packages = []
            for ei in bin_record.ei:
                st = "Despachado" if ei.dispatched else ("En Dock" if ei.on_dock else ("En Bin" if ei.on_bin else "Pendiente"))
                packages.append({
                    "id": ei.id,
                    "name": ei.display_name_custom or ei.name or '',
                    "so_name": ei.so_id.name if ei.so_id else '',
                    "status": st,
                    "carrier": ei.carrier_name if hasattr(ei, 'carrier_name') else ''
                })

            moves = []
            for m in bin_record.moves:
                moves.append({
                    "id": m.id,
                    "product_id": m.product_id.id,
                    "product_name": m.product_id.display_name,
                    "default_code": m.product_id.default_code or '',
                    "image_url": f"/web/image/product.product/{m.product_id.id}/image_128",
                    "demand_qty": m.product_uom_qty,
                    "done_qty": m.quantity,
                    "picking_name": m.picking_id.name if m.picking_id else '',
                    "state": m.state
                })

            return {
                "status": "success",
                "type": "bin",
                "data": {
                    "id": bin_record.id,
                    "name": bin_record.name,
                    "state": bin_record.state,
                    "state_label": "Disponible" if bin_record.state == 'available' else "Bloqueado",
                    "carrier": bin_record.carrier_id.name if bin_record.carrier_id else '',
                    "origin_doc": bin_record.origin_doc or '',
                    "packages_count": len(packages),
                    "packages": packages,
                    "moves_count": len(moves),
                    "moves": moves
                }
            }

        # 4. Intentar DOCK (dock.storage)
        dock_env = request.env['dock.storage'].sudo()
        dock_record = False
        for term in search_terms:
            dock_record = dock_env.search([('name', '=', term)], limit=1)
            if dock_record:
                break

        if dock_record:
            packages = []
            for ei in dock_record.ei:
                st = "Despachado" if ei.dispatched else ("En Dock" if ei.on_dock else ("En Bin" if ei.on_bin else "Pendiente"))
                packages.append({
                    "id": ei.id,
                    "name": ei.display_name_custom or ei.name or '',
                    "so_name": ei.so_id.name if ei.so_id else '',
                    "status": st,
                    "carrier": ei.carrier_name if hasattr(ei, 'carrier_name') else ''
                })

            moves = []
            for m in dock_record.moves:
                moves.append({
                    "id": m.id,
                    "product_id": m.product_id.id,
                    "product_name": m.product_id.display_name,
                    "default_code": m.product_id.default_code or '',
                    "image_url": f"/web/image/product.product/{m.product_id.id}/image_128",
                    "demand_qty": m.product_uom_qty,
                    "done_qty": m.quantity,
                    "picking_name": m.picking_id.name if m.picking_id else '',
                    "state": m.state
                })

            return {
                "status": "success",
                "type": "dock",
                "data": {
                    "id": dock_record.id,
                    "name": dock_record.name,
                    "state": dock_record.state,
                    "state_label": "Disponible" if dock_record.state == 'available' else "Bloqueado",
                    "packages_count": len(packages),
                    "packages": packages,
                    "moves_count": len(moves),
                    "moves": moves
                }
            }

        # 5. No encontrado
        return {
            "status": "not_found",
            "message": f"Código '{raw_barcode}' no corresponde a una Ubicación, Producto, BIN o DOCK."
        }
