<template>
    <div 
        class="cycle-count-operator-container"
        @touchstart="handleTouchStart"
        @touchmove="handleTouchMove"
        @touchend="handleTouchEnd"
    >
        <!-- Pull to refresh indicator -->
        <div v-if="pulling" class="pull-to-refresh-indicator" :style="{ height: pullDistance + 'px', opacity: pullDistance / 100 }">
            <i class="fa fa-refresh" :class="{ 'fa-spin': refreshing }"></i>
            <span>{{ refreshing ? 'Actualizando...' : 'Tire para actualizar' }}</span>
        </div>

        <!-- Header Info -->
        <div class="operator-header">
            <div class="wave-info">
                <span class="label">OLA:</span>
                <span class="value">{{ waveName }}</span>
            </div>
            
            <div class="header-actions">
                <Button 
                    @click="showLocationsModal = true"
                    class="p-button-text p-button-info p-button-sm mr-2" 
                    icon="fa fa-list"
                    label="Ubicaciones"
                />
                <Button 
                    v-if="pending_locations.length === 0"
                    @click="finishWave"
                    class="p-button-text p-button-success p-button-sm mr-2" 
                    label="Finalizar" 
                    icon="fa fa-check-circle"
                    :loading="loading"
                />
                <Button 
                    @click="exitFlow"
                    class="p-button-text p-button-danger p-button-sm exit-btn" 
                    label="Salir" 
                    icon="fa fa-times"
                />
            </div>
        </div>

        <!-- Main Workflow Area -->
        <div class="workflow-area">
            
            <!-- Context Banner (Current Location) -->
            <div class="current-context-banner" v-if="current_location.id">
                <div class="context-main">
                    <i class="fa fa-map-marker"></i>
                    <div class="loc-info">
                        <span class="loc-label">UBICACIÓN ACTUAL</span>
                        <span class="loc-name">{{ current_location.name }}</span>
                    </div>
                </div>
                <div class="context-stats">
                    <span class="pending-count">Quedan {{ pending_locations.length }}</span>
                </div>
            </div>

            <!-- Step: Scan Product / Location Overview -->
            <div v-if="step === 'product' && current_location.id" class="step-container">
                
                <div class="action-bar-top" v-if="current_location.id">
                    <Button 
                        v-if="!locationHasCounts"
                        label="UBICACIÓN VACÍA" 
                        icon="fa fa-trash" 
                        severity="danger" 
                        class="p-button-sm flex-1"
                        @click="markEmpty"
                        :loading="loading"
                    />
                    <Button 
                        label="SIGUIENTE UBICACIÓN" 
                        icon="fa fa-arrow-right" 
                        iconPos="right"
                        severity="info" 
                        class="p-button-sm flex-1"
                        @click="moveToNextLocation"
                        :loading="loading"
                    />
                </div>

                <div class="scanner-section">
                    <BarcodeScannerComponent 
                        :key="scannerKey"
                        instructions="Escanea el PRODUCTO"
                        :onScan="(data) => handleProductScan(data)"
                    />
                </div>
            </div>

            <!-- Step 3: Set Quantity -->
            <div v-else-if="step === 'quantity'" class="step-container quantity-step">
                <div class="context-info-compact">
                    <i class="fa fa-box"></i>
                    <span>{{ current_product.sku || current_product.name }}</span>
                </div>

                <div class="quantity-form-wrapper">
                    <div class="quantity-form">
                        <label>Cantidad Contada</label>
                        <div class="qty-input-wrapper">
                            <Button label="-" @click="quantity > 0 ? quantity-- : 0" class="p-button-outlined qty-btn" />
                            <InputNumber v-model="quantity" :min="0" class="qty-input" autofocus />
                            <Button label="+" @click="quantity++" class="p-button-outlined qty-btn" />
                        </div>
                        <div class="form-actions">
                            <Button label="CANCELAR" icon="fa fa-times" class="p-button-secondary p-button-text" @click="step = 'product'" />
                            <Button label="CONFIRMAR" icon="fa fa-check" class="p-button-success" @click="confirmCount" :loading="loading" />
                        </div>
                    </div>
                </div>
            </div>

            <!-- No Pending State -->
            <div v-if="pending_locations.length === 0 && !loading" class="empty-state-container">
                <i class="fa fa-check-circle success-icon"></i>
                <h3>¡Conteo Terminado!</h3>
                <p>Has procesado todas las ubicaciones de esta ola.</p>
                <Button label="FINALIZAR OLA" icon="fa fa-check" severity="success" size="large" @click="finishWave" />
            </div>
        </div>

        <!-- Session Log -->
        <div class="session-log">
            <div class="log-title">Conteo en esta sesión:</div>
            <div class="log-items">
                <div v-for="(item, idx) in session_log" :key="idx" class="log-item">
                    <div class="log-details">
                        <span class="log-loc">{{ item.location }}</span>
                        <span class="log-prod">{{ item.product }}</span>
                    </div>
                    <div class="log-qty">{{ item.qty }}</div>
                </div>
                <div v-if="session_log.length === 0" class="empty-log">
                    No has registrado productos aún.
                </div>
            </div>
        </div>

    </div>

    <!-- Locations List Modal -->
    <Dialog v-model:visible="showLocationsModal" header="Detalle de Ubicaciones" :style="{ width: '90vw' }" modal>
        <div class="locations-modal-content">
            <div class="location-group">
                <div class="group-title">PENDIENTES ({{ pending_locations.length }})</div>
                <div class="loc-grid">
                    <div v-for="loc in pending_locations" :key="loc.id" class="loc-item-modal pending">
                        <i class="fa fa-map-marker"></i>
                        <span>{{ loc.name }}</span>
                    </div>
                    <div v-if="pending_locations.length === 0" class="empty-msg">No hay ubicaciones pendientes.</div>
                </div>
            </div>
            <div class="location-group mt-4">
                <div class="group-title">COMPLETADAS ({{ done_locations.length }})</div>
                <div class="loc-grid">
                    <div v-for="loc in done_locations" :key="loc.id" class="loc-item-modal done">
                        <i class="fa fa-check-circle"></i>
                        <span>{{ loc.name }}</span>
                    </div>
                    <div v-if="done_locations.length === 0" class="empty-msg">Aún no has completado ninguna ubicación.</div>
                </div>
            </div>
        </div>
        <template #footer>
            <Button label="CERRAR" icon="fa fa-times" @click="showLocationsModal = false" class="p-button-text" />
        </template>
    </Dialog>
</template>

<script>
import BarcodeScannerComponent from '../QRScannerComponent/BarcodeScannerComponent.vue';
import Button from 'primevue/button';
import InputNumber from 'primevue/inputnumber';
import Dialog from 'primevue/dialog';
import { useGeneralStore } from "../../store/index";

export default {
    name: "CycleCountOperator",
    components: {
        BarcodeScannerComponent,
        Button,
        InputNumber,
        Dialog
    },
    data() {
        return {
            store: useGeneralStore(),
            ready: false,
            loading: false,
            scannerKey: 0,
            step: 'product', // product, quantity
            current_location: { id: null, name: '' },
            current_product: { id: null, name: '', sku: '' },
            quantity: 0,
            session_log: [],
            waveId: null,
            waveName: 'Cargando...',
            locations_list: [], 
            showLocationsModal: false,
            // Pull to refresh state
            startY: 0,
            pullDistance: 0,
            pulling: false,
            refreshing: false,
            maxPullDistance: 100
        }
    },
    computed: {
        pending_locations() {
            return (this.locations_list || []).filter(l => l.status === 'pending');
        },
        done_locations() {
            return (this.locations_list || []).filter(l => l.status === 'done');
        },
        locationHasCounts() {
            if (!this.current_location.id) return false;
            return this.session_log.some(log => log.location === this.current_location.name && log.qty > 0);
        }
    },
    async mounted() {
        this.waveId = this.store.mandatory_uncompleted.component_props?.cc_id;
        if (!this.waveId) {
            this.$toast.add({ 
                severity: 'error', 
                summary: 'Error de Inicialización', 
                detail: 'No se pudo recuperar el identificador de la ola de conteo.', 
                life: 5000 
            });
            this.exitFlow();
            return;
        }
        
        await this.loadWaveInfo();
        this.autoSelectFirstLocation();
        this.ready = true;
    },
    methods: {
        async loadWaveInfo(silent = false) {
            if (!silent) this.loading = true;
            try {
                let res = await this.store.callOdoo("get_cycle_count_details_minimal", "", { wave_id: this.waveId });
                if (res && res.ok) {
                    this.waveName = res.name ? res.name.split(' ')[0] : 'Cargando...';
                    this.locations_list = res.locations || [];
                } else if (res && res.error) {
                    this.$toast.add({ severity: 'error', summary: 'Error', detail: res.error, life: 5000 });
                }
            } finally {
                if (!silent) this.loading = false;
            }
        },

        autoSelectFirstLocation() {
            if (this.pending_locations.length > 0) {
                const loc = this.pending_locations[0];
                this.current_location = {
                    id: loc.id,
                    name: loc.name
                };
                this.step = 'product';
            } else {
                this.current_location = { id: null, name: '' };
            }
        },

        async handleProductScan(data) {
            try {
                let res = await this.store.callOdoo("validate_cycle_count_product", "", {
                    barcode: data
                });

                if (res.ok) {
                    this.current_product = {
                        id: res.product_id,
                        name: res.product_name,
                        sku: res.product_sku
                    };
                    this.quantity = 1;
                    this.step = 'quantity';
                } else {
                    this.$toast.add({ 
                        severity: 'error', 
                        summary: 'Producto no Encontrado', 
                        detail: (res.error || 'Producto no encontrado.'), 
                        life: 4000 
                    });
                    this.scannerKey++;
                }
            } catch (e) {
                this.$toast.add({ 
                    severity: 'error', 
                    summary: 'Error de Búsqueda', 
                    detail: (e.message || 'Error al buscar el producto.'), 
                    life: 4000 
                });
                this.scannerKey++;
            }
            await this.loadWaveInfo(true);
        },

        async markEmpty() {
            if (!this.current_location.id) return;
            
            const isLast = this.pending_locations.length === 1;
            const confirmMsg = `¿Confirmas que la ubicación ${this.current_location.name} está totalmente vacía?`;

            if (!confirm(confirmMsg)) return;
            
            this.loading = true;
            try {
                let res = await this.store.callOdoo("mark_location_empty", "", {
                    wave_id: this.waveId,
                    location_id: this.current_location.id,
                    operator_email: this.store.role.email
                });

                if (res.ok) {
                    const isManager = this.store.role && (this.store.role.role === 'WMDs Manager' || (this.store.role.permissions && this.store.role.permissions.includes('WMDs Manager')));
                    if (!isManager) {
                        this.$toast.add({ 
                            severity: 'success', 
                            summary: 'Ubicación Vacía', 
                            detail: `Ubicación ${this.current_location.name} registrada como vacía.`, 
                            life: 2000 
                        });
                    }
                    
                    this.session_log.unshift({
                        location: this.current_location.name,
                        product: '(UBICACIÓN VACÍA)',
                        qty: 0
                    });

                    await this.loadWaveInfo(true);
                    this.autoSelectFirstLocation();
                    this.scannerKey++;
                } else {
                    this.$toast.add({ severity: 'error', summary: 'Error', detail: res.error, life: 4000 });
                }
            } finally {
                this.loading = false;
            }
        },

        async moveToNextLocation() {
            if (!this.current_location.id) return;

            // Mark current as "done" by sending a dummy counted line if it doesn't have any product yet
            // to ensure it disappears from pending. If it has products, it's already counted.
            if (!this.locationHasCounts) {
                 this.loading = true;
                 try {
                     // We mark it as counted (implicitly "finished")
                     await this.store.callOdoo("mark_location_empty", "", {
                        wave_id: this.waveId,
                        location_id: this.current_location.id,
                        operator_email: this.store.role.email
                    });
                 } finally {
                     this.loading = false;
                 }
            }

            await this.loadWaveInfo(true);
            this.autoSelectFirstLocation();
            this.scannerKey++;
            this.$toast.add({ severity: 'info', summary: 'Siguiente Ubicación', detail: this.current_location.name || 'Ola completada', life: 2000 });
        },

        async confirmCount() {
            this.loading = true;
            try {
                let res = await this.store.callOdoo("log_cycle_count_line", "", {
                    wave_id: this.waveId,
                    location_id: this.current_location.id,
                    product_id: this.current_product.id,
                    qty: this.quantity,
                    operator_email: this.store.role.email
                });

                if (res.ok) {
                    const isManager = this.store.role && (this.store.role.role === 'WMDs Manager' || (this.store.role.permissions && this.store.role.permissions.includes('WMDs Manager')));
                    if (!isManager) {
                        this.$toast.add({ 
                            severity: 'success', 
                            summary: 'Conteo Registrado', 
                            detail: `Registrado: ${this.quantity} de ${this.current_product.sku || this.current_product.name}.`, 
                            life: 2000 
                        });
                    }
                    
                    this.session_log.unshift({
                        location: this.current_location.name,
                        product: this.current_product.sku || this.current_product.name,
                        qty: this.quantity
                    });

                    this.current_product = { id: null, name: '', sku: '' };
                    this.quantity = 0;
                    this.step = 'product';
                    this.scannerKey++;
                } else {
                    this.$toast.add({ severity: 'error', summary: 'Error', detail: res.error, life: 4000 });
                }
            } finally {
                this.loading = false;
            }
        },

        async finishWave() {
            if (this.pending_locations.length > 0) {
                this.$toast.add({ 
                    severity: 'warn', 
                    summary: 'Pendientes', 
                    detail: `Faltan ${this.pending_locations.length} ubicaciones por procesar.`, 
                    life: 4000 
                });
                return;
            }
            if (!confirm("¿Deseas finalizar esta ola de conteo?")) return;
            this.loading = true;
            try {
                let res = await this.store.callOdoo("finish_cycle_count_wave", "", { wave_id: this.waveId });
                if (res.ok) {
                    this.store.mandatory_uncompleted.doneMandatory();
                } else {
                    this.$toast.add({ severity: 'error', summary: 'Error', detail: res.error, life: 4000 });
                }
            } finally {
                this.loading = false;
            }
        },

        exitFlow() {
            if (this.step === 'quantity') {
                if (!confirm("Tienes un conteo pendiente. ¿Deseas salir de todas formas?")) return;
            }
            this.store.mandatory_uncompleted.doneMandatory();
        },

        // Pull to refresh handlers
        handleTouchStart(e) {
            if (this.$el.scrollTop === 0) {
                this.startY = e.touches[0].pageY;
                this.pulling = true;
            }
        },
        handleTouchMove(e) {
            if (!this.pulling || this.refreshing) return;
            const currentY = e.touches[0].pageY;
            const diff = currentY - this.startY;
            if (diff > 0) {
                this.pullDistance = Math.min(diff, this.maxPullDistance);
                if (diff > 10) e.preventDefault(); 
            }
        },
        async handleTouchEnd() {
            if (!this.pulling) return;
            if (this.pullDistance >= 60) {
                this.refreshing = true;
                await this.loadWaveInfo();
                this.refreshing = false;
            }
            this.pulling = false;
            this.pullDistance = 0;
        }
    }
}
</script>

<style scoped>
.cycle-count-operator-container {
    display: flex;
    flex-direction: column;
    height: 100vh;
    background: #f4f7f6;
    overflow-y: auto;
    position: relative;
    overscroll-behavior-y: contain;
}

.pull-to-refresh-indicator {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    overflow: hidden;
    background: rgba(59, 130, 246, 0.1);
    color: #3B82F6;
    z-index: 1000;
    transition: height 0.1s ease;
}

.operator-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: #fff;
    padding: 0.75rem 1rem;
    border-bottom: 1px solid #e2e8f0;
    box-shadow: 0 2px 4px rgba(0,0,0,0.02);
}

.wave-info .label { font-size: 0.65rem; color: #64748b; font-weight: 800; display: block; }
.wave-info .value { font-size: 1.1rem; font-weight: 900; color: #1e293b; }

.workflow-area {
    flex: 1;
    display: flex;
    flex-direction: column;
}

.current-context-banner {
    background: #1e293b;
    color: #fff;
    padding: 1rem;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.context-main { display: flex; align-items: center; gap: 0.75rem; }
.context-main i { font-size: 1.5rem; color: #3b82f6; }
.loc-info { display: flex; flex-direction: column; }
.loc-label { font-size: 0.65rem; color: #94a3b8; font-weight: bold; }
.loc-name { font-size: 1.2rem; font-weight: 900; }
.pending-count { font-size: 0.75rem; background: #334155; padding: 4px 8px; border-radius: 4px; }

.action-bar-top {
    display: flex;
    gap: 0.75rem;
    padding: 0.75rem;
    background: #fff;
    border-bottom: 1px solid #e2e8f0;
}

.scanner-section { flex: 1; }

.quantity-step { padding: 1rem; }
.context-info-compact {
    background: #e2e8f0;
    padding: 0.75rem;
    border-radius: 8px;
    display: flex;
    align-items: center;
    gap: 10px;
    font-weight: 800;
    margin-bottom: 1rem;
}

.quantity-form { display: flex; flex-direction: column; align-items: center; gap: 1.5rem; margin-top: 1rem; }
.quantity-form label { font-weight: 900; font-size: 1.2rem; color: #1e293b; }
.qty-input-wrapper { display: flex; align-items: center; gap: 1rem; }
.qty-btn { width: 60px; height: 60px; font-size: 2rem !important; }
.qty-input { width: 120px; }
:deep(.qty-input input) { text-align: center; font-size: 2.5rem; font-weight: 900; }
.form-actions { display: flex; gap: 1rem; width: 100%; margin-top: 1rem; }
.form-actions button { flex: 1; height: 50px; font-weight: 800; }

.empty-state-container {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 2rem;
    text-align: center;
    gap: 1rem;
}
.success-icon { font-size: 4rem; color: #22c55e; }
.empty-state-container h3 { font-size: 1.5rem; font-weight: 900; margin: 0; }

.session-log {
    background: #1e293b;
    color: #f8fafc;
    padding: 1rem;
    height: 200px;
    display: flex;
    flex-direction: column;
}
.log-title { font-weight: 800; margin-bottom: 0.5rem; border-bottom: 1px solid #334155; padding-bottom: 0.5rem; font-size: 0.8rem; }
.log-items { flex: 1; overflow-y: auto; }
.log-item { display: flex; justify-content: space-between; align-items: center; padding: 0.5rem 0; border-bottom: 1px solid #334155; }
.log-loc { color: #3b82f6; font-size: 0.7rem; font-weight: bold; }
.log-prod { font-size: 0.85rem; display: block; }
.log-qty { font-weight: 900; font-size: 1.2rem; color: #22c55e; }

.locations-modal-content { max-height: 60vh; overflow-y: auto; }
.group-title { font-size: 0.75rem; font-weight: 900; color: #64748b; margin-bottom: 0.75rem; border-left: 4px solid #3b82f6; padding-left: 10px; }
.loc-grid { display: flex; flex-direction: column; gap: 8px; }
.loc-item-modal { display: flex; align-items: center; gap: 10px; padding: 0.75rem; background: #f1f5f9; border-radius: 6px; font-weight: 600; }
.loc-item-modal.done { background: #dcfce7; color: #166534; border-left: 4px solid #22c55e; }
.loc-item-modal.pending { border-left: 4px solid #3b82f6; }

.flex-1 { flex: 1; }
</style>