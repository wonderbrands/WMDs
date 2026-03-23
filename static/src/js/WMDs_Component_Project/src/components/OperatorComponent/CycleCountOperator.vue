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
                    <i class="pi pi-map-marker"></i>
                    <span class="header-val">{{ current_location.name }}</span>
                    <i class="pi pi-pencil edit-icon" @click="resetToLocation"></i>
                </div>
                <div class="header-item">
                    <i class="pi pi-box"></i>
                    <span class="header-val">{{ current_product.sku || current_product.name }}</span>
                </div>
            </div>
            <Button 
                @click="finishWave"
                class="p-button-text p-button-success p-button-sm mr-2" 
                label="Finalizar" 
                icon="pi pi-check-circle"
                :loading="loading"
            />
            <Button 
                @click="exitFlow"
                class="p-button-text p-button-danger p-button-sm exit-btn" 
                label="Salir" 
                icon="pi pi-times"
            />
        </div>

        <!-- Main Workflow Area -->
        <div class="workflow-area">
            
            <!-- Step 1: Scan Location -->
            <div v-if="step === 'location'" class="step-container">
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
                        <i class="pi pi-map-marker"></i>
                        <span>{{ current_location.name }}</span>
                        <Button icon="pi pi-pencil" class="p-button-rounded p-button-warning p-button-sm ml-auto" @click="resetToLocation" label="Cambiar" />
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
                            <Button label="CANCELAR" icon="pi pi-times" class="p-button-secondary p-button-text" @click="step = 'product'" />
                            <Button label="CONFIRMAR" icon="pi pi-check" class="p-button-success" @click="confirmCount" :loading="loading" />
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
</template>

<script>
import BarcodeScannerComponent from '../QRScannerComponent/BarcodeScannerComponent.vue';
import Button from 'primevue/button';
import InputNumber from 'primevue/inputnumber';
import { useGeneralStore } from "../../store/index";

export default {
    name: "CycleCountOperator",
    components: {
        BarcodeScannerComponent,
        Button,
        InputNumber
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
            waveName: 'Cargando...'
        }
    },
    async mounted() {
        this.waveId = this.store.mandatory_uncompleted.component_props?.cc_id;
        if (!this.waveId) {
            this.$toast.add({ severity: 'error', summary: 'Error', detail: 'No se encontró ID de ola.', life: 3000 });
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
                    this.current_location = {
                        id: res.location_id,
                        name: res.location_name
                    };
                    this.step = 'product';
                    this.scannerKey++;
                } else {
                    this.$toast.add({ severity: 'error', summary: 'Ubicación Inválida', detail: res.error, life: 3000 });
                    this.scannerKey++;
                }
            } catch (e) {
                this.$toast.add({ severity: 'error', summary: 'Error', detail: 'Error al validar ubicación.', life: 3000 });
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
                    this.$toast.add({ severity: 'error', summary: 'Producto no encontrado', detail: res.error, life: 3000 });
                    this.scannerKey++;
                }
            } catch (e) {
                this.$toast.add({ severity: 'error', summary: 'Error', detail: 'Error al validar producto.', life: 3000 });
                this.scannerKey++;
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
                    this.$toast.add({ severity: 'success', summary: 'Registrado', detail: 'Conteo guardado con éxito.', life: 2000 });
                    
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
                    this.$toast.add({ severity: 'error', summary: 'Error', detail: res.error, life: 3000 });
                }
            } catch (e) {
                this.$toast.add({ severity: 'error', summary: 'Error', detail: 'No se pudo guardar el conteo.', life: 3000 });
            } finally {
                this.loading = false;
            }
        },

        async finishWave() {
            if (!confirm("¿Estás seguro de que quieres finalizar esta ola? Ya no podrás registrar más productos.")) return;
            this.loading = true;
            try {
                let res = await this.store.callOdoo("finish_cycle_count_wave", "", { wave_id: this.waveId });
                if (res.ok) {
                    this.$toast.add({ severity: 'success', summary: 'Finalizado', detail: 'Ola completada con éxito.', life: 3000 });
                    this.store.mandatory_uncompleted.doneMandatory();
                } else {
                    this.$toast.add({ severity: 'error', summary: 'Error', detail: res.error, life: 3000 });
                }
            } catch (e) {
                this.$toast.add({ severity: 'error', summary: 'Error', detail: 'No se pudo finalizar la ola.', life: 3000 });
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
    height: 80vh;
    padding: 10px;
    box-sizing: border-box;
    background: #f4f7f6;
    gap: 10px;
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
</style>
