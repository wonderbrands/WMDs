from odoo import models, fields, api


class StockPickingBarcodePrint(models.Model):
    _inherit = 'stock.picking'

    data_barcode_printed = fields.Boolean(
        string='Impreso desde Barcode',
        default=False,
        copy=False,
        help="Se marca True cuando la impresión combinada se dispara desde el botón Validar del barcode."
    )

    def _get_fields_stock_barcode(self):
        """Agrega barcode_printed a los campos cargados en la vista barcode."""
        fields = super()._get_fields_stock_barcode()
        fields.append('data_barcode_printed')
        return fields

    def action_print_combined_barcode(self):
        """
        Retorna la acción de reporte combinado para ser ejecutada vía doAction en el JS.
        Se llama desde barcode_behaviour.js antes de validar.
        """
        self.ensure_one()
        if not self.sale_id:
            return False

        return self.env.ref(
            'wb_printer_IoT.action_report_combined_pack_validate'
        ).report_action(self)

    def action_mark_barcode_printed(self):
        """Marca el picking como ya impreso desde barcode."""
        self.ensure_one()
        self.data_barcode_printed = True
        return True