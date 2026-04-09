from odoo import models, api, fields


class WmdsDispatchSessionReport(models.Model):
    _inherit = 'wmds.dispatch.session'
    
    carrier_id = fields.Many2one("carriers.list", string="Carrier de sesión")

    carrier_name_session = fields.Char(related="carrier_id.name", store=True, string="Carrier")

    def _get_so_summary(self):
        """
        Agrupa las líneas de la sesión por SO para el resumen
        en la hoja de salida PDF.
        """
        self.ensure_one()
        summary = {}
        for line in self.line_ids.sorted('scan_datetime'):
            if line.so_name not in summary:
                summary[line.so_name] = {
                    'so_name': line.so_name,
                    'carrier_name': line.carrier_name or '',
                    'product_name': line.product_name or '',
                    'total_ei': line.total_ei,
                    'scanned_count': 0,
                }
            summary[line.so_name]['scanned_count'] += 1
        return list(summary.values())