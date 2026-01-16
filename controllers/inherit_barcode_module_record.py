from odoo.addons.stock_barcode.controllers.stock_barcode import StockBarcodeController
from odoo import http

class StockBarcodeControllerInherit(StockBarcodeController):

    def get_barcode_data(self, model, res_id):
        pass
        """
        result = super().get_barcode_data(model, res_id)

        record = result["data"].get("record", {})

        picking = http.request.env[model].browse(res_id)
        if picking.operator:
            record["operator"] = {
                "id": picking.operator.id,
                "name": picking.operator.name,
            }
        else:
            record["operator"] = False

        return result"""
