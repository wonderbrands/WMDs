# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class ComexReleaseWizard(models.TransientModel):
    _name = 'comex.release.wizard'
    _description = 'Wizard de Liberación COMEX'

    purchase_order_id = fields.Many2one(
        'purchase.order',
        string='Orden de Compra',
        required=True,
        readonly=True,
    )
    purchase_order_name = fields.Char(
        related='purchase_order_id.name',
        string='Referencia PO',
    )
    line_ids = fields.One2many(
        'comex.release.wizard.line',
        'wizard_id',
        string='Líneas a Trasladar',
    )
    notes = fields.Text(
        string='Observaciones COMEX',
    )
    auto_validate = fields.Boolean(
        string='Auto-validar traslados',
        default=False,
        help=(
            'Si se activa, los traslados se validan automáticamente. '
            'Si no, quedan como "Listo" para que almacén los valide.'
        ),
    )
    warning_message = fields.Text(
        string='Advertencias',
        compute='_compute_warnings',
    )
    has_warnings = fields.Boolean(
        compute='_compute_warnings',
    )

    @api.depends('line_ids', 'line_ids.to_transfer',
                 'line_ids.storage_location_id')
    def _compute_warnings(self):
        for wizard in self:
            warnings = []

            unmapped = wizard.line_ids.filtered(
                lambda l: l.to_transfer and not l.storage_location_id
            )
            if unmapped:
                products = ', '.join(
                    unmapped.mapped('product_id.display_name')
                )
                warnings.append(
                    '⚠ Sin ubicación de almacenaje mapeada: %s. '
                    'Verifique que existan las ubicaciones equivalentes '
                    'en Stock/Almacenaje.' % products
                )

            reserved = wizard.line_ids.filtered(
                lambda l: l.to_transfer and l.reserved_quantity > 0
            )
            if reserved:
                warnings.append(
                    '⚠ Algunos productos tienen cantidad reservada. '
                    'El traslado podría fallar si no se liberan '
                    'las reservas primero.'
                )

            unrelated = wizard.line_ids.filtered(
                lambda l: l.to_transfer and not l.has_related_move
            )
            if unrelated:
                products = ', '.join(
                    unrelated.mapped('product_id.display_name')
                )
                warnings.append(
                    'ℹ No se confirmó trazabilidad directa con la PO '
                    'para: %s. Podría ser stock de otra PO en la misma '
                    'ubicación. Verifique antes de confirmar.' % products
                )

            wizard.warning_message = (
                '\n\n'.join(warnings) if warnings else False
            )
            wizard.has_warnings = bool(warnings)

    def _populate_lines(self, quarantine_data):
        """Crea las líneas del wizard con los datos de cuarentena."""
        self.ensure_one()
        WizardLine = self.env['comex.release.wizard.line']

        for data in quarantine_data:
            WizardLine.create({
                'wizard_id': self.id,
                'product_id': data['product_id'],
                'quantity_in_quarantine': data['quantity'],
                'reserved_quantity': data['reserved_quantity'],
                'available_quantity': data['available_quantity'],
                'quantity_to_transfer': data['available_quantity'],
                'lot_id': data.get('lot_id', False),
                'quarantine_location_id': data['quarantine_location_id'],
                'storage_location_id': data.get('storage_location_id', False),
                'uom_id': data['uom_id'],
                'has_related_move': data.get('has_related_move', False),
                'to_transfer': bool(data.get('storage_location_id')),
            })

    def action_confirm_release(self):
        """
        Confirma la liberación:
        1. Valida las líneas seleccionadas
        2. Activa check_commertial en la PO
        3. Crea los traslados internos
        4. Opcionalmente auto-valida
        """
        self.ensure_one()

        lines_to_transfer = self.line_ids.filtered(
            lambda l: l.to_transfer and l.quantity_to_transfer > 0
        )

        # Validaciones
        unmapped = lines_to_transfer.filtered(
            lambda l: not l.storage_location_id
        )
        if unmapped:
            raise ValidationError(
                'Las siguientes líneas no tienen ubicación de '
                'almacenaje: %s. Verifique que existan las ubicaciones '
                'equivalentes o desmarque la línea.'
                % ', '.join(unmapped.mapped('product_id.display_name'))
            )

        for line in lines_to_transfer:
            if line.quantity_to_transfer > line.available_quantity:
                raise ValidationError(
                    'La cantidad a trasladar de "%s" (%s) excede la '
                    'cantidad disponible (%s).'
                    % (line.product_id.display_name,
                       line.quantity_to_transfer,
                       line.available_quantity)
                )
            if line.quantity_to_transfer <= 0:
                raise ValidationError(
                    'La cantidad a trasladar de "%s" debe ser mayor a 0.'
                    % line.product_id.display_name
                )

        # 1. Activar VoBo
        po = self.purchase_order_id
        po._activate_comex_vobo()

        # 2. Crear traslados
        pickings = self.env['stock.picking']
        if lines_to_transfer:
            lines_data = []
            for line in lines_to_transfer:
                lines_data.append({
                    'product_id': line.product_id.id,
                    'product_name': line.product_id.display_name,
                    'quantity_to_transfer': line.quantity_to_transfer,
                    'lot_id': line.lot_id.id if line.lot_id else False,
                    'quarantine_location_id': line.quarantine_location_id.id,
                    'storage_location_id': line.storage_location_id.id,
                    'uom_id': line.uom_id.id,
                })

            pickings = po._create_quarantine_release_transfer(lines_data)

            # 3. Auto-validar si se seleccionó
            if self.auto_validate and pickings:
                for picking in pickings:
                    try:
                        for move in picking.move_ids:
                            move.quantity = move.product_uom_qty
                        picking.button_validate()
                    except Exception as e:
                        _logger.error(
                            'Error al auto-validar picking %s: %s',
                            picking.name, str(e)
                        )

        # Registrar notas si las hay
        if self.notes:
            self.env['wmds.log'].sudo().create({
                'purchase': po.id,
                'log': 'COMEX nota: %s' % self.notes,
                'user': self.env.user.id,
                'date': fields.Datetime.now(),
            })

        # Retornar vista del picking o notificación
        if len(pickings) == 1:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'stock.picking',
                'res_id': pickings.id,
                'view_mode': 'form',
                'target': 'current',
            }
        elif len(pickings) > 1:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'stock.picking',
                'domain': [('id', 'in', pickings.ids)],
                'view_mode': 'list,form',
                'target': 'current',
                'name': 'Traslados Liberación COMEX',
            }

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'VoBo COMEX Activado',
                'message': 'El VoBo fue activado. No se generaron traslados.',
                'type': 'success',
                'sticky': False,
            },
        }


class ComexReleaseWizardLine(models.TransientModel):
    _name = 'comex.release.wizard.line'
    _description = 'Línea del Wizard de Liberación COMEX'

    wizard_id = fields.Many2one(
        'comex.release.wizard',
        string='Wizard',
        required=True,
        ondelete='cascade',
    )
    to_transfer = fields.Boolean(
        string='Trasladar',
        default=True,
    )
    product_id = fields.Many2one(
        'product.product',
        string='Producto',
        readonly=True,
    )
    quantity_in_quarantine = fields.Float(
        string='Cant. Cuarentena',
        readonly=True,
        digits='Product Unit of Measure',
    )
    reserved_quantity = fields.Float(
        string='Cant. Reservada',
        readonly=True,
        digits='Product Unit of Measure',
    )
    available_quantity = fields.Float(
        string='Cant. Disponible',
        readonly=True,
        digits='Product Unit of Measure',
    )
    quantity_to_transfer = fields.Float(
        string='Cant. a Trasladar',
        digits='Product Unit of Measure',
    )
    lot_id = fields.Many2one(
        'stock.lot',
        string='Lote/Serie',
        readonly=True,
    )
    quarantine_location_id = fields.Many2one(
        'stock.location',
        string='Ubicación Cuarentena',
        readonly=True,
    )
    storage_location_id = fields.Many2one(
        'stock.location',
        string='Ubicación Almacenaje',
    )
    uom_id = fields.Many2one(
        'uom.uom',
        string='UdM',
        readonly=True,
    )
    has_related_move = fields.Boolean(
        string='Trazabilidad',
        readonly=True,
    )
