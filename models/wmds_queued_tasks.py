# -*- coding: utf-8 -*-
from odoo import models, fields, api, SUPERUSER_ID
from odoo.exceptions import UserError
import json
import logging
import traceback
from collections import deque

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
        ('completed_with_errors', 'Completed with Errors'),
        ('failed', 'Failed')
    ], string='Status', default='pending', required=True, index=True)
    error_message = fields.Text(string='Error Message')
    info_message = fields.Text(string='Info Log')

    def action_retry(self):
        """Retries the queued task"""
        self.ensure_one()
        self.write({
            'status': 'pending',
            'error_message': False,
            'info_message': False,
            'date_processed': False
        })
        # Process asynchronously immediately
        self._trigger_async_process()
        return True

    def action_stop(self):
        """Manually stops a running or pending queued task by setting it to completed_with_errors"""
        self.ensure_one()
        if self.status in ('running', 'pending'):
            self.write({
                'status': 'completed_with_errors',
                'error_message': 'Detenido manualmente por el operador.',
                'date_processed': fields.Datetime.now()
            })
        return True

    def action_retry_all_failed(self):
        """Retries all failed or completed_with_errors tasks"""
        tasks_to_retry = self.search([('status', 'in', ['failed', 'completed_with_errors'])])
        if tasks_to_retry:
            tasks_to_retry.write({
                'status': 'pending',
                'error_message': False,
                'info_message': False,
                'date_processed': False
            })
            tasks_to_retry[0]._trigger_async_process()
        return True

    def action_stop_all_running(self):
        """Stops all running or pending tasks"""
        tasks_to_stop = self.search([('status', 'in', ['running', 'pending'])])
        if tasks_to_stop:
            tasks_to_stop.write({
                'status': 'completed_with_errors',
                'error_message': 'Detenido manualmente por el operador.',
                'date_processed': fields.Datetime.now()
            })
        return True

    def _trigger_async_process(self):
        """Schedules the queue processor to run ASAP in the cron worker.

        Antes esto lanzaba un threading.Thread DENTRO del worker HTTP, de modo que
        el despacho pesado corría en el espacio de memoria de ese worker y su RSS
        contaba contra el límite de memoria por worker de Odoo.sh (limit_memory_hard),
        provocando que el worker fuera terminado con SIGKILL (signal 9) en lotes grandes.

        En su lugar, disparamos el cron dedicado (_trigger), que ejecuta el mismo
        procesador '_process_tasks_thread' en el worker de cron —con su propio ciclo de
        vida y presupuesto de memoria—. El cron ya corre cada minuto como respaldo; este
        disparo hace que arranque de inmediato en la siguiente pasada del cron.
        """
        self.env.ref('wmds.ir_cron_process_wmds_queued_tasks').sudo()._trigger()

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

                # Acquiring the lock guarantees no other processor is alive.
                # Any task still in 'running' is an orphan from a dead thread — reset it so
                # the queue below picks it up and retries. _execute_dispatch_package skips
                # already-dispatched packages, making the retry fully idempotent.
                orphaned = env['wmds.queued_tasks'].search([('status', '=', 'running')])
                if orphaned:
                    _logger.warning(
                        "wmds.queued_tasks: %d tarea(s) huérfana(s) en estado 'running' detectadas. "
                        "Reiniciando a 'pending' para reintento automático.",
                        len(orphaned)
                    )
                    for task in orphaned:
                        task.write({
                            'status': 'pending',
                            'info_message': (task.info_message or '') +
                                '\n\n[AUTO-RECOVERY] Hilo de proceso anterior terminó de forma inesperada. '
                                'Tarea reiniciada automáticamente; los paquetes ya despachados serán omitidos.',
                        })
                    cr.commit()

                # Find any pending tasks (includes tasks just recovered above)
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
                self.write({'info_message': "Iniciando movimiento a bin..."})
                self.env.cr.commit()
                self._execute_move_to_bin(params)
                self.write({
                    'status': 'completed',
                    'date_processed': fields.Datetime.now(),
                    'error_message': False,
                    'info_message': "Movimiento a bin completado con éxito."
                })
            elif self.task_type == 'move_to_dock':
                self.write({'info_message': "Iniciando movimiento a dock..."})
                self.env.cr.commit()
                self._execute_move_to_dock(params)
                self.write({
                    'status': 'completed',
                    'date_processed': fields.Datetime.now(),
                    'error_message': False,
                    'info_message': "Movimiento a dock completado con éxito."
                })
            elif self.task_type == 'dispatch_package':
                has_errors, error_summary = self._execute_dispatch_package(params)
                if has_errors:
                    self.write({
                        'status': 'completed_with_errors',
                        'date_processed': fields.Datetime.now(),
                        'error_message': error_summary
                    })
                else:
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

            # Auto-close PACK pickings for wholesale orders
            for picking in pickings:
                if picking.sale_id and picking.sale_id.data_is_wholesale_sale:
                    pack_pickings = self.env['stock.picking'].sudo().search([
                        ('sale_id', '=', picking.sale_id.id),
                        ('picking_type_id.name', 'ilike', 'Pack'),
                        ('state', 'not in', ['done', 'cancel'])
                    ])
                    for pack_pick in pack_pickings:
                        try:
                            pack_pick.action_assign()
                            for move in pack_pick.move_ids:
                                if move.state not in ('done', 'cancel'):
                                    move.write({
                                        'quantity': move.product_uom_qty,
                                        'picked': True
                                    })
                            res = pack_pick.button_validate()
                            if isinstance(res, dict) and res.get('res_model') == 'stock.backorder.confirmation':
                                wizard = self.env['stock.backorder.confirmation'].with_context(res['context']).sudo().create({
                                    'pick_ids': [(4, pack_pick.id)]
                                })
                                wizard.process()
                            _logger.info(f"Auto-validated wholesale PACK picking {pack_pick.name} for SO {picking.sale_id.name}")
                        except Exception as pe:
                            _logger.error(f"Error auto-validating wholesale PACK picking {pack_pick.name}: {pe}")

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

    def _update_progress(self, progress_msg):
        self.write({
            'status': 'running',
            'info_message': progress_msg
        })
        self.env.cr.commit()

    def _execute_dispatch_package(self, params):
        packs_ids = params.get("picks_ids", [])
        operator_login = params.get("operator_login")

        operator = self.env["res.users"].sudo().search([('login', '=', operator_login)], limit=1)
        user_id = operator.id if operator else self.env.user.id

        total_packs = len(packs_ids)
        # Asegurar estado running y mensaje inicial dinámico en la UI
        self.write({
            'status': 'running',
            'info_message': f"Iniciando procesamiento de {total_packs} paquetes por {operator_login}..."
        })
        self.env.cr.commit()

        # 1. Búsqueda masiva inicial para eliminar latencia de base de datos
        ei_tags = self.env["sale.order.ei"].sudo().search([
            ('display_name_custom', 'in', packs_ids)
        ])
        tag_by_name = {t.display_name_custom: t for t in ei_tags}

        # SO IDs presentes en este lote; usados por H-3 y H-5
        all_so_ids = list({t.so_id.id for t in ei_tags if t.so_id})

        # H-3: Búsqueda masiva de pickings PICK para todos los SOs del lote.
        # Una sola consulta reemplaza la búsqueda individual por paquete dentro del savepoint.
        so_pick_picking = {}
        if all_so_ids:
            pick_pickings = self.env['stock.picking'].sudo().search([
                ('sale_id', 'in', all_so_ids),
                ('state', 'in', ['assigned', 'done']),
                ('picking_type_id.name', 'ilike', 'Pick')
            ], order='date_done desc')
            for p in pick_pickings:
                sid = p.sale_id.id
                if sid not in so_pick_picking:
                    so_pick_picking[sid] = p

        # H-5: Conteo de EI despachadas por SO; sustituye el search_count por paquete.
        # read_group emite un único GROUP BY en vez de N COUNT(*) individuales.
        so_dispatched_count = {}
        if all_so_ids:
            count_data = self.env['sale.order.ei'].sudo().read_group(
                [('so_id', 'in', all_so_ids), ('dispatched', '=', True)],
                ['so_id'],
                ['so_id']
            )
            so_dispatched_count = {d['so_id'][0]: d['so_id_count'] for d in count_data}

        errors = []
        success_packs = []
        so_out_closed = {}       # Caché en memoria para almacenar si el OUT de una Sale Order ya está cerrado
        so_pending_pickings = {} # H-2: recordset OUT pendiente por SO, evita re-búsqueda dentro del savepoint
        so_ei_total = {}         # H-4: ei_total por SO; sobrevive a invalidate_all() al ser un dict Python plano
        # H-7: ventana deslizante acotada para el detalle de ejecución.
        # Antes log_lines era una lista sin límite y cada actualización de progreso
        # re-unía TODAS las líneas acumuladas ("\n".join) escribiéndolas en la BD cada
        # 10 paquetes: coste O(n²) en memoria y CPU que en lotes grandes contribuía al
        # agotamiento de memoria del worker. Con deque(maxlen=...) sólo se conservan las
        # últimas MAX_DETAIL_LINES; append/len/join siguen funcionando igual.
        MAX_DETAIL_LINES = 200
        log_lines = deque(maxlen=MAX_DETAIL_LINES)
        PROGRESS_INTERVAL = 10   # H-1: número de paquetes entre cada escritura de progreso a la BD
        
        for idx, pack_id in enumerate(packs_ids):
            now_str = fields.Datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # Obtener de forma instantánea en memoria sin hacer query
            tag = tag_by_name.get(pack_id)

            if not tag:
                err_msg = f"Paquete {pack_id}: No se encontró la etiqueta sale.order.ei en el sistema."
                errors.append(err_msg)
                log_lines.append(f"[{now_str}] {err_msg}")
                if (idx + 1) % PROGRESS_INTERVAL == 0 or idx == total_packs - 1:
                    self._update_progress(
                        f"Procesando lote de despachos...\n"
                        f"Progreso: {idx + 1} / {total_packs} paquetes.\n"
                        f" - Exitosos/Omitidos: {len(success_packs)}\n"
                        f" - Fallidos: {len(errors)}\n\n"
                        f"=== DETALLE DE EJECUCIÓN ===\n" +
                        "\n".join(log_lines)
                    )
                continue



            tag_dispatch_status = getattr(tag, 'dispatch_status', 'pending')
            if tag_dispatch_status == 'success' or tag.dispatched:
                # Si ya está despachado pero el subestado no estaba en success, lo actualizamos para coherencia
                if tag_dispatch_status != 'success':
                    try:
                        with self.env.cr.savepoint():
                            if 'dispatch_status' in tag._fields:
                                tag.write({'dispatch_status': 'success'})
                        self.env.cr.commit()
                    except Exception as write_err:
                        _logger.error(f"Error saving success status on already dispatched tag {pack_id}: {write_err}")
                _logger.info(f"Package {tag.display_name_custom} is already successfully dispatched. Skipping.")
                success_packs.append(f"Paquete {pack_id} (Omitido: Ya despachado)")
                log_lines.append(f"[{now_str}] Paquete {pack_id}: Omitido - Ya se encontraba despachado anteriormente.")
                if (idx + 1) % PROGRESS_INTERVAL == 0 or idx == total_packs - 1:
                    self._update_progress(
                        f"Procesando lote de despachos...\n"
                        f"Progreso: {idx + 1} / {total_packs} paquetes.\n"
                        f" - Exitosos/Omitidos: {len(success_packs)}\n"
                        f" - Fallidos: {len(errors)}\n\n"
                        f"=== DETALLE DE EJECUCIÓN ===\n" +
                        "\n".join(log_lines)
                    )
                continue

            so = tag.so_id
            if so and so.state == 'cancel':
                warn_msg = f"Paquete {pack_id}: No se puede despachar porque el pedido {so.name} está cancelado."
                success_packs.append(f"Paquete {pack_id} (Omitido: Pedido Cancelado)")
                log_lines.append(f"[{now_str}] ADVERTENCIA: {warn_msg}")
                try:
                    with self.env.cr.savepoint():
                        if 'dispatch_status' in tag._fields:
                            tag.write({'dispatch_status': 'failed'})
                    self.env.cr.commit()
                except Exception as write_err:
                    _logger.error(f"Error saving failed status for cancelled order tag {pack_id}: {write_err}")
                if (idx + 1) % PROGRESS_INTERVAL == 0 or idx == total_packs - 1:
                    self._update_progress(
                        f"Procesando lote de despachos...\n"
                        f"Progreso: {idx + 1} / {total_packs} paquetes.\n"
                        f" - Exitosos/Omitidos: {len(success_packs)}\n"
                        f" - Fallidos: {len(errors)}\n\n"
                        f"=== DETALLE DE EJECUCIÓN ===\n" +
                        "\n".join(log_lines)
                    )
                continue

            # 2. Optimización rápida: Si el OUT de la SO ya está cerrado, marcar y continuar inmediatamente
            if so:
                if so.id not in so_out_closed:
                    # Buscar en base de datos únicamente la primera vez para esta Sale Order
                    pending_out_pickings = self.env['stock.picking'].sudo().search([
                        ('sale_id', '=', so.id),
                        '|',
                        ('picking_type_id.code', '=', 'outgoing'),
                        ('picking_type_id.name', 'in', ['Órdenes de entrega', 'Delivery Orders']),
                        ('state', 'not in', ['done', 'cancel'])
                    ])
                    # Si no hay pickings de salida pendientes, el OUT ya está cerrado
                    so_out_closed[so.id] = not bool(pending_out_pickings)
                    so_pending_pickings[so.id] = pending_out_pickings  # H-2: cachear para reutilizar dentro del savepoint

                if so_out_closed[so.id]:
                    # Marcar etiqueta como despachada de forma directa y rápida (sin logs ni validaciones de stock)
                    try:
                        with self.env.cr.savepoint():
                            vals = {
                                'dispatched': True,
                                'on_dock': False,
                                'dock_id': False,
                            }
                            if 'dispatch_status' in tag._fields:
                                vals['dispatch_status'] = 'success'
                            tag.write(vals)
                        self.env.cr.commit()
                        success_packs.append(f"Paquete {pack_id} (Procesado rápido - OUT ya cerrado)")
                        log_lines.append(f"[{now_str}] Paquete {pack_id}: Procesado (rápido) - La orden de entrega (OUT) ya estaba cerrada/entregada.")
                    except Exception as e:
                        err_msg = f"Paquete {pack_id}: Error procesando despacho rápido - {str(e)}"
                        _logger.error(f"{err_msg}\n{traceback.format_exc()}")
                        errors.append(err_msg)
                        log_lines.append(f"[{now_str}] Paquete {pack_id}: ERROR en procesamiento rápido - {str(e)}")
                        try:
                            with self.env.cr.savepoint():
                                if 'dispatch_status' in tag._fields:
                                    tag.write({'dispatch_status': 'failed'})
                            self.env.cr.commit()
                        except Exception as write_err:
                            _logger.error(f"Error saving failed status on rapid dispatch tag {pack_id}: {write_err}")
                    if (idx + 1) % PROGRESS_INTERVAL == 0 or idx == total_packs - 1:
                        self._update_progress(
                            f"Procesando lote de despachos...\n"
                            f"Progreso: {idx + 1} / {total_packs} paquetes.\n"
                            f" - Exitosos/Omitidos: {len(success_packs)}\n"
                            f" - Fallidos: {len(errors)}\n\n"
                            f"=== DETALLE DE EJECUCIÓN ===\n" +
                            "\n".join(log_lines)
                        )
                    continue

            try:
                # 3. Solo iniciamos savepoint y transacción para los paquetes que realmente requieren despacho y tienen OUT pendiente
                with self.env.cr.savepoint():
                    vals = {
                        'dispatched': True,
                        'on_dock': False,
                        'dock_id': False,
                    }
                    if 'dispatch_status' in tag._fields:
                        vals['dispatch_status'] = 'success'
                    tag.write(vals)
                    
                    log_msg = f"Paquete {tag.display_name_custom} entregado a paquetería por {operator_login}."

                    # H-3: lookup en memoria en vez de búsqueda individual por paquete
                    picking = so_pick_picking.get(so.id) if so else None

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
                        # H-2: reutilizar el recordset capturado antes del savepoint
                        pending_out_pickings = so_pending_pickings.get(so.id, self.env['stock.picking'])

                        if pending_out_pickings:
                            if so.id not in so_ei_total:
                                # H-4: cachear ei_total; _compute_ei_total dispara 1-2 búsquedas en stock.picking
                                so_ei_total[so.id] = so.ei_total
                            total_ei = so_ei_total[so.id]
                            # H-5: +1 incluye la etiqueta actual ya escrita en el savepoint
                            new_dispatched_count = so_dispatched_count.get(so.id, 0) + 1
                            if new_dispatched_count >= total_ei:
                                for picking_out in pending_out_pickings:
                                    # H-6: suprimir logs de wmds durante la validación masiva
                                    picking_out.with_context(wmds_dispatch_in_progress=True).action_assign()

                                    for move in picking_out.move_ids:
                                        if move.state not in ('done', 'cancel'):
                                            move.with_context(wmds_dispatch_in_progress=True).write({
                                                'quantity': move.product_uom_qty,
                                                'picked': True
                                            })

                                    res = picking_out.with_context(wmds_dispatch_in_progress=True).button_validate()
                                    if isinstance(res, dict) and res.get('res_model') == 'stock.backorder.confirmation':
                                        wizard = self.env['stock.backorder.confirmation'].with_context(res['context']).sudo().create({
                                            'pick_ids': [(4, picking_out.id)]
                                        })
                                        wizard.process()
                                    _logger.info(f"Picking OUT {picking_out.name} validado con éxito en segundo plano.")
                                # Si acabamos de validar con éxito todos los pickings OUT, actualizamos la caché
                                so_out_closed[so.id] = True
                            else:
                                _logger.info(f"Faltan de despachar etiquetas para SO {so.name} ({new_dispatched_count}/{total_ei}).")
                        else:
                            _logger.info(f"No hay pickings OUT pendientes para SO {so.name}. Se salta la validación.")
                            so_out_closed[so.id] = True

                # Commit de la transacción de este paquete individual exitoso
                self.env.cr.commit()
                success_packs.append(f"Paquete {pack_id} (Procesado con éxito)")
                log_lines.append(f"[{now_str}] Paquete {pack_id}: Despachado y validado con éxito.")
                # H-5: commit confirmado — persistir el incremento en el contador en memoria
                if so:
                    so_dispatched_count[so.id] = so_dispatched_count.get(so.id, 0) + 1

            except Exception as e:
                err_detail = str(e) or repr(e)
                err_msg = f"Paquete {pack_id}: Error procesando despacho - {err_detail}"
                _logger.error(f"{err_msg}\n{traceback.format_exc()}")
                errors.append(err_msg)
                log_lines.append(f"[{now_str}] Paquete {pack_id}: ERROR - {err_detail}")
                # Escribir estado 'failed' para esta EI en su propia transacción y hacer commit
                try:
                    with self.env.cr.savepoint():
                        if 'dispatch_status' in tag._fields:
                            tag.write({'dispatch_status': 'failed'})
                    self.env.cr.commit()
                except Exception as write_err:
                    _logger.error(f"Error saving failed status on tag {pack_id}: {write_err}")

                if isinstance(e, MemoryError):
                    _logger.error("MemoryError detectado. Límite de memoria excedido. Se aborta la ejecución de la tarea.")
                    log_lines.append(f"[{now_str}] ERROR CRÍTICO: Límite de memoria excedido (MemoryError). Se detiene el procesamiento de los paquetes restantes para evitar inestabilidad del sistema.")
                    self.env.invalidate_all()
                    break

            if (idx + 1) % PROGRESS_INTERVAL == 0 or idx == total_packs - 1:
                self._update_progress(
                    f"Procesando lote de despachos...\n"
                    f"Progreso: {idx + 1} / {total_packs} paquetes.\n"
                    f" - Exitosos/Omitidos: {len(success_packs)}\n"
                    f" - Fallidos: {len(errors)}\n\n"
                    f"=== DETALLE DE EJECUCIÓN ===\n" +
                    "\n".join(log_lines)
                )

            # Invalida el caché de Odoo en cada iteración para liberar memoria y evitar MemoryError
            self.env.invalidate_all()

        # Escribir el log final consolidado
        final_msg = (
            f"Procesamiento finalizado.\n"
            f"Total: {total_packs} paquetes.\n"
            f" - Exitosos/Omitidos: {len(success_packs)}\n"
            f" - Fallidos: {len(errors)}\n\n"
            f"=== DETALLE DE EJECUCIÓN ===\n" +
            "\n".join(log_lines)
        )
        self.write({'info_message': final_msg})
        self.env.cr.commit()

        # Si hubo errores, consolidamos el reporte final para la UI
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
            
            return True, "\n".join(summary)

        return False, ""

    @api.model
    def cleanup_old_tasks(self):
        """Deletes queued tasks older than 15 days."""
        from datetime import datetime, timedelta
        limit_date = datetime.now() - timedelta(days=15)
        old_tasks = self.search([
            ('date_created', '<', limit_date),
            ('status', 'in', ['completed', 'completed_with_errors'])
        ])
        _logger.info(f"Removing {len(old_tasks)} queued tasks older than 15 days")
        old_tasks.unlink()
