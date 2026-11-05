import Dexie from 'dexie';

export const localDb = new Dexie('WMDS_Handheld_DB');

localDb.version(1).stores({
    // Índices para consultas eficientes en cola FIFO y auditoría
    scanQueue: '++id, sessionId, barcode, type, status, timestamp, [sessionId+status]',
    dispatchSessions: 'sessionId, operator, carrierId, status, updatedAt'
});

/**
 * Sanitiza cualquier objeto para que sea compatible con el Structured Clone Algorithm de IndexedDB
 * (elimina instancias de Vue, nodos DOM, funciones y referencias circulares)
 */
export function safeSerialize(val, depth = 0) {
    if (val === null || val === undefined) return null;
    if (typeof val !== 'object') {
        if (typeof val === 'function' || typeof val === 'symbol') return undefined;
        return val;
    }
    if (depth > 4) return undefined;

    // Detectar y descartar instancias de componentes Vue, Window y elementos DOM
    if (val.$ || val._isVue || val.$el || val.$options || (typeof Node !== 'undefined' && val instanceof Node) || (typeof Window !== 'undefined' && val instanceof Window)) {
        return undefined;
    }

    if (Array.isArray(val)) {
        return val.map(item => safeSerialize(item, depth + 1)).filter(item => item !== undefined);
    }

    const clean = {};
    for (const key of Object.keys(val)) {
        if (key.startsWith('$') || key.startsWith('_')) continue;
        const serialized = safeSerialize(val[key], depth + 1);
        if (serialized !== undefined) {
            clean[key] = serialized;
        }
    }
    return clean;
}

/**
 * Inicializa y abre explícitamente la base de datos local en IndexedDB
 */
export async function initLocalDb() {
    try {
        if (!localDb.isOpen()) {
            await localDb.open();
            console.log("[localDb] WMDS_Handheld_DB abierta y lista");
        }
        return localDb;
    } catch (err) {
        console.error("[localDb] Error abriendo WMDS_Handheld_DB:", err);
        return null;
    }
}

// Auto-inicializar al cargar el módulo
if (typeof window !== 'undefined' && 'indexedDB' in window) {
    initLocalDb();
}

/**
 * Encola o registra un escaneo de forma instantánea en IndexedDB (< 5ms)
 */
export async function enqueueScan({ sessionId, barcode, type = 'dispatch_ei', status = 'pending', payload = {} }) {
    const cleanBarcode = String(barcode || '').trim();
    if (!cleanBarcode) return null;

    const safePayload = safeSerialize(payload) || {};

    const record = {
        sessionId: String(sessionId || 'default'),
        barcode: cleanBarcode,
        type: String(type || 'scan'),
        status,
        timestamp: Date.now(),
        retryCount: 0,
        errorMsg: null,
        payload: safePayload,
        serverResponse: null
    };

    try {
        const id = await localDb.scanQueue.add(record);
        record.id = id;
        return record;
    } catch (err) {
        console.warn("[localDb] Fallo al guardar en scanQueue:", err);
        return record;
    }
}

/**
 * Obtiene los escaneos pendientes para una sesión en orden FIFO
 */
export async function getPendingScans(sessionId) {
    if (sessionId) {
        return await localDb.scanQueue
            .where('[sessionId+status]')
            .equals([sessionId, 'pending'])
            .sortBy('timestamp');
    }
    return await localDb.scanQueue
        .where('status')
        .equals('pending')
        .sortBy('timestamp');
}

/**
 * Actualiza el estado de un escaneo en la base de datos local
 */
export async function updateScanStatus(id, status, extra = {}) {
    if (!id) return null;
    try {
        const safeExtra = safeSerialize(extra) || {};
        return await localDb.scanQueue.update(id, {
            status,
            ...safeExtra,
            updatedAt: Date.now()
        });
    } catch (err) {
        console.warn(`[localDb] Fallo al actualizar scan ${id}:`, err);
        return null;
    }
}

/**
 * Obtiene todos los escaneos de una sesión
 */
export async function getSessionScans(sessionId) {
    return await localDb.scanQueue
        .where('sessionId')
        .equals(sessionId)
        .sortBy('timestamp');
}

/**
 * Limpia los escaneos sincronizados de una sesión finalizada
 */
export async function clearSyncedScans(sessionId) {
    return await localDb.scanQueue
        .where({ sessionId, status: 'synced' })
        .delete();
}

/**
 * Limpia todos los escaneos completados ('synced') de la base de datos local
 */
export async function clearAllSyncedScans() {
    try {
        const count = await localDb.scanQueue
            .where('status')
            .equals('synced')
            .delete();
        console.log(`[localDb] Purgados ${count} escaneos sincronizados.`);
        return count;
    } catch (err) {
        console.error("[localDb] Error purgando escaneos sincronizados:", err);
        return 0;
    }
}

/**
 * Reinicia todos los escaneos en estado de error a 'pending' para reintento manual
 */
export async function resetErrorScansToPending() {
    try {
        const count = await localDb.scanQueue
            .where('status')
            .equals('error')
            .modify({
                status: 'pending',
                retryCount: 0,
                errorMsg: null,
                updatedAt: Date.now()
            });
        console.log(`[localDb] Reiniciados ${count} escaneos con error a 'pending'.`);
        return count;
    } catch (err) {
        console.error("[localDb] Error reiniciando escaneos fallidos:", err);
        return 0;
    }
}

/**
 * Obtiene todos los escaneos con estado de error
 */
export async function getErrorScans() {
    try {
        return await localDb.scanQueue
            .where('status')
            .equals('error')
            .reverse()
            .sortBy('timestamp');
    } catch (err) {
        console.error("[localDb] Error obteniendo escaneos con error:", err);
        return [];
    }
}

/**
 * Elimina un escaneo puntual por su ID
 */
export async function deleteScanById(id) {
    try {
        await localDb.scanQueue.delete(id);
        console.log(`[localDb] Eliminado escaneo con ID ${id}`);
        return true;
    } catch (err) {
        console.error(`[localDb] Error eliminando escaneo ${id}:`, err);
        return false;
    }
}

/**
 * Elimina una lista de escaneos por sus IDs
 */
export async function deleteScansByIds(ids) {
    try {
        if (!ids || ids.length === 0) return 0;
        await localDb.scanQueue.bulkDelete(ids);
        console.log(`[localDb] Eliminados ${ids.length} escaneos seleccionados`);
        return ids.length;
    } catch (err) {
        console.error("[localDb] Error eliminando escaneos masivos:", err);
        return 0;
    }
}

/**
 * Elimina todos los escaneos con estado de error
 */
export async function clearAllErrorScans() {
    try {
        const count = await localDb.scanQueue
            .where('status')
            .equals('error')
            .delete();
        console.log(`[localDb] Eliminados todos los escaneos con error (${count})`);
        return count;
    } catch (err) {
        console.error("[localDb] Error eliminando todos los errores:", err);
        return 0;
    }
}

/**
 * Consulta las estadísticas actuales de la cola de escaneo
 */
export async function getBufferStats() {
    try {
        const [pending, processing, synced, error] = await Promise.all([
            localDb.scanQueue.where('status').equals('pending').count(),
            localDb.scanQueue.where('status').equals('processing').count(),
            localDb.scanQueue.where('status').equals('synced').count(),
            localDb.scanQueue.where('status').equals('error').count()
        ]);

        let lastError = null;
        if (error > 0) {
            const errItems = await localDb.scanQueue
                .where('status')
                .equals('error')
                .reverse()
                .sortBy('timestamp');
            if (errItems && errItems.length > 0) {
                lastError = errItems[0];
            }
        }

        const totalActive = pending + processing;
        return {
            pending,
            processing,
            synced,
            error,
            totalActive,
            hasData: (totalActive + synced + error) > 0,
            lastError
        };
    } catch (err) {
        console.warn("[localDb] Error obteniendo estadísticas de buffer:", err);
        return {
            pending: 0,
            processing: 0,
            synced: 0,
            error: 0,
            totalActive: 0,
            hasData: false,
            lastError: null
        };
    }
}
