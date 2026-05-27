<template>
    <div class="test-flow-container">
        <!-- Header con contador -->
        <div v-if="packageCount > 0" class="dock-header-counter">
            <span class="header-title">Traslado a DOCK</span>
            <div class="picked-summary-badge">
                <i class="fa fa-shopping-basket"></i>
                <span>{{ packageCount }}</span>
            </div>
        </div>
        
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
                    icon="fa fa-arrow-left" 
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
                    <i class="fa fa-map-signs confirmation-icon"></i>
                    <h3>Confirmar Traslado a DOCK</h3>
                    <div class="route-summary">
                        <div class="route-point">
                            <span class="label">ORIGEN</span>
                            <span class="value">{{ scannedBin }}</span>
                        </div>
                        <i class="fa fa-arrow-right"></i>
                        <div class="route-point">
                            <span class="label">DESTINO</span>
                            <span class="value">{{ targetDock }}</span>
                        </div>
                    </div>
                    <p v-if="binCarrierName" style="font-size: 0.85rem; color: #3498db; margin-bottom: 5px;">
                        <i class="fa fa-truck"></i> Carrier: <b>{{ binCarrierName }}</b>
                    </p>
                    <p class="packages-alert">Se moverán <b>{{ packageCount }}</b> paquetes en total.</p>
                    <div class="confirmation-buttons">
                        <Button label="Confirmar Envío" icon="fa fa-check" class="p-button-success" @click="confirmDockMove" />
                        <Button label="Corregir DOCK" icon="fa fa-refresh" class="p-button-secondary" @click="cancelDockConfirmation" />
                    </div>
                </div>
            </div>
        </div>

        <div class="buttons-col" v-if="!showDockConfirmation">
            <Button 
                @click="exitFlow"
                class="p-button-text p-button-danger p-button-sm" 
                label="Salir / Finalizar" 
                icon="fa fa-times"
            />
        </div>

        <div class="log-col">
            <div class="log-header">
                Traslado a DOCK
            </div>

            <div class="status-content">
                <div v-if="!scannedBin" class="empty-status">
                    <i class="fa fa-archive status-icon"></i>
                    Esperando escaneo del BIN origen...
                </div>

                <div v-else class="active-status">
                    <div class="bin-scanned">
                        <i class="fa fa-archive me-2"></i> {{ scannedBin }}
                    </div>
                    <!-- Carrier del BIN -->
                    <div v-if="binCarrierName" class="bin-carrier-tag">
                        <i class="fa fa-truck"></i> {{ binCarrierName }}
                    </div>
                    <div class="package-count">
                        <i class="fa fa-check-circle me-1"></i> {{ packageCount }} paquetes detectados
                    </div>
                    
                    <!-- Summary Cards -->
                    <div class="scan-summary-grid" v-if="scanSummary.length > 0" style="margin-bottom: 10px; width: 100%; text-align: left;">
                        <div v-for="item in paginatedScanSummary" :key="item.so_name" class="summary-card">
                            <div class="summary-so">{{ item.so_name }}</div>
                            <div class="summary-progress">
                                <div class="progress-text">{{ item.total_scanned }} / {{ item.total }}</div>
                                <div class="progress-bar">
                                    <div class="progress-fill" :style="{ width: (item.total_scanned / item.total * 100) + '%' }"></div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- Pagination Control for Summary Cards -->
                    <div v-if="summaryTotalPages > 1" class="pagination-container" style="margin-top: 5px; margin-bottom: 15px; width: 100%;">
                        <Button 
                            icon="fa fa-chevron-left" 
                            class="p-button-rounded p-button-text p-button-sm pagination-btn" 
                            :disabled="summaryCurrentPage === 1" 
                            @click="summaryCurrentPage--" 
                        />
                        <span class="pagination-info">
                            Pág. <b>{{ summaryCurrentPage }}</b> de <b>{{ summaryTotalPages }}</b>
                            <small class="pagination-total">({{ scanSummary.length }} órdenes)</small>
                        </span>
                        <Button 
                            icon="fa fa-chevron-right" 
                            class="p-button-rounded p-button-text p-button-sm pagination-btn" 
                            :disabled="summaryCurrentPage === summaryTotalPages" 
                            @click="summaryCurrentPage++" 
                        />
                    </div>

                    <div class="package-list-dock" v-if="packageDetails.length > 0">
                        <div v-for="pkg in paginatedPackageDetails" :key="pkg.name" class="package-item-dock">
                            <i class="fa fa-barcode me-2"></i> {{ pkg.name }} <small>({{ pkg.so }})</small>
                        </div>
                    </div>

                    <!-- Pagination Control -->
                    <div v-if="totalPages > 1" class="pagination-container">
                        <Button 
                            icon="fa fa-chevron-left" 
                            class="p-button-rounded p-button-text p-button-sm pagination-btn" 
                            :disabled="currentPage === 1" 
                            @click="currentPage--" 
                        />
                        <span class="pagination-info">
                            Pág. <b>{{ currentPage }}</b> de <b>{{ totalPages }}</b>
                            <small class="pagination-total">({{ packageDetails.length }} paquetes)</small>
                        </span>
                        <Button 
                            icon="fa fa-chevron-right" 
                            class="p-button-rounded p-button-text p-button-sm pagination-btn" 
                            :disabled="currentPage === totalPages" 
                            @click="currentPage++" 
                        />
                    </div>
                    
                    <div v-if="!showDockConfirmation">
                        <div class="status-instruction">
                            Listo para mover. <br> Escanea el DOCK de destino.
                        </div>
                        <i class="fa fa-arrow-down bounce-icon"></i>
                    </div>
                    <div v-else class="status-confirmed">
                        <i class="fa fa-spin fa-spinner me-2"></i> Esperando confirmación de despacho...
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
            packageDetails: [],
            showDockConfirmation: false,
            targetDock: null,
            binCarrierName: '',
            currentPage: 1,
            summaryCurrentPage: 1,
        }

    },
    computed: {
        totalPages() {
            return Math.ceil(this.packageDetails.length / 4) || 1;
        },
        paginatedPackageDetails() {
            const start = (this.currentPage - 1) * 4;
            return this.packageDetails.slice(start, start + 4);
        },
        scanSummary() {
            const summaryMap = {};
            this.packageDetails.forEach(item => {
                const soName = item.so || 'N/A';
                if (!summaryMap[soName]) {
                    summaryMap[soName] = { 
                        so_name: soName, 
                        total_scanned: 0, 
                        total: item.is_full ? 1 : 0 
                    };
                }
                summaryMap[soName].total_scanned++;
            });
            return Object.values(summaryMap).map(item => {
                if (item.total === 0) {
                    item.total = item.total_scanned;
                }
                return item;
            });
        },
        summaryTotalPages() {
            return Math.ceil(this.scanSummary.length / 4) || 1;
        },
        paginatedScanSummary() {
            const start = (this.summaryCurrentPage - 1) * 4;
            return this.scanSummary.slice(start, start + 4);
        }

    },
    watch: {
        'packageDetails.length'(newVal, oldVal) {
            const maxPages = Math.ceil(newVal / 4) || 1;
            if (this.currentPage > maxPages) {
                this.currentPage = maxPages;
            }
        },
        'scanSummary.length'(newVal, oldVal) {
            const maxPages = Math.ceil(newVal / 4) || 1;
            if (this.summaryCurrentPage > maxPages) {
                this.summaryCurrentPage = maxPages;
            }
        }
    },
    mounted() {
        console.log("Action: Component mounted");
        setTimeout(() => {
            this.ready = true;
            console.log("Action: Component ready state set to true");
        }, 500);
    },
    methods: {
        async validateDestDock(data) {
            console.log("Action: validateDestDock data received:", data);
            try {
                let parsedData = typeof data === 'string' ? JSON.parse(data) : data;
                const dockName = parsedData.name;
                
                let response = await this.store.callOdoo("validate_dock", "", {
                    dock: dockName
                });

                if (response.valid) {
                    // Validar mezcla en el DOCK según lo que hay en el BIN origen
                    const binHasEcommerce = this.packageDetails.some(p => !p.is_full);
                    const binHasFull = this.packageDetails.some(p => p.is_full);

                    if (binHasEcommerce && response.has_full) {
                        this.$toast.add({ 
                            severity: 'error', 
                            summary: 'DOCK con Fulfillment', 
                            detail: 'El DOCK ya contiene productos de Fulfillment y no se pueden mezclar con pedidos.', 
                            life: 5000 
                        });
                        this.scannerKey++;
                        return;
                    }
                    
                    if (binHasFull && response.has_ecommerce) {
                        this.$toast.add({ 
                            severity: 'error', 
                            summary: 'DOCK con pedidos', 
                            detail: 'El DOCK ya contiene pedidos y no se pueden mezclar con productos de Fulfillment.', 
                            life: 5000 
                        });
                        this.scannerKey++;
                        return;
                    }

                    this.targetDock = dockName;
                    this.showDockConfirmation = true;
                    console.log("Action: Showing confirmation screen for dock:", this.targetDock);
                } else {
                    this.$toast.add({ 
                        severity: 'error', 
                        summary: 'DOCK No Válido', 
                        detail: 'La ubicación escaneada no es un DOCK disponible o válido. ' + (response.error || 'Ubicación no encontrada'), 
                        life: 4000 
                    });
                    this.scannerKey++;
                }
            } catch (e) {
                console.log("Action: Error parsing dock data", e);
                this.$toast.add({ 
                    severity: 'error', 
                    summary: 'Error de Lectura QR', 
                    detail: 'El código QR del DOCK no pudo ser interpretado correctamente. ' + (e.message || 'Formato inválido'), 
                    life: 4000 
                });
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
                    if (response.status === "queued") {
                        if (this.$toast) {
                            this.$toast.add({
                                severity: 'info',
                                summary: 'Traslado Encolado',
                                detail: 'Debido a la cantidad de paquetes (>10), el traslado se procesará en segundo plano. Puedes continuar usando la app.',
                                life: 8000
                            });
                        }
                    } else {
                        const isManager = this.store.role && (this.store.role.role === 'WMDs Manager' || (this.store.role.permissions && this.store.role.permissions.includes('WMDs Manager')));
                        if (!isManager) {
                            this.$toast.add({ 
                                severity: 'success', 
                                summary: 'Traslado Exitoso', 
                                detail: `Se han movido ${response.moved_packages} paquetes desde ${this.scannedBin} al DOCK ${this.targetDock}.`, 
                                life: 4000 
                            });
                        }
                    }
                    this.resetScan();
                    this.showDockConfirmation = false;
                    this.targetDock = null;
                } else {

                    console.log("Action: Move failed", response.error);
                    this.$toast.add({ 
                        severity: 'error', 
                        summary: 'Error en Traslado', 
                        detail: 'No se pudo completar el movimiento al DOCK. ' + (response.error || 'Error en el servidor'), 
                        life: 4000 
                    });
                }

            } catch (e) {
                console.log("Action: Error in confirmDockMove", e);
                this.$toast.add({ 
                    severity: 'error', 
                    summary: 'Error de Conexión', 
                    detail: 'No se pudo establecer comunicación con el servidor. ' + (e.message || 'Error de red'), 
                    life: 4000 
                });
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
            this.packageDetails = [];
            this.binCarrierName = '';
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
    height: calc(100vh - var(--o-we-toolbar-height, 46px));
    padding: 10px;
    box-sizing: border-box;
    overflow-y: auto;
    gap: 1rem;
    background: #fff;
}

.dock-header-counter {
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: #3498db;
    color: white;
    padding: 8px 15px;
    border-radius: 8px;
}

.header-title {
    font-weight: bold;
    font-size: 0.9rem;
}

.picked-summary-badge {
    background: #111827;
    color: #facc15;
    padding: 4px 12px;
    border-radius: 20px;
    font-weight: 800;
    font-size: 0.9rem;
    display: flex;
    align-items: center;
    gap: 6px;
}

.scanner-col {
    flex: 0 0 auto;
    display: flex;
    gap: 10px;
}

.scanner-wrapper, .confirmation-wrapper {
    flex: 1;
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
    flex: 0 0 auto;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    padding-bottom: 10px;
}

.log-col {
    flex: 1;
    background: #2c3e50;
    border-radius: 8px;
    padding: 15px;
    color: #ecf0f1;
    min-height: 50vh;
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
    justify-content: flex-start;
    align-items: center;
    gap: 20px;
    overflow: hidden;
    width: 100%;
}

.empty-status {
    text-align: center;
    color: #7f8c8d;
    margin-top: auto;
    margin-bottom: auto;
}

.status-icon {
    font-size: 3rem;
    display: block;
    margin-bottom: 15px;
}

.active-status {
    text-align: center;
    display: flex;
    flex-direction: column;
    align-items: center;
    width: 100%;
    flex: 1;
    overflow: hidden;
}

.bin-scanned {
    font-size: 1.5rem;
    color: #f39c12;
    margin-bottom: 5px;
}

.bin-carrier-tag {
    background: #3498db;
    color: white;
    padding: 4px 12px;
    border-radius: 4px;
    font-size: 0.8rem;
    font-weight: bold;
    display: inline-block;
    margin-bottom: 10px;
}

.package-count {
    font-size: 1rem;
    color: #2ecc71;
    margin-bottom: 10px;
}

.package-list-dock {
    background: #34495e;
    border-radius: 4px;
    padding: 8px;
    margin-bottom: 15px;
    width: 100%;
    text-align: left;
    min-height: 100px;
}

.package-item-dock {
    font-size: 0.9rem;
    padding: 4px 0;
    border-bottom: 1px solid #455a64;
    font-family: monospace;
}

.package-item-dock:last-child {
    border-bottom: none;
}

.package-item-dock small {
    color: #bdc3c7;
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

.pagination-container {
    display: flex;
    justify-content: center;
    align-items: center;
    gap: 15px;
    margin-top: 12px;
    padding: 8px;
    background: #34495e;
    border-radius: 6px;
    border: 1px solid #455a64;
}

.pagination-info {
    font-size: 0.9rem;
    color: #ecf0f1;
    display: flex;
    align-items: center;
    gap: 5px;
}

.pagination-total {
    color: #bdc3c7;
    margin-left: 5px;
}

.pagination-btn {
    color: #ecf0f1 !important;
}

.pagination-btn:disabled {
    color: #7f8c8d !important;
    opacity: 0.5;
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
</style>