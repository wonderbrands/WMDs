from odoo import models, api


class WmdsDispatchSessionReport(models.Model):
    _inherit = 'wmds.dispatch.session'

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