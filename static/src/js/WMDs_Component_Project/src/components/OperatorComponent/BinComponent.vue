<template>
    <div class="test-flow-container">
        
        <div class="scanner-col">
            <div v-if="ready && !scan_bin" class="scanner-wrapper">
                <BarcodeScannerComponent 
                    :key="scannerKey"
                    context="scan_so"
                    instructions="Escanea la etiqueta de orden SO"
                    :onScan="(data) => serachAndValidateSO(data)"
                />
            </div>
            <div v-else-if="ready && scan_bin" class="scanner-wrapper">
                <Button 
                    icon="pi pi-arrow-left" 
                    @click="backToScanSO" 
                    class="p-button-rounded p-button-secondary back-button" 
                />
                <QRScannerComponent 
                    instructions="Escanea la ubicación BIN"
                    :onScan="(data) => validateBin(data)"
                />
            </div>
        </div>

        <div class="buttons-col">
            <Button v-if="so.length > 0 && !scan_bin"
                @click="goToScanBin"
                class="p-button-success p-button-sm" 
                label="Trasladar a BIN" 
                icon="pi pi-send"
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
                    <span class="log-title">Órdenes escaneadas: {{ so.length }}</span>
                    <Button icon="pi pi-trash" class="p-button-danger p-button-text p-button-sm" label="Limpiar Todo" @click="clearAllOrders" v-if="so.length > 0"/>
                </div>
            </div>

            <div class="log-list">
                <div v-for="(order, index) in so" :key="index" class="log-item">
                    <div>
                        <i class="pi pi-barcode barcode-icon"></i>
                        {{ order }}
                    </div>
                    <Button icon="pi pi-times" class="p-button-rounded p-button-danger p-button-text" @click="removeOrder(index)" />
                </div>
                <div v-if="so.length === 0" class="empty-log">
                    <i class="pi pi-search search-icon"></i>
                    Esperando escaneo de guía...
                </div>
            </div>
        </div>
    </div>
</template>

<script>
import QRScannerComponent from '../QRScannerComponent/QRScannerComponent.vue';
import BarcodeScannerComponent from '../QRScannerComponent/BarcodeScannerComponent.vue';
import Button from 'primevue/button';
import { useGeneralStore } from "../../store/index";

export default {
    name: "BinComponent",
    components: {
        QRScannerComponent,
        BarcodeScannerComponent,
        Button
    },
    data() {
        return {
            store: useGeneralStore(),
            scan_bin: false,
            so: [],
            ready: false,
            scannerKey: 0
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
        async serachAndValidateSO(data) {
            console.log("Action: serachAndValidateSO triggered with data:", data);
            try {
                if (this.so.includes(data)) {
                    console.log("Action: Duplicate SO detected, restarting scanner");
                    this.restartScanner();
                    return;
                }

                console.log("Action: Calling Odoo validate_attachment_guide");
                let response = await this.store.callOdoo("validate_attachment_guide", "", {
                    attachment_id: data,
                });

                if (response.valid) {
                    console.log("Action: Validation successful, pushing SO to array");
                    this.so.push(data);
                }
                
                this.restartScanner();
            } catch (e) {
                console.log("Action: Error in serachAndValidateSO", e);
                this.restartScanner();
            }
        },
        restartScanner() {
            console.log("Action: restartScanner triggered");
            this.scannerKey++;
        },
        exitFlow() {
            console.log("Action: exitFlow triggered");
            if (this.so.length > 0) {
                if (!confirm("Tienes órdenes pendientes de mover. ¿Estás seguro de que quieres salir?")) {
                    console.log("Action: exitFlow cancelled by user");
                    return;
                }
            }
            console.log("Action: Clearing data and finalizing flow");
            this.so = [];
            this.scan_bin = false;
            this.store.mandatory_uncompleted.doneMandatory();
        },
        async validateBin(data) {
            console.log("Action: validateBin triggered with data:", data);
            if (this.so.length === 0) {
                console.log("Action: No SOs to move, returning");
                return;
            }
            
            try {
                let parsedData = typeof data === 'string' ? JSON.parse(data) : data;
                let nameToValidate = parsedData.name;

                console.log("Action: Calling Odoo move_to_bin with bin:", nameToValidate);
                let response = await this.store.callOdoo("move_to_bin", "", {
                    bin: nameToValidate,
                    operator: this.store.role.email,
                    orders: this.so
                });

                if (response.ok) {
                    console.log("Action: move_to_bin successful");
                    this.so = [];
                    this.scan_bin = false;
                    this.scannerKey++; 
                }
            } catch (e) {
                console.log("Action: Error in validateBin", e);
                this.$toast.add({ severity: 'error', summary: 'Error de Validación', detail: 'No se pudo validar el bin.', life: 3000 });
            }
        },
        backToScanSO() {
            console.log("Action: backToScanSO triggered");
            this.scan_bin = false;
        },
        goToScanBin() {
            console.log("Action: goToScanBin triggered");
            this.scan_bin = true;
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
    height: 100vh;
    max-height: 90%;
    padding: 10px;
    box-sizing: border-box;
}

.scanner-col {
    height: 40%;
    min-height: 250px;
    display: flex;
    gap: 10px;
}

.scanner-wrapper {
    flex: 1;
    overflow: hidden;
    position: relative;
}

.back-button {
    position: absolute;
    top: 10px;
    left: 10px;
    z-index: 100;
}

.buttons-col {
    height: 20%;
    display: flex;
    flex-direction: column;
    gap: 10px;
    justify-content: center;
    align-items: center;
}

.log-col {
    height: 40%;
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
}

.log-title {
    font-weight: bold;
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