import { createApp, h } from 'vue';
import PrimeVue from 'primevue/config';
import ToastService from 'primevue/toastservice';
import Aura from '@primeuix/themes/aura';
import { createPinia } from 'pinia';
import Toast from 'primevue/toast';
import DispatchComponent from './components/OperatorComponent/DispatchComponent.vue';
import { useGeneralStore } from './store/index';
import { localDb } from './services/localDb';
import { scanQueueWorker } from './services/scanQueueWorker';

const app = createApp({
    render() {
        return h('div', [
            h(Toast),
            h(DispatchComponent, { ref: 'dispatch' })
        ]);
    }
});

const pinia = createPinia();
app.use(ToastService);
pinia.use(({ store }) => {
    store.toast = app.config.globalProperties.$toast;
});
app.use(pinia);
app.use(PrimeVue, {
    theme: {
        preset: Aura,
        options: {
            darkModeSelector: false
        }
    }
});

// Inicializar y mockear store ANTES de montar el componente
const store = useGeneralStore(pinia);

store.role = {
    email: 'test_operator@wonderbrands.co',
    name: 'Test Operator',
    role: 'WMDs Operator',
    is_identified: true
};

const testState = {
    backendDelayMs: 40,
    serverFail: false,
    cancelledBarcodes: new Set(),
    mismatchBarcodes: new Set(),
    backendCalls: [],
};

// Mock Odoo calls
const originalCallOdoo = async (context, term, params, options = {}) => {
    testState.backendCalls.push({ context, term, params, time: Date.now() });

    if (testState.backendDelayMs > 0) {
        await new Promise(r => setTimeout(r, testState.backendDelayMs));
    }

    if (testState.serverFail) {
        throw new Error('Connection refused / 500 Internal Server Error');
    }

    switch (context) {
        case 'get_carrier_list':
            return {
                ok: true,
                carriers: [
                    { id: 1, name: 'DHL Express' },
                    { id: 2, name: 'Estafeta' },
                    { id: 3, name: 'FedEx' }
                ]
            };

        case 'get_dispatch_session':
            return {
                active: false,
                session_id: null,
                carrier_id: null,
                lines: []
            };

        case 'validate_attachment_guide': {
            const barcode = params.attachment_id || '';
            if (testState.cancelledBarcodes.has(barcode)) {
                const so = barcode.split('/')[0] || barcode;
                return {
                    valid: true,
                    name: barcode,
                    so: so,
                    so_state: 'cancel',
                    total: 1,
                    current: 1,
                    dispatched_count: 0
                };
            }
            if (barcode.startsWith('INVALID')) {
                return { valid: false, error: 'Etiqueta no encontrada en Odoo' };
            }
            const parts = barcode.match(/^([A-Za-z0-9_\-]+)\/(\d+)/);
            const so = parts ? parts[1] : barcode;
            const current = parts ? parseInt(parts[2], 10) : 1;
            return {
                valid: true,
                name: barcode,
                so: so,
                so_state: 'sale',
                total: 2,
                current: current,
                dispatched_count: 0,
                state: { dispatched: false, on_dock: true }
            };
        }

        case 'save_dispatch_session_line': {
            const barcode = params.ei_name || '';
            if (testState.mismatchBarcodes.has(barcode)) {
                return {
                    ok: false,
                    carrier_mismatch: true,
                    mismatch_message: 'Guía no pertenece al carrier seleccionado'
                };
            }
            return {
                ok: true,
                session_id: 888,
                line_id: Math.floor(Math.random() * 10000) + 1,
                product_name: 'Producto SKU-TEST-01',
                carrier_name: 'DHL Express'
            };
        }

        case 'remove_dispatch_session_line':
            return { ok: true };

        case 'clear_dispatch_session':
            return { ok: true };

        case 'complete_dispatch_session':
            return {
                ok: true,
                session_id: 888,
                operator_name: 'Test Operator',
                carrier_name: 'DHL Express',
                date_start: new Date().toISOString(),
                date_end: new Date().toISOString(),
                lines: [],
                so_summary: [],
                total_lines: 5
            };

        case 'dispatch_orders':
            return { status: 'success' };

        default:
            return { ok: true };
    }
};

store.callOdoo = (context, term, params, options) => originalCallOdoo(context, term, params, options);
store.callOdooSilent = (context, term, params) => originalCallOdoo(context, term, params, { silent: true });

// Ahora sí, montar la app
const vm = app.mount('#test-app');

// Expose helpers for Playwright
window.__TEST__ = {
    localDb,
    scanQueueWorker,
    getDispatchVm: () => vm.$refs.dispatch,
    getStore: () => store,
    testState,
    async clearAllLocalDb() {
        await localDb.scanQueue.clear();
        await localDb.dispatchSessions.clear();
    },
    async simulateLaserScan(barcode) {
        const dispatchVm = vm.$refs.dispatch;
        if (!dispatchVm) throw new Error("DispatchComponent not found");
        await dispatchVm.searchAndValidateSO(barcode);
    }
};

console.log("__TEST__ ready");
