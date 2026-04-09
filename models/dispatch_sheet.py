from odoo import models, fields, api
import base64
import logging

_logger = logging.getLogger(__name__)


class WmdsDispatchSheet(models.Model):
    _name = "wmds.dispatch.sheet"
    _description = "Hoja de Salida (PDF persistido)"
    _order = "create_date desc"

    name = fields.Char(string="Referencia", required=True, readonly=True)
    session_id = fields.Many2one(
        "wmds.dispatch.session", string="Sesión de Despacho",
        required=True, readonly=True, ondelete="cascade",
    )
    operator_id = fields.Many2one("res.users", string="Operador", readonly=True)
    date_dispatched = fields.Datetime(string="Fecha de Despacho", readonly=True)
    total_packages = fields.Integer(string="Total Paquetes", readonly=True)
    so_names = fields.Char(string="Órdenes de Venta", readonly=True)
    pdf_file = fields.Binary(string="PDF Hoja de Salida", attachment=True, readonly=True)
    pdf_filename = fields.Char(string="Nombre Archivo")
    
    
    line_ids = fields.One2many(related='session_id.line_ids', string="Líneas de Escaneo", readonly=True)

    def action_download_pdf(self):
        """Abre el PDF almacenado para descarga / impresión."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{self._name}/{self.id}/pdf_file/{self.pdf_filename}?download=true',
            'target': 'new',
        }

    def action_reprint(self):
        """Re-imprime usando el reporte original de la sesión (IoT)."""
        self.ensure_one()
        report = self.env.ref('wmds.action_report_dispatch_sheet')
        return report.report_action(self.session_id.id)

    @api.model
    def create_from_session(self, session):
        existing = self.search([('session_id', '=', session.id)], limit=1)
        if existing:
            return existing
        
        report = self.env.ref('wmds.action_report_dispatch_sheet')
        pdf_content, _ = report._render_qweb_pdf(report.report_name, [session.id])
        
        date_str = fields.Datetime.now().strftime('%d%b')
        carrier_label = session.carrier_id.name if session.carrier_id else "HOJA"
        name = f"{carrier_label}-{session.id}-{date_str}"

        # Órdenes asociadas
        so_list = list({line.so_name for line in session.line_ids if line.so_name})
        so_names = ', '.join(sorted(so_list))

        sheet = self.create({
            'name': name,
            'session_id': session.id,
            'operator_id': session.operator_id.id if hasattr(session, 'operator_id') else self.env.uid,
            'date_dispatched': session.date_end or fields.Datetime.now(),
            'total_packages': len(session.line_ids),
            'so_names': so_names,
            'pdf_file': base64.b64encode(pdf_content),
            'pdf_filename': f"{name}.pdf",
        })
        return sheet