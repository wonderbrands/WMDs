from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class WmdsDispatchSession(models.Model):
    '''
    sesión del operador con estado active/completed/cancelled
    '''
    
    _name = 'wmds.dispatch.session'
    _description = 'Sesión de Despacho WMDs'
    _order = 'date_start desc'

    operator_id = fields.Many2one('res.users', string='Operador', required=True, index=True)
    operator_login = fields.Char(string='Login del Operador', related='operator_id.login', store=True)
    operator_name = fields.Char(string='Nombre del Operador', related='operator_id.name', store=True)
    state = fields.Selection([
        ('active', 'Activa'),
        ('completed', 'Completada'),
        ('cancelled', 'Cancelada'),
    ], string='Estado', default='active', required=True, index=True)
    date_start = fields.Datetime(string='Fecha de Inicio', default=fields.Datetime.now, required=True)
    date_end = fields.Datetime(string='Fecha de Cierre')
    line_ids = fields.One2many('wmds.dispatch.session.line', 'session_id', string='Líneas de Escaneo')
    line_count = fields.Integer(string='Total Líneas', compute='_compute_line_count', store=True)

    @api.depends('line_ids')
    def _compute_line_count(self):
        for record in self:
            record.line_count = len(record.line_ids)


class WmdsDispatchSessionLine(models.Model):
    '''
    cada EI escaneada, con producto, carrier, fecha de escaneo
    '''
    
    _name = 'wmds.dispatch.session.line'
    _description = 'Línea de Sesión de Despacho WMDs'
    _order = 'scan_datetime desc'

    session_id = fields.Many2one('wmds.dispatch.session', string='Sesión', required=True, ondelete='cascade', index=True)
    ei_name = fields.Char(string='Etiqueta Interna (EI)', required=True)  # e.g. SO12345/1
    so_name = fields.Char(string='Orden de Venta', required=True)  # e.g. SO12345
    product_name = fields.Char(string='Producto')
    carrier_name = fields.Char(string='Carrier / Paquetería')
    scan_datetime = fields.Datetime(string='Fecha/Hora de Escaneo', default=fields.Datetime.now)
    sequence_number = fields.Integer(string='No. de Etiqueta')
    total_ei = fields.Integer(string='Total EI de la Orden')
    dispatched_count = fields.Integer(string='Despachados al momento del escaneo')