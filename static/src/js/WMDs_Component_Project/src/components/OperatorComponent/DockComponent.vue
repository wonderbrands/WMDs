<template>
    <div class="test-flow-container">
        
        <div class="scanner-col">
            <div v-if="ready && !scannedBin && !showDockConfirmation" class="scanner-wrapper">
                <QRScannerComponent 
                    :key="scannerKey"
                    context="dock_validate_bin"
                    :extra_data="this"
                    instructions="Escanea el BIN que vas a mover"
                />
            </div>
            
            <div v-else-if="ready && scannedBin && !showDockConfirmation" class="scanner-wrapper">
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

            <div v-else-if="showDockConfirmation" class="confirmation-wrapper">
                <div class="confirmation-content">
                    <i class="pi pi-directions-alt confirmation-icon"></i>
                    <h3>Confirmar Traslado a DOCK</h3>
                    <div class="route-summary">
                        <div class="route-point">
                            <span class="label">ORIGEN</span>
                            <span class="value">{{ scannedBin }}</span>
                        </div>
                        <i class="pi pi-arrow-right"></i>
                        <div class="route-point">
                            <span class="label">DESTINO</span>
                            <span class="value">{{ targetDock }}</span>
                        </div>
                    </div>
                    <p class="packages-alert">Se moverán <b>{{ packageCount }}</b> paquetes en total.</p>
                    <div class="confirmation-buttons">
                        <Button label="Confirmar Envío" icon="pi pi-check" class="p-button-success" @click="confirmDockMove" />
                        <Button label="Corregir DOCK" icon="pi pi-refresh" class="p-button-secondary" @click="cancelDockConfirmation" />
                    </div>
                </div>
            </div>
        </div>

        <div class="buttons-col" v-if="!showDockConfirmation">
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
                    
                    <div v-if="!showDockConfirmation">
                        <div class="status-instruction">
                            Listo para mover. <br> Escanea el DOCK de destino.
                        </div>
                        <i class="pi pi-arrow-down bounce-icon"></i>
                    </div>
                    <div v-else class="status-confirmed">
                        <i class="pi pi-spin pi-spinner me-2"></i> Esperando confirmación de despacho...
                    </div>
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
            packageCount: 0,
            showDockConfirmation: false,
            targetDock: null
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
        validateDestDock(data) {
            console.log("Action: validateDestDock data received:", data);
            try {
                let parsedData = typeof data === 'string' ? JSON.parse(data) : data;
                this.targetDock = parsedData.name;
                this.showDockConfirmation = true;
                console.log("Action: Showing confirmation screen for dock:", this.targetDock);
            } catch (e) {
                console.log("Action: Error parsing dock data", e);
                this.$toast.add({ severity: 'error', summary: 'Error de Lectura', detail: 'Código de DOCK no reconocido.', life: 3000 });
                this.scannerKey++;
            }
        },

        async confirmDockMove() {
            console.log("Action: confirmDockMove triggered");
            try {
                console.log("Action: Calling Odoo move_bin_to_dock with bin:", this.scannedBin, "and dock:", this.targetDock);
                let response = await this.store.callOdoo("move_bin_to_dock", "", {
                    bin: this.scannedBin,
                    dock: this.targetDock,
                    operator: this.store.role.email
                });

                if (response.ok) {
                    console.log("Action: Move successful");
                    this.$toast.add({ severity: 'success', summary: 'Éxito', detail: `Se movieron ${response.moved_packages} paquetes al DOCK ${this.targetDock}`, life: 3000 });
                    this.resetScan();
                    this.showDockConfirmation = false;
                    this.targetDock = null;
                } else {
                    console.log("Action: Move failed", response.error);
                    this.$toast.add({ severity: 'error', summary: 'Error', detail: response.error, life: 3000 });
                }

            } catch (e) {
                console.log("Action: Error in confirmDockMove", e);
                this.$toast.add({ severity: 'error', summary: 'Error de Conexión', detail: 'No se pudo contactar al servidor.', life: 3000 });
            }
        },

        cancelDockConfirmation() {
            console.log("Action: cancelDockConfirmation triggered");
            this.showDockConfirmation = false;
            this.targetDock = null;
            this.scannerKey++;
        },

        resetScan() {
            console.log("Action: resetScan triggered");
            this.scannedBin = null;
            this.packageCount = 0;
            this.showDockConfirmation = false;
            this.targetDock = null;
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
    height: 35%;
    display: flex;
    gap: 10px;
}

.scanner-wrapper, .confirmation-wrapper {
    flex: 1;
    overflow: hidden;
    position: relative;
}

.confirmation-wrapper {
    display: flex;
    justify-content: center;
    align-items: center;
    background: #ffffff;
    border-radius: 8px;
    border: 2px solid #3498db;
    color: #2c3e50;
    padding: 15px;
    overflow-y: auto;
}

.confirmation-content h3 {
    margin: 10px 0;
    color: #2980b9;
}

.confirmation-icon {
    font-size: 2.5rem;
    color: #3498db;
}

.route-summary {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 20px;
    margin: 15px 0;
    padding: 10px;
    background: #f8f9fa;
    border-radius: 4px;
}

.route-point {
    display: flex;
    flex-direction: column;
}

.route-point .label {
    font-size: 0.7rem;
    color: #7f8c8d;
    font-weight: bold;
}

.route-point .value {
    font-size: 1.1rem;
    font-weight: bold;
    color: #2c3e50;
}

.packages-alert {
    font-size: 0.9rem;
    margin-bottom: 15px;
}

.confirmation-buttons {
    display: flex;
    gap: 10px;
    justify-content: center;
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
    flex: 1;
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

.status-confirmed {
    color: #3498db;
    font-weight: bold;
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