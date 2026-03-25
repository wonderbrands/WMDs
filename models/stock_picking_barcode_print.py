from odoo import models, fields, api


class StockPickingBarcodePrint(models.Model):
    _inherit = 'stock.picking'

    data_barcode_printed = fields.Boolean(
        string='Impreso desde Barcode',
        default=False,
        copy=False,
        help="Se marca True cuando la impresión se dispara desde el botón Validar del barcode."
    )

    def _get_fields_stock_barcode(self):
        """Agrega data_barcode_printed a los campos cargados en la vista barcode."""
        fields = super()._get_fields_stock_barcode()
        fields.append('data_barcode_printed')
        return fields

    def action_print_guia_from_barcode(self):
        """
        Retorna la acción de reporte de GUÍA (report_attachment_dummy)
        usando el sale_order.id como res_id.
        Retorna False si no hay adjuntos (para que el JS sepa que no hay nada que imprimir).
        """
        self.ensure_one()
        if not self.sale_id:
            return False
        
        # Verificar que existen adjuntos antes de disparar
        has_attachments = self.env['sale.order.attachment'].search_count([
            ('so_id', '=', self.sale_id.id)
        ])
        if not has_attachments:
            return False

        report = self.env.ref('wb_printer_IoT.action_report_print_attachment_4x8')
        return report.report_action(self.sale_id)

    def action_print_etiqueta_from_barcode(self):
        """
        Retorna la acción de reporte de ETIQUETA ZPL (report_zpl_backup)
        usando el sale_order.id como res_id.
        Retorna False si es mayoreo (para que el JS sepa que no hay nada que imprimir).
        """
        self.ensure_one()
        if not self.sale_id:
            return False

        # Verificar mayoreo antes de disparar
        team_name = self.sale_id.team_id.name if self.sale_id.team_id else ""
        if 'mayoreo' in team_name.lower():
            return False

        report = self.env.ref('wb_printer_IoT.action_report_zpl_backup')
        return report.report_action(self.sale_id)

    def action_mark_barcode_printed(self):
        """Marca el picking como ya impreso desde barcode."""
        self.ensure_one()
        self.data_barcode_printed = True
        return True