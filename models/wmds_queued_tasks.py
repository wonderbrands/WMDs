# -*- coding: utf-8 -*-
from odoo import models, fields, api, SUPERUSER_ID
from odoo.exceptions import UserError
import json
import logging
import re
import traceback
from collections import deque

_logger = logging.getLogger(__name__)

class WmdsQueuedTasks(models.Model):
    _name = 'wmds.queued_tasks'
    _description = 'WMDs Queued Tasks'
    _order = 'id desc'

    # Solo los despachos se encolan. move_to_bin/move_to_dock se conservan para el
    # historial y para vaciar tareas creadas antes de que esos traslados pasaran a
    # ejecutarse al momento (ver bin_dock_operations.py).
    task_type = fields.Selection([
        ('move_to_bin', 'Move to Bin (legacy)'),
        ('move_to_dock', 'Move to Dock (legacy)'),
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

    @api.model
    def _normalize_barcode(self, raw):
        """Normaliza códigos de barras escaneados corrigiendo anomalías conocidas:
        - Invertidos por buffer de escáner (terminan en OS, ej: 1/68849301OS -> SO10394886/1)
        - Falta de prefijo S inicial (ej: O10390927/1 -> SO10390927/1)
        - Letra espuria al final por rebote de tecla (ej: SO10386370/1Q -> SO10386370/1)
        """
        if not raw or not isinstance(raw, str):
            return raw
        val = raw.strip()
        if val.endswith('OS'):
            val = val[::-1]
        elif val.startswith('O10') and '/' in val:
            val = 'S' + val
        m = re.match(r'^(SO\d+/\d+)[A-Za-z]$', val)
        if m:
            val = m.group(1)
        return val

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
            if self.task_type in ('move_to_bin', 'move_to_dock'):
                self._execute_legacy_bin_dock(params)
                self.write({
                    'status': 'completed',
                    'date_processed': fields.Datetime.now(),
                    'error_message': False,
                    'info_message': "Traslado completado con éxito."
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

    def _execute_legacy_bin_dock(self, params):
        """Vacía tareas move_to_bin/move_to_dock encoladas antes de que estos traslados
        pasaran a ejecutarse al momento. Ya no se crean tareas nuevas de estos tipos."""
        bin_storage = self.env["bin.storage"].sudo().search([('name', '=', params.get("bin"))], limit=1)
        if not bin_storage:
            raise UserError(f"Bin {params.get('bin')} no encontrado")
        if self.task_type == 'move_to_bin':
            bin_storage._wmds_move_to_bin(
                params.get("operator"),
                orders=params.get("orders"),
                batch_id=params.get("batch_id"),
                pick_id=params.get("pick_id"),
                carrier_id=params.get("carrier_id"),
            )
        else:
            dock_storage = self.env["dock.storage"].sudo().search([('name', '=', params.get("dock"))], limit=1)
            if not dock_storage:
                raise UserError("Bin o Dock no existe")
            bin_storage._wmds_move_to_dock(dock_storage, params.get("operator"), params.get("selected_packages", []))

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

        # Normalización preventiva de códigos escaneados
        normalized_packs_ids = [self._normalize_barcode(p) for p in packs_ids]
        lookup_keys = list(set(packs_ids + normalized_packs_ids))

        # 1. Búsqueda masiva inicial para eliminar latencia de base de datos
        ei_tags = self.env["sale.order.ei"].sudo().search([
            ('display_name_custom', 'in', lookup_keys)
        ])
        tag_by_name = {t.display_name_custom: t for t in ei_tags}

        # Punto de extensión: EI que un complemento resuelve antes del bucle. Las que quedan
        # 'dispatched' se omiten en el bucle como ya despachadas.
        special_log = []
        special_errors = []
        try:
            special = ei_tags._wmds_dispatch_handle(operator=operator)
            if special['consumed']:
                if special['handled'] and 'dispatch_status' in self.env['sale.order.ei']._fields:
                    special['handled'].write({'dispatch_status': 'success'})
                self.env.cr.commit()
            special_log += special['log']
            special_errors += special['errors']
        except Exception as e:
            self.env.cr.rollback()
            _logger.error(f"Error en complementos antes del despacho: {e}\n{traceback.format_exc()}")
            special_errors.append(f"Error en complementos antes del despacho: {e}")

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

        errors = list(special_errors)
        success_packs = []
        so_out_closed = {}       # Caché en memoria para almacenar si el OUT de una Sale Order ya está cerrado
        so_pending_pickings = {} # H-2: recordset OUT pendiente por SO, evita re-búsqueda dentro del savepoint
        so_ei_total = {}         # H-4: ei_total por SO; sobrevive a invalidate_all() al ser un dict Python plano
        # H-7: ventana deslizante acotada para el detalle de ejecución.
        MAX_DETAIL_LINES = 200
        log_lines = deque(maxlen=MAX_DETAIL_LINES)
        PROGRESS_INTERVAL = 10   # H-1: número de paquetes entre cada escritura de progreso a la BD
        
        for idx, pack_id_raw in enumerate(packs_ids):
            now_str = fields.Datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            pack_id = self._normalize_barcode(pack_id_raw)

            # Obtener de forma instantánea en memoria
            tag = tag_by_name.get(pack_id) or tag_by_name.get(pack_id_raw)

            # Si no existe la etiqueta en DB, pero corresponde a una orden de venta real (ej. se saltaron BIN):
            if not tag and '/' in pack_id:
                try:
                    so_name_cand, seq_cand_str = pack_id.split('/', 1)
                    if seq_cand_str.isdigit():
                        seq_cand = int(seq_cand_str)
                        cand_so = self.env['sale.order'].sudo().search([('name', '=', so_name_cand)], limit=1)
                        if cand_so and cand_so.state not in ('draft', 'cancel'):
                            tag = self.env['sale.order.ei'].sudo().search([
                                ('so_id', '=', cand_so.id),
                                ('sequence_number', '=', seq_cand)
                            ], limit=1)
                            if not tag:
                                with self.env.cr.savepoint():
                                    vals = {
                                        'so_id': cand_so.id,
                                        'sequence_number': seq_cand,
                                        'dispatched': True,
                                        'on_dock': False,
                                        'dock_id': False,
                                    }
                                    if 'dispatch_status' in self.env['sale.order.ei']._fields:
                                        vals['dispatch_status'] = 'success'
                                    tag = self.env['sale.order.ei'].sudo().create(vals)
                                self.env.cr.commit()
                                _logger.info(f"Auto-creada etiqueta EI {pack_id} en despacho para SO {cand_so.name}")
                            tag_by_name[pack_id] = tag
                            tag_by_name[pack_id_raw] = tag
                            if cand_so.id not in so_pick_picking:
                                pick_p = self.env['stock.picking'].sudo().search([
                                    ('sale_id', '=', cand_so.id),
                                    ('state', 'in', ['assigned', 'done']),
                                    ('picking_type_id.name', 'ilike', 'Pick')
                                ], order='date_done desc', limit=1)
                                if pick_p:
                                    so_pick_picking[cand_so.id] = pick_p
                except Exception as auto_ei_err:
                    _logger.warning(f"No se pudo auto-crear EI para {pack_id}: {auto_ei_err}")

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

        # Lo resuelto por complementos va al final para que la ventana de MAX_DETAIL_LINES no lo descarte.
        log_lines.extend(special_log + [f"ERROR: {e}" for e in special_errors])

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
