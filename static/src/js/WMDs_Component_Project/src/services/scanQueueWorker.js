import { localDb, updateScanStatus, getPendingScans } from './localDb';

class ScanQueueWorker {
    constructor() {
        this.isProcessing = false;
        this.listeners = new Set();
        this.store = null;
        this.activeSessionId = null;
        this.retryTimeout = null;
    }

    /**
     * Inicializa el worker con la instancia del store de Pinia
     */
    async init(store) {
        this.store = store;
        await this.recoverOrphanProcessingScans();
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
                        console.log(`[QueueWorker] Queue empty for session: ${this.activeSessionId}`);
                        this.notify('queue_empty', { sessionId: this.activeSessionId });
                        break;
                    }
                }

                const item = pendingItems[0];
                console.log(`[QueueWorker] Processing item ${item.id} (${item.barcode})...`);
                await updateScanStatus(item.id, 'processing');
                this.notify('processing', item);

                try {
                    const result = await this.dispatchItem(item);
                    console.log(`[QueueWorker] Result for ${item.barcode}:`, result);
                    if (result.ok) {
                        await updateScanStatus(item.id, 'synced', {
                            serverResponse: result.data
                        });
                        item.status = 'synced';
                        item.serverResponse = result.data;
                        this.notify('synced', { item, result: result.data });
                    } else {
                        // Error de validación / negocio
                        const errorMsg = result.error || 'Validación rechazada';
                        console.warn(`[QueueWorker] Business error for ${item.barcode}:`, errorMsg);
                        await updateScanStatus(item.id, 'error', {
                            errorMsg,
                            serverResponse: result.data
                        });
                        item.status = 'error';
                        item.errorMsg = errorMsg;
                        item.serverResponse = result.data;
                        this.notify('error', { item, error: errorMsg, isBusinessError: true, serverResponse: result.data });
                    }
                } catch (netErr) {
                    console.error("[QueueWorker] Error de red/servidor procesando escaneo:", netErr);
                    const newRetry = (item.retryCount || 0) + 1;
                    
                    if (newRetry <= 5) {
                        // Reintentar más tarde
                        await updateScanStatus(item.id, 'pending', {
                            retryCount: newRetry,
                            errorMsg: netErr.message || 'Error de conexión'
                        });
                        this.notify('retry', { item, attempt: newRetry });
                        // Esperar con backoff exponencial antes de continuar
                        await new Promise(r => setTimeout(r, Math.min(1000 * Math.pow(2, newRetry), 8000)));
                    } else {
                        // Máximo de reintentos alcanzado
                        await updateScanStatus(item.id, 'error', {
                            errorMsg: 'Excedido límite de reintentos por error de conexión'
                        });
                        this.notify('error', { item, error: 'Error de red permanente', isBusinessError: false });
                    }
                    break; // Pausar ciclo hasta siguiente trigger
                }
            }
        } finally {
            this.isProcessing = false;
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
        } else if (item.type === 'bin_ei') {
            return await this.processBinEi(item);
        }

        return { ok: false, error: `Tipo de escaneo no soportado: ${item.type}` };
    }

    /**
     * Lógica de validación y persistencia para etiquetas EI en Despacho
     */
    async processDispatchEi(item) {
        // Paso 1: Validar guía / etiqueta interna con Odoo de forma silenciosa
        const valRes = await this.store.callOdooSilent("validate_attachment_guide", "", {
            attachment_id: item.barcode
        });

        if (!valRes || !valRes.valid) {
            return {
                ok: false,
                error: (valRes && valRes.error) || 'Etiqueta o formato no válido en Odoo',
                data: valRes
            };
        }

        // Si está cancelado
        if (valRes.so_state === 'cancel') {
            return {
                ok: false,
                error: `El pedido ${valRes.so} está cancelado.`,
                data: { ...valRes, is_cancelled: true }
            };
        }

        // Si ya fue despachado
        if (valRes.state && valRes.state.dispatched) {
            return {
                ok: false,
                error: `La etiqueta ${item.barcode} ya fue despachada anteriormente.`,
                data: { ...valRes, already_dispatched: true }
            };
        }

        // Paso 2: Persistir en la sesión de despacho activa
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
