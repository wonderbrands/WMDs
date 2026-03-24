<template>
    <div class="test-flow-container">
        
        <div class="scanner-col">
            <div v-if="ready" class="scanner-wrapper">
                <BarcodeScannerComponent 
                    :key="scannerKey"
                    instructions="Escanea la guía para despacho"
                    :onScan="(data) => searchAndValidateSO(data)"
                />
            </div>
        </div>

        <div class="buttons-col">
            <Button v-if="so.length > 0"
                @click="dispatchToCarrier"
                class="p-button-success p-button-sm" 
                label="Entregar a paquetería" 
                icon="pi pi-truck"
            />
            <Button 
                @click="exitFlow"
                class="p-button-text p-button-danger p-button-sm" 
                label="Salir / Finalizar" 
                icon="pi pi-times"
            />
        </div>

        <div class="log-col">
            <div class="log-header">
                <div class="log-header-info">
                    <span class="log-title">Resumen de Despacho</span>
                    <Button icon="pi pi-trash" class="p-button-danger p-button-text p-button-sm" label="Limpiar Todo" @click="clearAllOrders" v-if="so.length > 0"/>
                </div>
            </div>

            <!-- Visualization of n/total -->
            <div class="scan-summary-grid" v-if="scanSummary.length > 0">
                <div v-for="item in scanSummary" :key="item.so_name" class="summary-card">
                    <div class="summary-so">{{ item.so_name }}</div>
                    <div class="summary-progress">
                        <div class="progress-text">{{ item.total_scanned }} / {{ item.total }}</div>
                        <div class="progress-bar">
                            <div class="progress-fill" :style="{ width: (item.total_scanned / item.total * 100) + '%' }"></div>
                        </div>
                    </div>
                </div>
            </div>

            <div class="log-list">
                <div v-for="(order, index) in so" :key="index" class="log-item">
                    <div>
                        <i class="pi pi-barcode barcode-icon"></i>
                        {{ order.name }}
                        <small class="text-info ml-2">({{ order.current }}/{{ order.total }})</small>
                    </div>
                    <Button icon="pi pi-times" class="p-button-rounded p-button-danger p-button-text" @click="removeOrder(index)" />
                </div>
                
                <div v-if="so.length === 0" class="empty-log">
                    <i class="pi pi-box search-icon"></i>
                    Esperando escaneo de etiqueta EI (SOXXXX/N)...
                </div>
            </div>
        </div>
    </div>
</template>

<script>
import BarcodeScannerComponent from '../QRScannerComponent/BarcodeScannerComponent.vue';
import Button from 'primevue/button';
import { useGeneralStore } from "../../store/index";

export default {
    name: "DispatchComponent",
    components: {
        BarcodeScannerComponent,
        Button
    },
    data() {
        return {
            store: useGeneralStore(),
            so: [], // Array of objects: { name, so_name, total, current }
            ready: false,
            scannerKey: 0
        }
    },
    computed: {
        scanSummary() {
            const summaryMap = {};
            this.so.forEach(item => {
                if (!summaryMap[item.so_name]) {
                    summaryMap[item.so_name] = { 
                        so_name: item.so_name, 
                        scanned: item.processed_count || 0, 
                        total: item.total,
                        newly_scanned: 0
                    };
                }
                summaryMap[item.so_name].newly_scanned++;
            });
            
            const result = Object.values(summaryMap).map(item => {
                return {
                    ...item,
                    total_scanned: item.scanned + item.newly_scanned
                };
            });
            return result;
        }
    },
    mounted() {
        console.log("Action: Component mounted");
        localStorage.removeItem("mandatory_uncompleted");
        setTimeout(() => {
            this.ready = true;
            console.log("Action: Component ready state set to true");
        }, 500);
    },
    methods: {
        async searchAndValidateSO(data) {
            console.log("Action: searchAndValidateSO triggered with data:", data);
            try {
                if (this.so.some(o => o.name === data)) {
                    console.log("Action: Duplicate guide detected, restarting scanner");
                    this.restartScanner();
                    return;
                }

                console.log("Action: Calling Odoo validate_attachment_guide");
                let response = await this.store.callOdoo("validate_attachment_guide", "", {
                    attachment_id: data,
                });

                if (response.valid) {
                    if (response.state && response.state.dispatched) {
                        console.log("Action: Guide already dispatched");
                        if(this.$toast) {
                            this.$toast.add({ severity: 'error', summary: 'Error', detail: 'Esta guía ya ha sido despachada.', life: 3000 });
                        }
                    } else if (response.state && !response.state.on_dock) {
                        console.log("Action: Guide not on dock");
                        if(this.$toast) {
                            this.$toast.add({ severity: 'error', summary: 'Error', detail: 'Esta guía no está en un DOCK.', life: 3000 });
                        }
                    } else {
                        console.log("Action: Validation successful, pushing to array");
                        this.so.push({
                            name: response.name,
                            so_name: response.so,
                            total: response.total,
                            current: response.current,
                            processed_count: response.processed_count || 0
                        });
                    }
                } else {
                    console.log("Action: Validation failed");
                    if(this.$toast) {
                        this.$toast.add({ severity: 'error', summary: 'Guía Inválida', detail: 'La guía no es válida para despacho.', life: 3000 });
                    }
                }
                
                this.restartScanner();
            } catch (e) {
                console.log("Action: Error in searchAndValidateSO", e);
                this.restartScanner();
            }
        },
        restartScanner() {
            console.log("Action: restartScanner triggered");
            this.scannerKey++;
        },
        async dispatchToCarrier() {
            console.log("Action: dispatchToCarrier triggered");
            if (this.so.length === 0) {
                console.log("Action: No guides to dispatch, returning");
                return;
            }
            
            try {
                const picks_ids = this.so.map(o => o.name);
                console.log("Action: Calling Odoo dispatch_orders with picks_ids:", picks_ids);
                let response = await this.store.callOdoo("dispatch_orders", "", {
                    operator_login: this.store.role.email,
                    picks_ids: picks_ids 
                });

                if (response.status === "success") {
                    console.log("Action: Dispatch successful");
                    if (response.warning) {
                        console.log("Action: Dispatch completed with warning:", response.warning);
                        this.$toast.add({ 
                            severity: 'warn', 
                            summary: 'Entrega Parcial', 
                            detail: response.warning, 
                            life: 6000 
                        });
                    } else {
                        console.log("Action: Dispatch fully completed");
                        this.$toast.add({ 
                            severity: 'success', 
                            summary: 'Éxito', 
                            detail: 'Todas las órdenes han sido completadas y cerradas.', 
                            life: 3000 
                        });
                    }

                    this.so = [];
                    this.restartScanner(); 
                } else {
                    console.log("Action: Dispatch returned non-success status", response);
                    throw new Error(response.message || "Error desconocido");
                }
            } catch (e) {
                console.log("Action: Error in dispatchToCarrier", e);
                if(this.$toast) {
                    this.$toast.add({ 
                        severity: 'error', 
                        summary: 'Error de Despacho', 
                        detail: e.message || 'No se pudo completar la entrega.', 
                        life: 4000 
                    });
                }
            }
        },       
        exitFlow() {
            console.log("Action: exitFlow triggered");
            if (this.so.length > 0) {
                if (!confirm("Tienes guías escaneadas sin entregar a paquetería. ¿Estás seguro de que quieres salir?")) {
                    console.log("Action: exitFlow cancelled by user");
                    return;
                }
            }
            console.log("Action: Finalizing flow");
            this.so = [];
            this.store.mandatory_uncompleted.doneMandatory();
        },
        clearAllOrders() {
            console.log("Action: clearAllOrders triggered");
            this.so = [];
        },
        removeOrder(index) {
            console.log("Action: removeOrder triggered for index:", index);
            this.so.splice(index, 1);
        }
    }
}
</script>

<style scoped>
.test-flow-container {
    display: flex;
    flex-direction: column;
    gap: 1rem;
    height: 80vh;
    padding: 10px;
    box-sizing: border-box;
}

.scanner-col {
    height: 30%;
    display: flex;
    gap: 10px;
}

.scanner-wrapper {
    flex: 1;
    overflow: hidden;
    position: relative;
}

.buttons-col {
    height: 10%;
    display: flex;
    flex-direction: column;
    gap: 10px;
    justify-content: center;
    align-items: center;
}

.log-col {
    height: 60%;
    display: flex;
    flex-direction: column;
    background: #2c3e50;
    border-radius: 8px;
    padding: 15px;
    color: #ecf0f1;
    overflow: hidden;
}

.log-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 10px;
}

.log-header-info {
    display: flex;
    align-items: center;
    gap: 10px;
    width: 100%;
    justify-content: space-between;
}

.log-title {
    font-weight: bold;
}

.scan-summary-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
    gap: 8px;
    margin-bottom: 10px;
    padding: 5px;
}

.summary-card {
    background: #34495e;
    padding: 8px;
    border-radius: 6px;
    border-left: 4px solid #3498db;
}

.summary-so {
    font-size: 0.8rem;
    font-weight: bold;
    color: #bdc3c7;
}

.summary-progress {
    margin-top: 4px;
}

.progress-text {
    font-size: 0.9rem;
    font-weight: 800;
    text-align: right;
    color: #ecf0f1;
}

.progress-bar {
    height: 4px;
    background: #2c3e50;
    border-radius: 2px;
    margin-top: 2px;
    overflow: hidden;
}

.progress-fill {
    height: 100%;
    background: #2ecc71;
    transition: width 0.3s ease;
}

.log-list {
    flex: 1;
    overflow-y: auto;
    background: #34495e;
    border-radius: 4px;
    padding: 10px;
}

.log-item {
    padding: 8px 0;
    border-bottom: 1px solid #5d6d7e;
    font-family: monospace;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.barcode-icon {
    margin-right: 10px;
    color: #f1c40f;
}

.empty-log {
    text-align: center;
    color: #7f8c8d;
    margin-top: 20px;
}

.search-icon {
    font-size: 2rem;
    display: block;
    margin-bottom: 10px;
}
</style>