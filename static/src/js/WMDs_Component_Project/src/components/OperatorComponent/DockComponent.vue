<template>
    <div class="test-flow-container" style="display: flex; flex-direction: column; gap: 1rem; height: 100vh; padding: 10px;">
        
        <div class="scanner-section" style="display: flex; gap: 10px; height: 40%; min-height: 250px;">
            
            <div v-if="ready && !scannedBin" style="flex: 1; overflow: hidden; position: relative;">
                <QRScannerComponent 
                    :key="scannerKey"
                    context="scan_bin_source"
                    instructions="Escanea el BIN que vas a mover"
                    :onScan="(data) => validateSourceBin(data)"
                />
            </div>
            
            <div v-else-if="ready && scannedBin" style="flex: 1; overflow: hidden; position: relative;">
                <Button 
                    icon="pi pi-arrow-left" 
                    @click="resetScan" 
                    class="p-button-rounded p-button-secondary" 
                    style="position: absolute; top: 10px; left: 10px; z-index: 100;" 
                />
                <QRScannerComponent 
                    :key="scannerKey + 1"
                    context="scan_dock_dest"
                    instructions="Escanea la ubicación DOCK"
                    :onScan="(data) => validateDestDock(data)"
                />
            </div>

            <div style="display: flex; flex-direction: column; justify-content: flex-end; padding-bottom: 10px;">
                <Button 
                    @click="exitFlow"
                    class="p-button-text p-button-danger p-button-sm" 
                    label="Salir / Finalizar" 
                    icon="pi pi-times"
                />
            </div>
        </div>

        <div class="log-section" style="flex: 1; display: flex; flex-direction: column; background: #2c3e50; border-radius: 8px; padding: 15px; color: #ecf0f1; overflow: hidden;">
            <div style="text-align: center; margin-bottom: 20px; font-size: 1.2rem; font-weight: bold; border-bottom: 1px solid #5d6d7e; padding-bottom: 10px;">
                Traslado a DOCK
            </div>

            <div style="flex: 1; display: flex; flex-direction: column; justify-content: center; align-items: center; gap: 20px;">
                
                <div v-if="!scannedBin" style="text-align: center; color: #7f8c8d;">
                    <i class="pi pi-box" style="font-size: 3rem; display: block; margin-bottom: 15px;"></i>
                    Esperando escaneo del BIN origen...
                </div>

                <div v-else style="text-align: center;">
                    <div style="font-size: 1.5rem; color: #f39c12; margin-bottom: 5px;">
                        <i class="pi pi-box me-2"></i> {{ scannedBin }}
                    </div>
                    <div style="font-size: 1rem; color: #2ecc71; margin-bottom: 15px;">
                        <i class="pi pi-check-circle me-1"></i> {{ packageCount }} paquetes detectados
                    </div>
                    <div style="color: #ecf0f1; margin-bottom: 20px;">
                        Listo para mover. <br> Escanea el DOCK de destino.
                    </div>
                    <i class="pi pi-arrow-down" style="font-size: 2rem; color: #3498db; animation: bounce 2s infinite;"></i>
                </div>
            </div>
        </div>
    </div>
</template>

<script>
import QRScannerComponent from '../QRScannerComponent/QRScannerComponent.vue';
import Button from 'primevue/button';
import { useGeneralStore } from "../../store/index";

export default {
    name: "DockComponent",
    components: {
        QRScannerComponent,
        Button
    },
    data() {
        return {
            store: useGeneralStore(),
            ready: false,
            scannerKey: 0,
            scannedBin: null,
            packageCount: 0
        }
    },
    mounted() {
        localStorage.removeItem("mandatory_uncompleted");
        setTimeout(() => {
            this.ready = true;
        }, 500);
    },
    methods: {
        async validateSourceBin(data) {
            try {
                let parsedData = typeof data === 'string' ? JSON.parse(data) : data;
                let binName = parsedData.name;
                
                this.store.loading = true;

                let response = await this.store.odoo_middleware.getFromOdoo("validate_bin", "", {
                    bin: binName
                });

                if (response.valid) {
                    this.scannedBin = binName;
                    this.packageCount = response.total_packages || 0;
                } else {
                    alert(`Error: ${response.error}`);
                    this.scannerKey++;
                }
                
            } catch (e) {
                console.error(e);
                alert("Error de conexión con el servidor.");
                this.scannerKey++; 
            } finally {
                this.store.loading = false;
            }
        },

        async validateDestDock(data) {
            if (!this.scannedBin) return;
            
            try {
                let parsedData = typeof data === 'string' ? JSON.parse(data) : data;
                let dockName = parsedData.name;

                this.store.loading = true; 

                let response = await this.store.odoo_middleware.getFromOdoo("move_bin_to_dock", "", {
                    bin: this.scannedBin,
                    dock: dockName,
                    operator: this.store.role.email
                });

                if (response.ok) {
                    alert(`Éxito: Se movieron ${response.moved_packages} paquetes al DOCK ${dockName}`);
                    this.resetScan();
                } else {
                    alert(`Error: ${response.error}`);
                    this.scannerKey++;
                }

            } catch (e) {
                console.error(e);
                alert("Error de conexión con el servidor.");
                this.scannerKey++;
            } finally {
                this.store.loading = false;
            }
        },

        resetScan() {
            this.scannedBin = null;
            this.packageCount = 0;
            this.scannerKey++;
        },

        exitFlow() {
            if (this.scannedBin) {
                if (!confirm("Tienes un movimiento a medias. ¿Seguro que quieres salir?")) {
                    return;
                }
            }
            this.store.mandatory_uncompleted.doneMandatory();
        }
    }
}
</script>

<style scoped>
@keyframes bounce {
  0%, 20%, 50%, 80%, 100% {transform: translateY(0);}
  40% {transform: translateY(-15px);}
  60% {transform: translateY(-7px);}
}
</style>