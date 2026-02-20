<template>
    <div class="test-flow-container" style="display: flex; flex-direction: column; gap: 1rem; height: 100vh; padding: 10px;">
        
        <div class="scanner-section" style="display: flex; gap: 10px; height: 40%; min-height: 250px;">
            <div v-if="ready && !scan_bin" style="flex: 1; overflow: hidden; position: relative;">
                <BarcodeScannerComponent 
                    :key="scannerKey"
                    context="scan_so"
                    instructions="Escanea la etiqueta de orden SO"
                    :onScan="(data) => serachAndValidateSO(data)"
                />
            </div>
            <div v-else-if="ready && scan_bin" style="flex: 1; overflow: hidden; position: relative;">
                <QRScannerComponent 
                    context="scan_bin"
                    instructions="Escanea la ubicación BIN"
                    :onScan="(data) => validateBin(data)"
                />
            </div>
            <div v-if="so.length > 0 && !scan_bin" style="display:flex; align-items:center;">
                 <Button @click="scan_bin = true"
                    class="p-button-success p-button-sm" label="Trasladar a BIN" />
            </div>
        </div>

        <div class="log-section" style="flex: 1; display: flex; flex-direction: column; background: #2c3e50; border-radius: 8px; padding: 15px; color: #ecf0f1; overflow: hidden;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                <div>
                    <Button icon="pi pi-trash" class="p-button-danger p-button-sm" label="Limpiar" @click="so = []" style="margin-right: 10px;"/>
                </div>
            </div>

            <div class="log-list" style="flex: 1; overflow-y: auto; background: #34495e; border-radius: 4px; padding: 10px;">
                <div v-for="(order, index) in so" :key="index" 
                     style="padding: 5px 0; border-bottom: 1px solid #5d6d7e; font-family: monospace; display: flex; justify-content: space-between;">
                    <div>
                        {{ order }}
                    </div>
                    <div @click="so.splice(index,1)" style="cursor: pointer; color: #e74c3c; font-weight: bold; padding: 0 10px;">
                        X
                    </div>
                </div>
                <div v-if="so.length === 0" style="text-align: center; color: #7f8c8d; margin-top: 20px;">
                    Esperando escaneo...
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
        localStorage.removeItem("mandatory_uncompleted");
        setTimeout(() => {
            this.ready = true;
        }, 500);
    },
    methods: {
        async serachAndValidateSO(data) {
            try {
                if (this.so.includes(data)) {
                    this.restartScanner();
                    return;
                }

                let response = await this.store.odoo_middleware.getFromOdoo("validate_attachment_guide", "", {
                    attachment_id: data,
                });

                if (response.valid) {
                    this.so.push(data);
                }
                
                this.restartScanner();

            } catch (e) {
                console.log("Error:", e);
                this.restartScanner();
            }
        },
        restartScanner() {
            this.scannerKey++;
        },
        async validateBin(data) {
            if (this.so.length === 0) return;
            
            try {
                let parsedData = typeof data === 'string' ? JSON.parse(data) : data;
                let nameToValidate = parsedData.name;

                let response = await this.store.odoo_middleware.getFromOdoo("move_to_bin", "", {
                    bin: nameToValidate,
                    operator: this.store.role.email,
                    orders: this.so
                });

                if (response.ok) {
                    this.store.mandatory_uncompleted.doneMandatory();
                    this.so = [];
                    this.scan_bin = false;
                    this.scannerKey++; // Reset for next cycle
                }
            } catch (e) {
                console.error("Bin validation error", e);
            }
        }
    }
}
</script>