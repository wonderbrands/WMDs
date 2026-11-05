import { 
    localDb, 
    updateScanStatus, 
    getPendingScans, 
    clearAllSyncedScans, 
    resetErrorScansToPending, 
    getBufferStats,
    getErrorScans,
    deleteScanById,
    deleteScansByIds,
    clearAllErrorScans
} from './localDb';

class ScanQueueWorker {
    constructor() {
        this.isProcessing = false;
        this.listeners = new Set();
        this.store = null;
        this.activeSessionId = null;
        this.retryTimeout = null;
        this.retryInterval = null;
        this.cleanupInterval = null;
    }

    /**
     * Inicializa el worker con la instancia del store de Pinia y arranca timers
     */
    async init(store) {
        this.store = store;
        await this.recoverOrphanProcessingScans();
        await this.refreshBufferStats();
        this.startPeriodicRetry();
        this.startPeriodicCleanup();
        console.log("[QueueWorker] Inicializado con timers de 5m (reintento) y 10m (limpieza)");
    }

    /**
     * Timer periódico cada 5 minutos (300,000 ms) para reintentar scans pendientes o no sincronizados
     */
    startPeriodicRetry() {
        if (this.retryInterval) clearInterval(this.retryInterval);
        this.retryInterval = setInterval(async () => {
            console.log("[QueueWorker] Ciclo de reintento automático (cada 5 min)...");
            try {
                const pending = await getPendingScans(null);
                if (pending && pending.length > 0) {
                    this.kickQueue();
                }
                await this.refreshBufferStats();
            } catch (e) {
                console.error("[QueueWorker] Error en ciclo de reintento periódico:", e);
            }
        }, 5 * 60 * 1000);
    }

    /**
     * Timer periódico cada 10 minutos (600,000 ms) para eliminar registros completados ('synced')
     */
    startPeriodicCleanup() {
        if (this.cleanupInterval) clearInterval(this.cleanupInterval);
        this.cleanupInterval = setInterval(async () => {
            console.log("[QueueWorker] Ciclo de limpieza automática de completados (cada 10 min)...");
            try {
                await clearAllSyncedScans();
                await this.refreshBufferStats();
            } catch (e) {
                console.error("[QueueWorker] Error en ciclo de limpieza automática:", e);
            }
        }, 10 * 60 * 1000);
    }

    async recoverOrphanProcessingScans() {
        try {
            const count = await localDb.scanQueue
                .where('status')
                .equals('processing')
                .modify({ status: 'pending' });
            if (count > 0) {
                console.log(`[QueueWorker] Recuperados ${count} escaneos huérfanos de 'processing' a 'pending'`);
            }
        } catch (e) {
            console.error("Error recuperando scans huérfanos:", e);
        }
    }

    /**
     * Consulta las estadísticas actuales de IndexedDB y actualiza el store
     */
    async refreshBufferStats() {
        try {
            const stats = await getBufferStats();
            if (this.store && typeof this.store.updateBufferStats === 'function') {
                this.store.updateBufferStats(stats);
            }
            this.notify('stats_updated', stats);
            return stats;
        } catch (e) {
            console.warn("[QueueWorker] Error actualizando buffer stats:", e);
            return null;
        }
    }

    /**
     * Dispara un reintento manual inmediato de los registros con error o pendientes
     */
    async triggerManualRetry() {
        console.log("[QueueWorker] Reintento manual solicitado por usuario");
        await resetErrorScansToPending();
        await this.refreshBufferStats();
        this.kickQueue();
    }

    /**
     * Purgado manual inmediato de los registros completados
     */
    async triggerManualClearSynced() {
        console.log("[QueueWorker] Purgado manual de completados solicitado");
        await clearAllSyncedScans();
        await this.refreshBufferStats();
    }

    /**
     * Obtiene los escaneos con error para visualización detallada en el widget
     */
    async getErrorScans() {
        return await getErrorScans();
    }

    /**
     * Elimina un único escaneo por su ID y actualiza métricas reactivas
     */
    async triggerDeleteErrorScan(id) {
        console.log(`[QueueWorker] Eliminando escaneo con error ID: ${id}`);
        const res = await deleteScanById(id);
        await this.refreshBufferStats();
        return res;
    }

    /**
     * Elimina una lista de escaneos seleccionados por sus IDs y actualiza métricas reactivas
     */
    async triggerDeleteSelectedErrors(ids) {
        console.log(`[QueueWorker] Eliminando ${ids?.length || 0} escaneos seleccionados`);
        const res = await deleteScansByIds(ids);
        await this.refreshBufferStats();
        return res;
    }

    /**
     * Elimina todos los escaneos en estado de error de la base de datos local
     */
    async triggerClearAllErrors() {
        console.log("[QueueWorker] Eliminando todos los escaneos con error");
        const res = await clearAllErrorScans();
        await this.refreshBufferStats();
        return res;
    }

    /**
     * Establece la sesión activa y despierta la cola
     */
    setActiveSession(sessionId) {
        this.activeSessionId = sessionId;
        this.kickQueue();
    }

    /**
     * Suscribe un componente a los eventos de la cola
     */
    subscribe(callback) {
        this.listeners.add(callback);
        return () => this.listeners.delete(callback);
    }

    notify(event, data) {
        this.listeners.forEach(cb => {
            try {
                cb(event, data);
            } catch (err) {
                console.error("Error in queue listener:", err);
            }
        });
    }

    /**
     * Despierta el ciclo de procesamiento de la cola si no está corriendo
     */
    kickQueue() {
        this.refreshBufferStats();
        if (this.isProcessing) return;
        this.processQueue();
    }

    /**
     * Bucle principal FIFO de procesamiento en segundo plano
     */
    async processQueue() {
        if (this.isProcessing) return;
        this.isProcessing = true;

        try {
            await this.recoverOrphanProcessingScans();
            while (true) {
                let pendingItems = await getPendingScans(this.activeSessionId);
                if (!pendingItems || pendingItems.length === 0) {
                    const fallback = await getPendingScans(null);
                    if (fallback && fallback.length > 0) {
                        pendingItems = fallback;
                    } else {
                        console.log(`[QueueWorker] Cola vacía para sesión: ${this.activeSessionId}`);
                        this.notify('queue_empty', { sessionId: this.activeSessionId });
                        break;
                    }
                }

                const item = pendingItems[0];
                console.log(`[QueueWorker] Procesando item ${item.id} (${item.barcode})...`);
                await updateScanStatus(item.id, 'processing');
                await this.refreshBufferStats();
                this.notify('processing', item);

                try {
                    const result = await this.dispatchItem(item);
                    console.log(`[QueueWorker] Resultado para ${item.barcode}:`, result);
                    if (result.ok) {
                        await updateScanStatus(item.id, 'synced', {
                            serverResponse: result.data
                        });
                        item.status = 'synced';
                        item.serverResponse = result.data;
                        this.notify('synced', { item, result: result.data });

                        // RETROALIMENTACIÓN VISUAL DE ÉXITO (Toast verde):
                        if (this.store && typeof this.store.notifyBufferSuccess === 'function') {
                            this.store.notifyBufferSuccess(item, result.data);
                        }
                    } else {
                        // Error de validación / negocio
                        const errorMsg = result.error || 'Validación rechazada';
                        console.warn(`[QueueWorker] Error de negocio para ${item.barcode}:`, errorMsg);
                        await updateScanStatus(item.id, 'error', {
                            errorMsg,
                            serverResponse: result.data
                        });
                        item.status = 'error';
                        item.errorMsg = errorMsg;
                        item.serverResponse = result.data;
                        this.notify('error', { item, error: errorMsg, isBusinessError: true, serverResponse: result.data });
                        
                        // PREVENCIÓN DE FALLO SILENCIOSO: Disparar toast estándar en UI
                        if (this.store && typeof this.store.notifyBufferError === 'function') {
                            this.store.notifyBufferError(errorMsg, item.barcode);
                        }
                    }
                } catch (netErr) {
                    console.error("[QueueWorker] Error de red procesando escaneo:", netErr);
                    const newRetry = (item.retryCount || 0) + 1;
                    const netMsg = netErr.message || 'Error de conexión con el servidor';
                    
                    // Retroalimentación inmediata en Toast (no silenciar fallos de red)
                    if (this.store && typeof this.store.notifyBufferError === 'function') {
                        this.store.notifyBufferError(`Fallo de red (${netMsg}). Guardado en buffer local para reenvío automático.`, item.barcode);
                    }

                    if (newRetry <= 5) {
                        // Reintentar más tarde
                        await updateScanStatus(item.id, 'pending', {
                            retryCount: newRetry,
                            errorMsg: netMsg
                        });
                        this.notify('retry', { item, attempt: newRetry, error: netMsg });
                        // Esperar con backoff exponencial antes de continuar
                        await new Promise(r => setTimeout(r, Math.min(1000 * Math.pow(2, newRetry), 8000)));
                    } else {
                        // Máximo de reintentos alcanzado
                        const permError = 'Excedido límite de reintentos por error de conexión';
                        await updateScanStatus(item.id, 'error', {
                            errorMsg: permError
                        });
                        this.notify('error', { item, error: permError, isBusinessError: false });
                    }
                    break; // Pausar ciclo hasta siguiente trigger
                } finally {
                    await this.refreshBufferStats();
                }
            }
        } finally {
            this.isProcessing = false;
            await this.refreshBufferStats();
        }
    }

    /**
     * Envia el elemento al endpoint correspondiente en Odoo
     */
    async dispatchItem(item) {
        if (!this.store) {
            throw new Error("Store no inicializado en ScanQueueWorker");
        }

        if (item.type === 'dispatch_ei') {
            return await this.processDispatchEi(item);
        } else if (item.type === 'bin_ei' || item.type === 'bin_scan_so') {
            return await this.processBinScanSo(item);
        } else if (item.payload && item.payload.context) {
            return await this.processContextAction(item);
        }

        return { ok: false, error: `Tipo de escaneo no soportado: ${item.type}` };
    }

    async processContextAction(item) {
        const res = await this.store.executeActionByContext(item.payload.context, item.barcode, item.payload.extra_data);
        if (res && res.error && res.error.is_network_error) {
            throw new Error(res.error.message || 'Error de conexión');
        }
        if (res && res.error) {
            return { ok: false, error: res.error.message || 'Error en validación', data: res };
        }
        return { ok: true, data: res };
    }

    /**
     * Lógica de validación para etiquetas en BIN (bin_scan_so)
     */
    async processBinScanSo(item) {
        const valRes = await this.store.callOdooSilent("validate_attachment_guide", "", {
            attachment_id: item.barcode
        });

        if (!valRes || (valRes.error && valRes.error.is_network_error)) {
            const netMsg = (valRes && valRes.error && valRes.error.message) || 'Error de conexión con el servidor';
            throw new Error(netMsg);
        }

        if (valRes.error) {
            return {
                ok: false,
                error: valRes.error.message || 'Error del servidor',
                data: valRes
            };
        }

        if (!valRes.valid) {
            return {
                ok: false,
                error: valRes.message || 'La guía escaneada no es válida o no existe.',
                data: valRes
            };
        }

        const state = valRes.state || {};
        if (state.dispatched) {
            return {
                ok: false,
                error: `La guía ${item.barcode} ya fue despachada anteriormente.`,
                data: valRes
            };
        }
        if (state.on_bin) {
            return {
                ok: false,
                error: `La guía ${item.barcode} ya se encuentra registrada en el BIN ${state.bin_name}.`,
                data: valRes
            };
        }
        if (state.on_dock) {
            return {
                ok: false,
                error: `La guía ${item.barcode} ya se encuentra ubicada en el DOCK ${state.dock_name}.`,
                data: valRes
            };
        }

        const payload = item.payload || {};
        if (payload.carrier_id) {
            const carrierCheck = await this.store.callOdooSilent("validate_ei_carrier", "", {
                so_name: valRes.so,
                carrier_id: payload.carrier_id,
            });
            if (carrierCheck && carrierCheck.error && carrierCheck.error.is_network_error) {
                throw new Error(carrierCheck.error.message || 'Error de conexión');
            }
            if (!carrierCheck || !carrierCheck.valid) {
                return {
                    ok: false,
                    error: (carrierCheck && carrierCheck.message) || 'Carrier no coincide con la guía',
                    data: carrierCheck
                };
            }
        }

        return {
            ok: true,
            data: valRes
        };
    }

    /**
     * Lógica de validación y persistencia para etiquetas EI en Despacho
     */
    async processDispatchEi(item) {
        const valRes = await this.store.callOdooSilent("validate_attachment_guide", "", {
            attachment_id: item.barcode
        });

        if (valRes && valRes.error && valRes.error.is_network_error) {
            throw new Error(valRes.error.message || 'Error de conexión con el servidor');
        }

        if (!valRes || !valRes.valid) {
            return {
                ok: false,
                error: (valRes && valRes.error) || 'Etiqueta o formato no válido en Odoo',
                data: valRes
            };
        }

        if (valRes.so_state === 'cancel') {
            return {
                ok: false,
                error: `El pedido ${valRes.so} está cancelado.`,
                data: { ...valRes, is_cancelled: true }
            };
        }

        if (valRes.state && valRes.state.dispatched) {
            return {
                ok: false,
                error: `La etiqueta ${item.barcode} ya fue despachada anteriormente.`,
                data: { ...valRes, already_dispatched: true }
            };
        }

        const payload = item.payload || {};
        const sessionRes = await this.store.callOdooSilent("save_dispatch_session_line", "", {
            operator_login: payload.operator_login || this.store.role?.email,
            ei_name: valRes.name || item.barcode,
            so_name: valRes.so,
            total: valRes.total,
            current: valRes.current,
            dispatched_count: valRes.dispatched_count || 0,
            carrier_id: payload.carrier_id || null
        });

        if (sessionRes && sessionRes.carrier_mismatch) {
            return {
                ok: false,
                error: sessionRes.mismatch_message || 'El transportista no coincide con la guía.',
                data: sessionRes
            };
        }

        if (!sessionRes || !sessionRes.ok) {
            return {
                ok: false,
                error: (sessionRes && sessionRes.error) || 'Error guardando línea de sesión en Odoo',
                data: sessionRes
            };
        }

        return {
            ok: true,
            data: {
                ...valRes,
                session_id: sessionRes.session_id,
                line_id: sessionRes.line_id,
                product_name: sessionRes.product_name || '',
                carrier_name: sessionRes.carrier_name || '',
            }
        };
    }

    /**
     * Lógica de validación para etiquetas en BIN
     */
    async processBinEi(item) {
        const valRes = await this.store.callOdooSilent("validate_attachment_guide", "", {
            attachment_id: item.barcode
        });

        if (!valRes || !valRes.valid) {
            return { ok: false, error: 'Guía no válida', data: valRes };
        }

        return { ok: true, data: valRes };
    }
}

export const scanQueueWorker = new ScanQueueWorker();
