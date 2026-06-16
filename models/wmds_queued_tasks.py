# -*- coding: utf-8 -*-
from odoo import models, fields, api, SUPERUSER_ID
from odoo.exceptions import UserError
import json
import logging
import traceback
import threading

_logger = logging.getLogger(__name__)

class WmdsQueuedTasks(models.Model):
    _name = 'wmds.queued_tasks'
    _description = 'WMDs Queued Tasks'
    _order = 'id desc'

    task_type = fields.Selection([
        ('move_to_bin', 'Move to Bin'),
        ('move_to_dock', 'Move to Dock'),
        ('dispatch_package', 'Dispatch Package')
    ], string='Task Type', required=True)

    params = fields.Text(string='Parameters', required=True)
    operator_login = fields.Char(string='Operator Login', required=True)
    date_created = fields.Datetime(string='Date Created', default=fields.Datetime.now, required=True)
    date_processed = fields.Datetime(string='Date Processed')
    status = fields.Selection([
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed')
    ], string='Status', default='pending', required=True, index=True)
    error_message = fields.Text(string='Error Message')

    def action_retry(self):
        """Retries the queued task"""
        self.ensure_one()
        self.write({
            'status': 'pending',
            'error_message': False,
            'date_processed': False
        })
        # Process asynchronously immediately
        self._trigger_async_process()
        return True

    def _trigger_async_process(self):
        """Launches a background thread to process the tasks immediately."""
        dbname = self.env.cr.dbname
        registry = self.env.registry
        
        # We start a new thread to process the queued task
        thread = threading.Thread(target=self._process_tasks_thread, args=(registry, dbname))
        thread.daemon = True
        thread.start()

    @classmethod
    def _process_tasks_thread(cls, registry, dbname):
        with registry.cursor() as cr:
            # Try to acquire advisory lock. If another thread is already processing the queue, exit immediately.
            cr.execute("SELECT pg_try_advisory_lock(847192847)")
            if not cr.fetchone()[0]:
                _logger.info("Another queue processor thread is already running. Exiting.")
                return

            try:
                env = api.Environment(cr, SUPERUSER_ID, {})
                # Find any pending tasks
                pending_tasks = env['wmds.queued_tasks'].search([('status', '=', 'pending')], order='id asc')
                for task in pending_tasks:
                    task._process_task()
            finally:
                cr.execute("SELECT pg_advisory_unlock(847192847)")

    def _process_task(self):
        self.ensure_one()
        if self.status != 'pending':
            return
        
        self.write({'status': 'running'})
        self.env.cr.commit() # Commit running state so other workers see it

        try:
            params = json.loads(self.params)
            if self.task_type == 'move_to_bin':
                self._execute_move_to_bin(params)
            elif self.task_type == 'move_to_dock':
                self._execute_move_to_dock(params)
            elif self.task_type == 'dispatch_package':
                self._execute_dispatch_package(params)
            
            self.write({
                'status': 'completed',
                'date_processed': fields.Datetime.now(),
                'error_message': False
            })
        except Exception as e:
            self.env.cr.rollback()
            error_text = f"{str(e)}\n{traceback.format_exc()}"
            _logger.error(f"Error executing queued task {self.id}: {error_text}")
            self.write({
                'status': 'failed',
                'date_processed': fields.Datetime.now(),
                'error_message': error_text
            })
        finally:
            self.env.cr.commit()

    def _execute_move_to_bin(self, params):
        bin_name = params.get("bin")
        operator_login = params.get("operator")
        orders = params.get("orders")
        batch_id = params.get("batch_id")
        pick_id = params.get("pick_id")
        carrier_id = params.get("carrier_id")

        operator_orm = self.env["res.users"].sudo().search([('login', '=', operator_login)], limit=1)
        bin_storage = self.env["bin.storage"].sudo().search([('name', '=', bin_name)], limit=1)
        if not bin_storage:
            raise UserError(f"Bin {bin_name} no encontrado")

        if carrier_id:
            bin_storage.write({'carrier_id': int(carrier_id)})

        bin_log = self.env["bin.log"].sudo().search([('bin_id', '=', bin_storage.id)], limit=1)
        if not bin_log:
            bin_log = self.env["bin.log"].sudo().create({'bin_id': bin_storage.id})

        operator_name = operator_orm.name if operator_orm else "Desconocido"

        if batch_id or pick_id:
            if batch_id:
                batch = self.env['stock.picking.batch'].sudo().browse(batch_id)
                pickings = batch.picking_ids
                log_target = {"batch_pick": batch.id}
                log_label = f"Lote {batch.name}"
            else:
                picking = self.env['stock.picking'].sudo().browse(pick_id)
                pickings = picking
                log_target = {"pick": picking.id}
                log_label = f"Traslado {picking.name}"

            moves = pickings.mapped('move_ids').filtered(lambda m: m.state == 'done' and not m.dispatched)
            
            for move in moves:
                if move.write_date and self.date_created and move.write_date > self.date_created:
                    _logger.info(f"Skipping stale move_to_bin for move {move.id} (task date_created: {self.date_created}, write_date: {move.write_date})")
                    continue
                move.write({
                    'on_bin': True,
                    'bin_id': bin_storage.id,
                    'on_dock': False,
                    'dock_id': False,
                    'dispatched': False
                })
                
                log_msg = f"El operador {operator_name} puso el producto {move.product_id.display_name} (de la orden {move.picking_id.name}) en el bin {bin_storage.name}"
                
                self.env["log.line"].sudo().create({
                    "operator_id": operator_orm.id if operator_orm else False,
                    "qty": move.quantity,
                    "message": log_msg,
                    "bin_log_id": bin_log.id
                })

            log_vals = {
                "log": f"{log_label} movido a BIN {bin_storage.name} por {operator_name}",
                "user": operator_orm.id if operator_orm else False,
            }
            log_vals.update(log_target)
            self.env["wmds.log"].sudo().create(log_vals)

        if orders:
            for so_custom_name in orders:
                ei_tag = self.env["sale.order.ei"].sudo().search([
                    ('display_name_custom', '=', so_custom_name)
                ], limit=1)

                is_new = False
                if not ei_tag and '/' in so_custom_name:
                    parts = so_custom_name.split('/')
                    if len(parts) == 2:
                        so_name, seq_str = parts
                        so = self.env['sale.order'].sudo().search([('name', '=', so_name)], limit=1)
                        if so:
                            try:
                                seq = int(seq_str)
                                if 0 < seq <= so.ei_total:
                                    ei_tag = self.env["sale.order.ei"].sudo().create({
                                        'so_id': so.id,
                                        'sequence_number': seq
                                    })
                                    is_new = True
                            except ValueError:
                                pass

                if ei_tag:
                    if not is_new and ei_tag.write_date and self.date_created and ei_tag.write_date > self.date_created:
                        _logger.info(f"Skipping stale move_to_bin for package {so_custom_name} (task date_created: {self.date_created}, write_date: {ei_tag.write_date})")
                        continue
                    ei_tag.write({
                        'on_bin': True,
                        'bin_id': bin_storage.id,
                        'on_dock': False,
                        'dock_id': False,
                        'dispatched': False
                    })
                    
                    log_msg = f"El operador {operator_name} puso el paquete {so_custom_name} en el bin {bin_storage.name}"

                    self.env["log.line"].sudo().create({
                        "operator_id": operator_orm.id if operator_orm else False,
                        "qty": 1,
                        "message": log_msg,
                        "bin_log_id": bin_log.id
                    })

                    if ei_tag.so_id:
                        picking = self.env['stock.picking'].sudo().search([
                            ('sale_id', '=', ei_tag.so_id.id),
                            ('state', 'in', ['assigned', 'done']),
                            ('picking_type_id.name', 'ilike', 'Pick')
                        ], order='date_done desc', limit=1)
                        
                        if picking:
                            self.env["wmds.log"].sudo().create({
                                "pick": picking.id,
                                "log": log_msg,
                                "user": operator_orm.id if operator_orm else False,
                            })
                        else:
                            self.env["wmds.log"].sudo().create({
                                "sale": ei_tag.so_id.id,
                                "log": log_msg,
                                "user": operator_orm.id if operator_orm else False,
                            })

    def _execute_move_to_dock(self, params):
        bin_name = params.get("bin")
        dock_name = params.get("dock")
        operator_login = params.get("operator")
        selected_packages = params.get("selected_packages", [])

        operator_orm = self.env["res.users"].sudo().search([('login', '=', operator_login)], limit=1)
        bin_storage = self.env["bin.storage"].sudo().search([('name', '=', bin_name)], limit=1)
        dock_storage = self.env["dock.storage"].sudo().search([('name', '=', dock_name)], limit=1)

        if not dock_storage or not bin_storage:
            raise UserError("Bin o Dock no existe")

        ei_domain = [('bin_id', '=', bin_storage.id), ('on_bin', '=', True)]
        move_domain = [('bin_id', '=', bin_storage.id), ('on_bin', '=', True)]

        if selected_packages:
            ei_names = [p['name'] for p in selected_packages if not p.get('is_full')]
            move_ids = [p['move_id'] for p in selected_packages if p.get('is_full')]
            
            if ei_names:
                ei_domain.append(('display_name_custom', 'in', ei_names))
            else:
                ei_domain.append(('id', '=', 0))

            if move_ids:
                move_domain.append(('id', 'in', move_ids))
            else:
                move_domain.append(('id', '=', 0))

        dock_log = self.env["dock.log"].sudo().search([
            ('dock_id', '=', dock_storage.id), 
            ('bin_id', '=', bin_storage.id)
        ], limit=1)

        if not dock_log:
            dock_log = self.env["dock.log"].sudo().create({
                'dock_id': dock_storage.id,
                'bin_id': bin_storage.id
            })

        operator_name = operator_orm.name if operator_orm else "Desconocido"

        ei_tags = self.env["sale.order.ei"].sudo().search(ei_domain)
        for tag in ei_tags:
            if tag.write_date and self.date_created and tag.write_date > self.date_created:
                _logger.info(f"Skipping stale move_to_dock for package {tag.display_name_custom} (task date_created: {self.date_created}, write_date: {tag.write_date})")
                continue
            tag.on_bin = False
            tag.bin_id = False
            tag.on_dock = True
            tag.dock_id = dock_storage.id

            log_msg = f"El operador {operator_name} movió el paquete {tag.display_name_custom} del {bin_storage.name} al DOCK {dock_storage.name}"

            self.env["log.line"].sudo().create({
                "operator_id": operator_orm.id if operator_orm else False,
                "qty": 1,
                "message": log_msg,
                "dock_log_id": dock_log.id
            })

            if tag.so_id:
                picking = self.env['stock.picking'].sudo().search([
                    ('sale_id', '=', tag.so_id.id),
                    ('state', 'in', ['assigned', 'done']),
                    ('picking_type_id.name', 'ilike', 'Pick')
                ], order='date_done desc', limit=1)
                
                if picking:
                    self.env["wmds.log"].sudo().create({
                        "pick": picking.id,
                        "log": log_msg,
                        "user": operator_orm.id if operator_orm else False,
                    })
                else:
                    self.env["wmds.log"].sudo().create({
                        "sale": tag.so_id.id,
                        "log": log_msg,
                        "user": operator_orm.id if operator_orm else False,
                    })

        moves = self.env["stock.move"].sudo().search(move_domain)
        processed_pickings = self.env['stock.picking']
        processed_batches = self.env['stock.picking.batch']

        for move in moves:
            if move.write_date and self.date_created and move.write_date > self.date_created:
                _logger.info(f"Skipping stale move_to_dock for move {move.id} (task date_created: {self.date_created}, write_date: {move.write_date})")
                continue
            move.on_bin = False
            move.bin_id = False
            move.on_dock = True
            move.dock_id = dock_storage.id

            log_msg = f"El operador {operator_name} movió el producto {move.product_id.display_name} del {bin_storage.name} al DOCK {dock_storage.name}"

            self.env["log.line"].sudo().create({
                "operator_id": operator_orm.id if operator_orm else False,
                "qty": move.quantity,
                "message": log_msg,
                "dock_log_id": dock_log.id
            })
            
            if move.picking_id:
                processed_pickings |= move.picking_id
                if move.picking_id.batch_id:
                    processed_batches |= move.picking_id.batch_id

        for batch in processed_batches:
            self.env["wmds.log"].sudo().create({
                "batch_pick": batch.id,
                "log": f"Lote {batch.name} movido a DOCK {dock_storage.name} por {operator_name}",
                "user": operator_orm.id if operator_orm else False,
            })

        for picking in processed_pickings:
            if not picking.batch_id:
                self.env["wmds.log"].sudo().create({
                    "pick": picking.id,
                    "log": f"Traslado {picking.name} movido a DOCK {dock_storage.name} por {operator_name}",
                    "user": operator_orm.id if operator_orm else False,
                })

        # Verificar si el BIN quedó vacío para liberarlo
        has_remaining = self.env["sale.order.ei"].sudo().search_count([('bin_id', '=', bin_storage.id), ('on_bin', '=', True)]) > 0 or \
                        self.env["stock.move"].sudo().search_count([('bin_id', '=', bin_storage.id), ('on_bin', '=', True)]) > 0
        
        if not has_remaining:
            bin_storage.write({
                'state': 'available',
                'carrier_id': False,
            })

    def _execute_dispatch_package(self, params):
        packs_ids = params.get("picks_ids", [])
        operator_login = params.get("operator_login")

        operator = self.env["res.users"].sudo().search([('login', '=', operator_login)], limit=1)
        user_id = operator.id if operator else self.env.user.id

        # 1. Búsqueda masiva inicial para eliminar latencia de base de datos
        ei_tags = self.env["sale.order.ei"].sudo().search([
            ('display_name_custom', 'in', packs_ids)
        ])
        tag_by_name = {t.display_name_custom: t for t in ei_tags}

        errors = []
        success_packs = []
        
        for pack_id in packs_ids:
            # Obtener de forma instantánea en memoria sin hacer query
            tag = tag_by_name.get(pack_id)

            if not tag:
                errors.append(f"Paquete {pack_id}: No se encontró la etiqueta sale.order.ei en el sistema.")
                continue

            if tag.write_date and self.date_created and tag.write_date > self.date_created:
                _logger.info(f"Skipping stale dispatch for package {tag.display_name_custom} (task date_created: {self.date_created}, write_date: {tag.write_date})")
                success_packs.append(f"Paquete {pack_id} (Omitido: write_date posterior a la creación de la tarea)")
                continue

            if tag.dispatched:
                _logger.info(f"Package {tag.display_name_custom} is already dispatched. Skipping.")
                success_packs.append(f"Paquete {pack_id} (Omitido: Ya despachado previamente)")
                continue

            so = tag.so_id
            if so and so.state == 'cancel':
                errors.append(f"Paquete {pack_id}: No se puede despachar porque el pedido {so.name} está cancelado.")
                continue

            try:
                # 2. Solo iniciamos savepoint y transacción para los paquetes que realmente requieren despacho
                with self.env.cr.savepoint():
                    tag.write({
                        'dispatched': True,
                        'on_dock': False,
                        'dock_id': False
                    })
                    
                    log_msg = f"Paquete {tag.display_name_custom} entregado a paquetería por {operator_login}."
                    
                    picking = self.env['stock.picking'].sudo().search([
                        ('sale_id', '=', so.id) if so else ('id', '=', False),
                        ('state', 'in', ['assigned', 'done']),
                        ('picking_type_id.name', 'ilike', 'Pick')
                    ], order='date_done desc', limit=1)
                    
                    if picking:
                        self.env["wmds.log"].sudo().create({
                            "pick": picking.id,
                            "log": log_msg,
                            "user": user_id,
                        })
                    elif so:
                        self.env['wmds.log'].sudo().create({
                            'sale': so.id,
                            'log': log_msg,
                            'user': user_id,
                            'date': fields.Datetime.now(),
                        })

                    if so:
                        pending_out_pickings = self.env['stock.picking'].sudo().search([
                            ('sale_id', '=', so.id),
                            '|',
                            ('picking_type_id.code', '=', 'outgoing'),
                            ('picking_type_id.name', 'in', ['Órdenes de entrega', 'Delivery Orders']),
                            ('state', 'not in', ['done', 'cancel'])
                        ])
                        
                        if pending_out_pickings:
                            total_ei = so.ei_total
                            dispatched_ei_count = self.env['sale.order.ei'].sudo().search_count([
                                ('so_id', '=', so.id),
                                ('dispatched', '=', True)
                            ])
                            
                            if dispatched_ei_count >= total_ei:
                                for picking_out in pending_out_pickings:
                                    picking_out.action_assign()
                                    
                                    for move in picking_out.move_ids:
                                        if move.state not in ('done', 'cancel'):
                                            move.write({
                                                'quantity': move.product_uom_qty,
                                                'picked': True
                                            })
                                    
                                    res = picking_out.button_validate()
                                    if isinstance(res, dict) and res.get('res_model') == 'stock.backorder.confirmation':
                                        wizard = self.env['stock.backorder.confirmation'].with_context(res['context']).sudo().create({
                                            'pick_ids': [(4, picking_out.id)]
                                        })
                                        wizard.process()
                                    _logger.info(f"Picking OUT {picking_out.name} validado con éxito en segundo plano.")
                            else:
                                _logger.info(f"Faltan de despachar etiquetas para SO {so.name} ({dispatched_ei_count}/{total_ei}).")
                        else:
                            _logger.info(f"No hay pickings OUT pendientes para SO {so.name}. Se salta la validación.")

                # Commit de la transacción de este paquete individual exitoso
                self.env.cr.commit()
                success_packs.append(f"Paquete {pack_id} (Procesado con éxito)")

            except Exception as e:
                err_msg = f"Paquete {pack_id}: Error procesando despacho - {str(e)}"
                _logger.error(f"{err_msg}\n{traceback.format_exc()}")
                errors.append(err_msg)

        # Si hubo errores, consolidamos el reporte final para la UI y lanzamos error para habilitar reintento
        if errors:
            summary = []
            summary.append("=== RESUMEN DE PROCESAMIENTO CON ERRORES ===")
            summary.append("Nota: El procesamiento continuó con los demás paquetes del lote a pesar de las fallas individuales.")
            summary.append(f"\nPaquetes procesados con éxito/omitidos: {len(success_packs)}")
            for s in success_packs:
                summary.append(f" - {s}")
            summary.append(f"\nPaquetes fallidos: {len(errors)}")
            for err in errors:
                summary.append(f" - {err}")
            
            raise UserError("\n".join(summary))

    @api.model
    def cleanup_old_tasks(self):
        """Deletes queued tasks older than 15 days."""
        from datetime import datetime, timedelta
        limit_date = datetime.now() - timedelta(days=15)
        old_tasks = self.search([
            ('date_created', '<', limit_date),
            ('status', 'in', ['completed', 'failed'])
        ])
        _logger.info(f"Removing {len(old_tasks)} queued tasks older than 15 days")
        old_tasks.unlink()
