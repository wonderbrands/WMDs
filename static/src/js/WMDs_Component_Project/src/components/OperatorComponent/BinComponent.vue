<template>
    <div class="test-flow-container" style="display: flex; flex-direction: column; gap: 1rem; height: 100vh; padding: 10px;">
        
        <div class="scanner-section" style="display: flex; gap: 10px; height: 40%; min-height: 250px;">
            <!--
            <div v-if="ready" style="flex: 1; border: 2px dashed #3498db; border-radius: 8px; overflow: hidden; position: relative;">
                <QRScannerComponent 
                    context="TEST_QR"
                    instructions="Escane"
                    :onScan="(data) => addLog('QR', data)"
                />
            </div>

            <div v-if="ready" style="flex: 1; border: 2px dashed #e67e22; border-radius: 8px; overflow: hidden; position: relative;">
                <BarcodeScannerComponent 
                    context="TEST_BARCODE"
                    instructions="Escáner Barcode (Prueba)"
                    :onScan="(data) => addLog('BARCODE', data)"
                />
            -->
            <div v-if="ready && !scan_bin" style="flex: 1; overflow: hidden; position: relative;">
                <BarcodeScannerComponent 
                    context="scan_so"
                    instructions="Escanea la etiqueta de orden SO"
                    :onScan="(data) => serachAndValidateSO(data)"
                />
                <Button v-if="so.length >0"
                class="p-button-success p-button-sm" label="Trasladar a BIN" />
            </div>
            <div v-else-if="ready && scan_bin" style="flex: 1; overflow: hidden; position: relative;">
                <QRScannerComponent 
                    context="scan_bin"
                    instructions="Escanea la ubicación BIN"
                    :onScan="(data) => validateBin(data)"
                />
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
                     style="padding: 5px 0; border-bottom: 1px solid #5d6d7e; font-family: monospace;">
                    <div>
                        {{ order }}
                    </div>
                    <div @click="so.splice(index,1)">
                        x
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
            so:[],
            ready: false
        }
    },
    mounted(){
        localStorage.removeItem("mandatory_uncompleted");
        setTimeout(() => {
            this.ready = true;
        }, 500);
    },
    methods: {
        async serachAndValidateSO(data){
            if (this.so.includes(data)){

            } else {
                let response = await this.store.odoo_middleware.getFromOdoo("validate_attachment_guide'", "",
                    {
                        attachment_id: data,
                    }
                )
                if (response.valid){
                    this.so.push(response.name)
                }
            }
           
        },
        async validateBin(data){
            if (this.so.length === 0){

            } else {
                let response = await this.store.odoo_middleware.getFromOdoo("move_to_bin", "",
                    {
                        bin: data,
                        operator: this.store.role.email,
                        orders: this.so
                    }
                )
                if (response.ok){
                    this.store.mandatory_uncompleted.doneMandatory()
                }
            }
        },
    }
}
</script>