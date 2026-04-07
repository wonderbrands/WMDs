<template>
    <div class="cycle-count-operator-container">
        
        <!-- Header Info -->
        <div class="operator-header">
            <div v-if="step !== 'quantity'" class="wave-info">
                <span class="label">OLA:</span>
                <span class="value">{{ waveName }}</span>
            </div>
            <div v-else class="context-info-header">
                <div class="header-item">
                    <i class="fa fa-map-marker"></i>
                    <span class="header-val">{{ current_location.name }}</span>
                    <i class="fa fa-pencil edit-icon" @click="resetToLocation"></i>
                </div>
                <div class="header-item">
                    <i class="fa fa-box"></i>
                    <span class="header-val">{{ current_product.sku || current_product.name }}</span>
                </div>
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
            
            <!-- Step 1: Scan Location -->
            <div v-if="step === 'location'" class="step-container">
                <!-- Pending Locations Info -->
                <div class="pending-summary" v-if="pending_locations.length > 0">
                    <div class="summary-title">Próximas Ubicaciones ({{ pending_locations.length }})</div>
                    <div class="summary-list">
                        <span v-for="loc in pending_locations.slice(0, 3)" :key="loc.id" class="loc-badge">
                            {{ loc.name }}
                        </span>
                        <span v-if="pending_locations.length > 3" class="loc-badge more">
                            +{{ pending_locations.length - 3 }} más
                        </span>
                    </div>
                </div>
                <div class="pending-summary completed" v-else>
                    <div class="summary-title">¡Todas las ubicaciones contadas!</div>
                </div>

                <div class="scanner-section">
                    <BarcodeScannerComponent 
                        :key="scannerKey"
                        instructions="Escanea la UBICACIÓN a contar"
                        :onScan="(data) => handleLocationScan(data)"
                    />
                </div>
            </div>

            <!-- Step 2: Scan Product -->
            <div v-else-if="step === 'product'" class="step-container">
                <div class="current-context">
                    <div class="context-item">
                        <i class="fa fa-map-marker"></i>
                        <span>{{ current_location.name }}</span>
                        <Button icon="fa fa-pencil" class="p-button-rounded p-button-warning p-button-sm ml-auto" @click="resetToLocation" label="Cambiar" />
                    </div>
                    <div class="mt-2 flex justify-content-center">
                        <Button 
                            label="UBICACIÓN VACÍA" 
                            icon="fa fa-trash" 
                            severity="danger" 
                            class="p-button-sm"
                            @click="markEmpty"
                            :loading="loading"
                        />
                    </div>
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
            step: 'location', // location, product, quantity
            current_location: { id: null, name: '' },
            current_product: { id: null, name: '', sku: '' },
            quantity: 0,
            session_log: [],
            waveId: null,
            waveName: 'Cargando...',
            locations_list: [], // [{id, name, status}]
            showLocationsModal: false
        }
    },
    computed: {
        pending_locations() {
            return this.locations_list.filter(l => l.status === 'pending');
        },
        done_locations() {
            return this.locations_list.filter(l => l.status === 'done');
        }
    },
    async mounted() {
        this.waveId = this.store.mandatory_uncompleted.component_props?.cc_id;
        if (!this.waveId) {
            this.$toast.add({ 
                severity: 'error', 
                summary: 'Error de Inicialización', 
                detail: 'No se pudo recuperar el identificador de la ola de conteo. Por favor, reintente desde el menú principal.', 
                life: 5000 
            });
            this.exitFlow();
            return;
        }
        
        // Cargar nombre de la ola si es necesario, o usar el que viene
        // Por ahora asumimos que el store o props lo tienen o lo recuperamos
        this.waveName = "Cargando...";
        await this.loadWaveInfo();
        
        localStorage.removeItem("mandatory_uncompleted");
        this.ready = true;
    },
    methods: {
        async loadWaveInfo() {
            // Podríamos llamar a un endpoint para obtener detalles de la ola
            // Por simplicidad, si no tenemos el nombre lo dejamos así o lo buscamos
            let res = await this.store.callOdoo("get_cycle_count_details_minimal", "", { wave_id: this.waveId });
            if (res && res.ok) {
                this.waveName = res.name;
                this.locations_list = res.locations || [];
            }
        },

        async handleLocationScan(data) {
            console.log("Location Scanned:", data);
            try {
                let res = await this.store.callOdoo("validate_cycle_count_location", "", {
                    wave_id: this.waveId,
                    location_name: data
                });

                if (res.ok) {
                    const isDone = this.done_locations.some(l => l.id === res.location_id);
                    if (isDone) {
                        this.$toast.add({ 
                            severity: 'warn', 
                            summary: 'Ubicación ya contada', 
                            detail: 'Esta ubicación ya fue procesada y no puede volver a escanearse.', 
                            life: 4000 
                        });
                        this.scannerKey++;
                        return;
                    }

                    this.current_location = {
                        id: res.location_id,
                        name: res.location_name
                    };
                    this.step = 'product';
                    this.scannerKey++;
                } else {
                    this.$toast.add({ 
                        severity: 'error', 
                        summary: 'Ubicación Inválida', 
                        detail: (res.error || 'La ubicación escaneada no es válida para esta ola.'), 
                        life: 4000 
                    });
                    this.scannerKey++;
                }
            } catch (e) {
                this.$toast.add({ 
                    severity: 'error', 
                    summary: 'Error de Validación', 
                    detail: (e.message || 'Error al validar la ubicación.'), 
                    life: 4000 
                });
                this.scannerKey++;
            }
        },

        async handleProductScan(data) {
            console.log("Product Scanned:", data);
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
        },

        async markEmpty() {
            const isLast = this.pending_locations.length === 1 && this.pending_locations[0].id === this.current_location.id;
            const confirmMsg = isLast 
                ? "Si se pone esta ubicación vacía, se cerrará la ola en automático ya que es la última. ¿Desea continuar?"
                : `¿Confirmas que la ubicación ${this.current_location.name} está totalmente vacía?`;

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
                            detail: `Se ha registrado correctamente que la ubicación ${this.current_location.name} no contiene stock.`, 
                            life: 3000 
                        });
                    }
                    
                    // Update local list status
                    let loc = this.locations_list.find(l => l.id === this.current_location.id);
                    if (loc) loc.status = 'done';

                    // Update local session log
                    this.session_log.unshift({
                        location: this.current_location.name,
                        product: '(UBICACIÓN VACÍA)',
                        qty: 0
                    });

                    if (isLast) {
                        // Automáticamente finalizar ola
                        await this.finishWave(true);
                    } else {
                        // Reset to location step to scan next location
                        this.resetToLocation();
                    }
                } else {
                    this.$toast.add({ 
                        severity: 'error', 
                        summary: 'Error de Registro', 
                        detail: (res.error || 'No se pudo marcar la ubicación como vacía.'), 
                        life: 4000 
                    });
                }
            } catch (e) {
                this.$toast.add({ 
                    severity: 'error', 
                    summary: 'Error de Comunicación', 
                    detail: (e.message || 'Error al completar la acción de vaciado.'), 
                    life: 4000 
                });
            } finally {
                this.loading = false;
            }
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
                            detail: `Se registró un conteo de ${this.quantity} para el producto ${this.current_product.sku || this.current_product.name}.`, 
                            life: 2000 
                        });
                    }
                    
                    // Update local list status
                    let loc = this.locations_list.find(l => l.id === this.current_location.id);
                    if (loc) loc.status = 'done';

                    // Agregar al log local
                    this.session_log.unshift({
                        location: this.current_location.name,
                        product: this.current_product.sku || this.current_product.name,
                        qty: this.quantity
                    });

                    // Limpiar producto y volver a escanear producto (manteniendo ubicación)
                    this.current_product = { id: null, name: '', sku: '' };
                    this.quantity = 0;
                    this.step = 'product';
                    this.scannerKey++;
                } else {
                    this.$toast.add({ 
                        severity: 'error', 
                        summary: 'Error al Guardar', 
                        detail: (res.error || 'Error al guardar el conteo.'), 
                        life: 4000 
                    });
                }
            } catch (e) {
                this.$toast.add({ 
                    severity: 'error', 
                    summary: 'Error de Conexión', 
                    detail: (e.message || 'Error al enviar el conteo.'), 
                    life: 4000 
                });
            } finally {
                this.loading = false;
            }
        },

        async finishWave(autoFinish = false) {
            if (this.pending_locations.length > 0) {
                this.$toast.add({ 
                    severity: 'warn', 
                    summary: 'Ubicaciones Pendientes', 
                    detail: `No es posible finalizar la ola mientras existan ubicaciones por contar. Quedan ${this.pending_locations.length} pendientes.`, 
                    life: 5000 
                });
                return;
            }
            if (!autoFinish && !confirm("¿Estás seguro de que quieres finalizar esta ola? Ya no podrás registrar más productos.")) return;
            this.loading = true;
            try {
                let res = await this.store.callOdoo("finish_cycle_count_wave", "", { wave_id: this.waveId });
                if (res.ok) {
                    const isManager = this.store.role && (this.store.role.role === 'WMDs Manager' || (this.store.role.permissions && this.store.role.permissions.includes('WMDs Manager')));
                    if (!isManager) {
                        this.$toast.add({ 
                            severity: 'success', 
                            summary: 'Ola Finalizada', 
                            detail: 'La ola de conteo ha sido completada exitosamente.', 
                            life: 3000 
                        });
                    }
                    this.store.mandatory_uncompleted.doneMandatory();
                } else {
                    this.$toast.add({ 
                        severity: 'error', 
                        summary: 'Error al Finalizar', 
                        detail: 'No se pudo completar el cierre de la ola. ' + (res.error || 'Error en el servidor'), 
                        life: 4000 
                    });
                }
            } catch (e) {
                this.$toast.add({ 
                    severity: 'error', 
                    summary: 'Error Crítico', 
                    detail: 'Ocurrió un error inesperado al intentar finalizar la ola. ' + (e.message || 'Error desconocido'), 
                    life: 4000 
                });
            } finally {
                this.loading = false;
            }
        },

        resetToLocation() {
            this.current_location = { id: null, name: '' };
            this.current_product = { id: null, name: '', sku: '' };
            this.step = 'location';
            this.scannerKey++;
        },

        exitFlow() {
            if (this.step !== 'location') {
                if (!confirm("¿Estás seguro de que quieres salir? Se perderá el progreso de la ubicación actual si no has confirmado.")) {
                    return;
                }
            }
            this.store.mandatory_uncompleted.doneMandatory();
        }
    }
}
</script>

<style scoped>
.cycle-count-operator-container {
    display: flex;
    flex-direction: column;
    min-height: 100%;
    padding: 10px;
    box-sizing: border-box;
    background: #f4f7f6;
    gap: 10px;
    overflow-y: auto;
}

.operator-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: #fff;
    padding: 10px 15px;
    border-radius: 8px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.05);
}

.wave-info .label {
    font-size: 0.7rem;
    color: #888;
    font-weight: bold;
    display: block;
}

.wave-info .value {
    font-size: 1rem;
    font-weight: 800;
    color: #2c3e50;
}

.context-info-header {
    display: flex;
    flex-direction: column;
    gap: 2px;
}

.header-item {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 0.85rem;
    font-weight: bold;
    color: #2c3e50;
}

.header-item i {
    color: #3498db;
    font-size: 0.8rem;
}

.header-val {
    max-width: 150px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.edit-icon {
    cursor: pointer;
    color: #f39c12 !important;
    margin-left: 5px;
}

.header-actions {
    display: flex;
    gap: 5px;
}

.workflow-area {
    flex: 2;
    background: #fff;
    border-radius: 8px;
    overflow: hidden;
    display: flex;
    flex-direction: column;
}

.step-container {
    height: 100%;
    display: flex;
    flex-direction: column;
}

.pending-summary {
    background: #fff9c4;
    padding: 10px;
    border-bottom: 2px solid #fbc02d;
}

.pending-summary.completed {
    background: #c8e6c9;
    border-bottom-color: #4caf50;
    text-align: center;
}

.summary-title {
    font-size: 0.75rem;
    font-weight: bold;
    color: #5d4037;
    margin-bottom: 5px;
    text-transform: uppercase;
}

.pending-summary.completed .summary-title {
    color: #2e7d32;
    font-size: 0.9rem;
    margin-bottom: 0;
}

.summary-list {
    display: flex;
    flex-wrap: wrap;
    gap: 5px;
}

.loc-badge {
    background: #fbc02d;
    color: #000;
    font-size: 0.75rem;
    font-weight: bold;
    padding: 2px 8px;
    border-radius: 12px;
}

.loc-badge.more {
    background: #e0e0e0;
    color: #616161;
}

.scanner-section {
    flex: 1;
}

.current-context {
    background: #eef2f3;
    padding: 10px;
    display: flex;
    flex-direction: column;
    gap: 5px;
    border-bottom: 1px solid #ddd;
}

.context-item {
    display: flex;
    align-items: center;
    gap: 10px;
    font-weight: bold;
    color: #34495e;
}

.context-item i {
    color: #3498db;
}

.product-info {
    display: flex;
    flex-direction: column;
}

.product-sku {
    font-size: 0.8rem;
    color: #7f8c8d;
}

.quantity-step {
    padding: 10px;
    justify-content: flex-start;
}

.quantity-form-wrapper {
    flex: 1;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    padding-bottom: 20px;
}

.quantity-form {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 15px;
    margin-top: 10px;
}

.quantity-form label {
    font-weight: bold;
    font-size: 1.1rem;
}

.qty-input-wrapper {
    display: flex;
    align-items: center;
    gap: 10px;
}

.qty-btn {
    width: 50px;
    height: 50px;
    font-size: 1.5rem !important;
    font-weight: bold !important;
}

.qty-input {
    width: 100px;
}

:deep(.qty-input input) {
    text-align: center;
    font-size: 2rem;
    font-weight: bold;
}

.form-actions {
    display: flex;
    gap: 20px;
    width: 100%;
    justify-content: center;
    margin-top: 10px;
}

.session-log {
    flex: 1;
    background: #2c3e50;
    color: #ecf0f1;
    border-radius: 8px;
    padding: 15px;
    display: flex;
    flex-direction: column;
    overflow: hidden;
}

.log-title {
    font-weight: bold;
    margin-bottom: 10px;
    border-bottom: 1px solid #555;
    padding-bottom: 5px;
}

.log-items {
    flex: 1;
    overflow-y: auto;
}

.log-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 8px 0;
    border-bottom: 1px solid #3e4f5f;
    font-size: 0.9rem;
}

.log-details {
    display: flex;
    flex-direction: column;
}

.log-loc {
    font-weight: bold;
    color: #3498db;
    font-size: 0.8rem;
}

.log-qty {
    font-weight: bold;
    font-size: 1.2rem;
    color: #2ecc71;
}

.empty-log {
    text-align: center;
    color: #95a5a6;
    margin-top: 20px;
    font-style: italic;
}

/* Modal Styles */
.locations-modal-content {
    max-height: 60vh;
    overflow-y: auto;
}

.location-group {
    display: flex;
    flex-direction: column;
}

.group-title {
    font-size: 0.8rem;
    font-weight: bold;
    color: #757575;
    margin-bottom: 10px;
    border-left: 4px solid #3498db;
    padding-left: 10px;
}

.loc-grid {
    display: flex;
    flex-direction: column;
    gap: 8px;
}

.loc-item-modal {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px;
    background: #f5f5f5;
    border-radius: 6px;
    font-size: 0.9rem;
}

.loc-item-modal i {
    font-size: 1rem;
}

.loc-item-modal.pending {
    border-left: 4px solid #fbc02d;
}

.loc-item-modal.pending i {
    color: #fbc02d;
}

.loc-item-modal.done {
    border-left: 4px solid #4caf50;
    background: #e8f5e9;
    color: #2e7d32;
}

.loc-item-modal.done i {
    color: #4caf50;
}

.empty-msg {
    color: #9e9e9e;
    font-style: italic;
    font-size: 0.85rem;
    padding: 10px;
}
</style>