<template>
    <div class="test-flow-container" style="display: flex; flex-direction: column; gap: 1rem; height: 100vh; padding: 10px;">
        
        <div class="scanner-section" style="display: flex; gap: 10px; height: 40%;">
            <div style="flex: 1; border: 2px dashed #3498db; border-radius: 8px; overflow: hidden;">
                <QRScannerComponent 
                    context="TEST_QR"
                    instructions="Escáner QR (Prueba)"
                    :onScan="(data) => addLog('QR', data)"
                />
            </div>

            <div style="flex: 1; border: 2px dashed #e67e22; border-radius: 8px; overflow: hidden;">
                <BarcodeScannerComponent 
                    context="TEST_BARCODE"
                    instructions="Escáner Barcode (Prueba)"
                    :onScan="(data) => addLog('BARCODE', data)"
                />
            </div>
        </div>

        <div class="log-section" style="flex: 1; display: flex; flex-direction: column; background: #2c3e50; border-radius: 8px; padding: 15px; color: #ecf0f1; overflow: hidden;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                <h3 style="margin: 0;">Registro de Captura</h3>
                <div>
                    <Button icon="pi pi-trash" class="p-button-danger p-button-sm" label="Limpiar" @click="logs = []" style="margin-right: 10px;"/>
                    <Button icon="pi pi-play" class="p-button-success p-button-sm" label="Log Final" @click="processFinalLog" />
                </div>
            </div>

            <div class="log-list" style="flex: 1; overflow-y: auto; background: #34495e; border-radius: 4px; padding: 10px;">
                <div v-for="(log, index) in logs" :key="index" 
                     style="padding: 5px 0; border-bottom: 1px solid #5d6d7e; font-family: monospace;">
                    <span :style="{ color: log.type === 'QR' ? '#3498db' : '#e67e22' }">[{{ log.type }}]</span>
                    <span style="color: #95a5a6; margin: 0 10px;">{{ log.time }}:</span>
                    <span>{{ log.data }}</span>
                </div>
                <div v-if="logs.length === 0" style="text-align: center; color: #7f8c8d; margin-top: 20px;">
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
            logs: []
        }
    },
    mounted(){
        this.store.mandatory_uncompleted.doneMandatory()
    },
    methods: {
        addLog(type, data) {
            console.log(`Log Registrado (${type}):`, data);
            
            this.logs.unshift({
                type: type,
                data: data,
                time: new Date().toLocaleTimeString()
            });

            this.$forceUpdate();
        },

        processFinalLog() {
            console.log("--- RESULTADO DE LA PRUEBA ---");
            console.table(this.logs);
            alert(`Se capturaron ${this.logs.length} elementos. Revisa la consola.`);
        }
    }
}
</script>