import Dexie from 'dexie';

export const localDb = new Dexie('WMDS_Handheld_DB');

localDb.version(1).stores({
    // Índices para consultas eficientes en cola FIFO
    scanQueue: '++id, sessionId, barcode, status, timestamp, [sessionId+status]',
    dispatchSessions: 'sessionId, operator, carrierId, status, updatedAt'
});

/**
 * Encola un escaneo de forma instantánea en IndexedDB (< 5ms)
 */
export async function enqueueScan({ sessionId, barcode, type = 'dispatch_ei', payload = {} }) {
    const cleanBarcode = String(barcode || '').trim();
    if (!cleanBarcode) return null;

    const record = {
        sessionId: sessionId || 'default',
        barcode: cleanBarcode,
        type,
        status: 'pending',
        timestamp: Date.now(),
        retryCount: 0,
        errorMsg: null,
        payload,
        serverResponse: null
    };

    const id = await localDb.scanQueue.add(record);
    record.id = id;
    return record;
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
    return await localDb.scanQueue.update(id, {
        status,
        ...extra,
        updatedAt: Date.now()
    });
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
