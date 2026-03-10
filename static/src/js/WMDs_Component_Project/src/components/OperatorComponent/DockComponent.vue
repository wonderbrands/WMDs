<template>
    <div class="test-flow-container">
        
        <div class="scanner-col">
            <div v-if="ready && !scannedBin" class="scanner-wrapper">
                <QRScannerComponent 
                    :key="scannerKey"
                    instructions="Escanea el BIN que vas a mover"
                    :onScan="(data) => validateSourceBin(data)"
                />
            </div>
            
            <div v-else-if="ready && scannedBin" class="scanner-wrapper">
                <Button 
                    icon="pi pi-arrow-left" 
                    @click="resetScan" 
                    class="p-button-rounded p-button-secondary back-button" 
                />
                <QRScannerComponent 
                    :key="scannerKey + 1"
                    instructions="Escanea la ubicación DOCK"
                    :onScan="(data) => validateDestDock(data)"
                />
            </div>
        </div>

        <div class="buttons-col">
            <Button 
                @click="exitFlow"
                class="p-button-text p-button-danger p-button-sm" 
                label="Salir / Finalizar" 
                icon="pi pi-times"
            />
        </div>

        <div class="log-col">
            <div class="log-header">
                Traslado a DOCK
            </div>

            <div class="status-content">
                <div v-if="!scannedBin" class="empty-status">
                    <i class="pi pi-box status-icon"></i>
                    Esperando escaneo del BIN origen...
                </div>

                <div v-else class="active-status">
                    <div class="bin-scanned">
                        <i class="pi pi-box me-2"></i> {{ scannedBin }}
                    </div>
                    <div class="package-count">
                        <i class="pi pi-check-circle me-1"></i> {{ packageCount }} paquetes detectados
                    </div>
                    <div class="status-instruction">
                        Listo para mover. <br> Escanea el DOCK de destino.
                    </div>
                    <i class="pi pi-arrow-down bounce-icon"></i>
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
        console.log("Action: Component mounted");
        localStorage.removeItem("mandatory_uncompleted");
        setTimeout(() => {
            this.ready = true;
            console.log("Action: Component ready state set to true");
        }, 500);
    },
    methods: {
        async validateSourceBin(data) {
            console.log("Action: validateSourceBin triggered with data:", data);
            try {
                let parsedData = typeof data === 'string' ? JSON.parse(data) : data;
                let binName = parsedData.name;
                
                console.log("Action: Calling Odoo validate_bin with bin:", binName);
                let response = await this.store.callOdoo("validate_bin", "", {
                    bin: binName
                });

                if (response.valid) {
                    console.log("Action: Source bin validation successful");
                    this.scannedBin = binName;
                    this.packageCount = response.total_packages || 0;
                } else {
                    console.log("Action: Source bin validation failed", response.error);
                    this.$toast.add({ severity: 'error', summary: 'Error', detail: response.error, life: 3000 });
                    this.scannerKey++;
                }
                
            } catch (e) {
                console.log("Action: Error in validateSourceBin", e);
                this.$toast.add({ severity: 'error', summary: 'Error de Conexión', detail: 'No se pudo contactar al servidor.', life: 3000 });
                this.scannerKey++; 
            }
        },

        async validateDestDock(data) {
            console.log("Action: validateDestDock triggered with data:", data);
            if (!this.scannedBin) {
                console.log("Action: No source bin scanned, returning");
                return;
            }
            
            try {
                let parsedData = typeof data === 'string' ? JSON.parse(data) : data;
                let dockName = parsedData.name;

                console.log("Action: Calling Odoo move_bin_to_dock with bin:", this.scannedBin, "and dock:", dockName);
                let response = await this.store.callOdoo("move_bin_to_dock", "", {
                    bin: this.scannedBin,
                    dock: dockName,
                    operator: this.store.role.email
                });

                if (response.ok) {
                    console.log("Action: Move successful");
                    this.$toast.add({ severity: 'success', summary: 'Éxito', detail: `Se movieron ${response.moved_packages} paquetes al DOCK ${dockName}`, life: 3000 });
                    this.resetScan();
                } else {
                    console.log("Action: Move failed", response.error);
                    this.$toast.add({ severity: 'error', summary: 'Error', detail: response.error, life: 3000 });
                    this.scannerKey++;
                }

            } catch (e) {
                console.log("Action: Error in validateDestDock", e);
                this.$toast.add({ severity: 'error', summary: 'Error de Conexión', detail: 'No se pudo contactar al servidor.', life: 3000 });
                this.scannerKey++;
            }
        },

        resetScan() {
            console.log("Action: resetScan triggered");
            this.scannedBin = null;
            this.packageCount = 0;
            this.scannerKey++;
        },

        exitFlow() {
            console.log("Action: exitFlow triggered");
            if (this.scannedBin) {
                if (!confirm("Tienes un movimiento a medias. ¿Seguro que quieres salir?")) {
                    console.log("Action: exitFlow cancelled by user");
                    return;
                }
            }
            console.log("Action: Finalizing flow");
            this.store.mandatory_uncompleted.doneMandatory();
        }
    }
}
</script>

<style scoped>
.test-flow-container {
    display: flex;
    flex-direction: column;
    gap: 1rem;
    height: 90vh;
    max-height: 90%;
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

.back-button {
    position: absolute;
    top: 10px;
    left: 10px;
    z-index: 100;
}

.buttons-col {
    height: 10%;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    padding-bottom: 10px;
}

.log-col {
    height: 60%;
    display: flex;
    flex-direction: column;
    background: #2c3e50;
    border-radius: 8px;
    padding: 15px;
    color: #ecf0f1;
    overflow-y: auto;
}

.log-header {
    text-align: center;
    margin-bottom: 20px;
    font-size: 1.2rem;
    font-weight: bold;
    border-bottom: 1px solid #5d6d7e;
    padding-bottom: 10px;
}

.status-content {
    flex: 1;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    gap: 20px;
}

.empty-status {
    text-align: center;
    color: #7f8c8d;
}

.status-icon {
    font-size: 3rem;
    display: block;
    margin-bottom: 15px;
}

.active-status {
    text-align: center;
}

.bin-scanned {
    font-size: 1.5rem;
    color: #f39c12;
    margin-bottom: 5px;
}

.package-count {
    font-size: 1rem;
    color: #2ecc71;
    margin-bottom: 15px;
}

.status-instruction {
    color: #ecf0f1;
    margin-bottom: 20px;
}

.bounce-icon {
    font-size: 2rem;
    color: #3498db;
    animation: bounce 2s infinite;
}

@keyframes bounce {
  0%, 20%, 50%, 80%, 100% {transform: translateY(0);}
  40% {transform: translateY(-15px);}
  60% {transform: translateY(-7px);}
}
</style>