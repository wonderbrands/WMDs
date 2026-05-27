<template>
    <div class="test-flow-container">

        <!-- ── Selección de Carrier (antes de escanear) ── -->
        <div v-if="!selectedCarrierId && !loadingCarriers" class="carrier-select-overlay">
            <div class="carrier-select-card">
                <i class="fa fa-truck" style="font-size: 2.5rem; color: #3498db; margin-bottom: 10px;"></i>
                <h3 style="margin: 0 0 5px;">Seleccione el Carrier</h3>
                <span style="font-size: 0.8rem; color: #95a5a6; margin-bottom: 15px;">
                    Los escaneos se asociarán a este carrier
                </span>
                <select v-model="carrierIdChoice" class="carrier-dropdown">
                    <option :value="null" disabled>-- Seleccionar --</option>
                    <option v-for="c in carrierList" :key="c.id" :value="c.id">{{ c.name }}</option>
                </select>
                <Button
                    label="Continuar"
                    icon="fa fa-check"
                    class="p-button-success"
                    :disabled="!carrierIdChoice"
                    @click="confirmCarrier"
                />
                <Button
                    label="Cancelar"
                    icon="fa fa-times"
                    class="p-button-text p-button-danger p-button-sm"
                    @click="exitFlow"
                    style="margin-top: 5px;"
                />
            </div>
        </div>

        <!-- ── Contenido principal (solo si hay carrier) ── -->
        <template v-if="selectedCarrierId">

            <!-- Carrier indicator -->
            <div class="carrier-indicator flex justify-content-between align-items-center">
                <div>
                    <i class="fa fa-truck"></i> {{ selectedCarrierName }}
                    <Button
                        v-if="so.length === 0 && !scan_bin && !showConfirmation"
                        icon="fa fa-pencil"
                        class="p-button-text p-button-sm"
                        style="color: white; margin-left: 8px; padding: 2px 6px;"
                        @click="changeCarrier"
                    />
                </div>
                <div class="picked-summary-badge">
                    <i class="fa fa-shopping-basket"></i>
                    <span>{{ so.length }}</span>
                </div>
            </div>

            <div class="scanner-col">
                <div v-if="ready && !scan_bin && !showConfirmation" class="scanner-wrapper">
                    <BarcodeScannerComponent 
                        :key="scannerKey"
                        context="bin_scan_so"
                        :extra_data="this"
                        instructions="Escanea la etiqueta de orden SO"
                    />
                </div>
                <div v-else-if="ready && scan_bin && !showConfirmation" class="scanner-wrapper">
                    <Button 
                        icon="fa fa-arrow-left" 
                        @click="backToScanSO" 
                        class="p-button-rounded p-button-secondary back-button" 
                    />
                    <QRScannerComponent 
                        instructions="Escanea la ubicación BIN"
                        :onScan="(data) => validateBin(data)"
                    />
                </div>

                <div v-else-if="showConfirmation" class="confirmation-wrapper">
                    <div class="confirmation-content">
                        <i class="fa fa-exclamation-triangle confirmation-icon"></i>
                        <h3>Confirmación de Traslado</h3>
                        <p>Vas a mover <b>{{ so.length }}</b> órdenes al BIN: <b>{{ targetBin }}</b></p>
                        <p style="font-size: 0.85rem; color: #3498db;"><i class="fa fa-truck"></i> Carrier: <b>{{ selectedCarrierName }}</b></p>
                        <div class="confirmation-buttons">
                            <Button label="Confirmar" icon="fa fa-check" class="p-button-success" @click="confirmMove" />
                            <Button label="Re-escanear BIN" icon="fa fa-refresh" class="p-button-secondary" @click="cancelConfirmation" />
                        </div>
                    </div>
                </div>
            </div>

            <div class="buttons-col" v-if="!showConfirmation">
                <Button v-if="so.length > 0 && !scan_bin"
                    @click="goToScanBin"
                    class="p-button-success p-button-sm" 
                    label="Trasladar a BIN" 
                    icon="fa fa-paper-plane"
                />
                <Button v-if="so.length === 0 && !scan_bin && !lastUsedBin"
                    @click="goToScanBin"
                    class="p-button-warning p-button-sm" 
                    label="Bloquear un BIN" 
                    icon="fa fa-lock"
                />
                <Button v-if="lastUsedBin && so.length === 0"
                    @click="blockLastBin"
                    class="p-button-warning p-button-sm" 
                    :label="'Bloquear BIN ' + lastUsedBin" 
                    icon="fa fa-lock"
                />
                <Button v-if="lastUsedBin && so.length === 0"
                    @click="lastUsedBin = null"
                    class="p-button-text p-button-secondary p-button-sm" 
                    label="Limpiar BIN seleccionado" 
                    icon="fa fa-refresh"
                />
                <Button 
                    @click="exitFlow"
                    class="p-button-text p-button-danger p-button-sm" 
                    label="Salir / Finalizar" 
                    icon="fa fa-times"
                />
            </div>

            <div class="log-col">
                <div class="log-header">
                    <div class="log-header-info">
                        <span class="log-title">Resumen de Escaneo</span>
                        <Button icon="fa fa-trash" class="p-button-danger p-button-text p-button-sm" label="Limpiar Todo" @click="clearAllOrders" v-if="so.length > 0 && !showConfirmation"/>
                    </div>
                </div>

                <!-- Visualization of n/total -->
                <div class="scan-summary-grid" v-if="scanSummary.length > 0">
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
                <div v-if="summaryTotalPages > 1" class="pagination-container" style="margin-top: 10px; margin-bottom: 15px;">
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

                <div class="log-list">
                    <div v-for="order in paginatedSo" :key="order.name" class="log-item">
                        <div>
                            <i class="fa fa-barcode barcode-icon"></i>
                            {{ order.name }}
                            <small class="text-info ml-2">({{ order.current }}/{{ order.total }})</small>
                        </div>
                        <Button v-if="!showConfirmation" icon="fa fa-times" class="p-button-rounded p-button-danger p-button-text" @click="removeOrder(order)" />
                    </div>
                    <div v-if="so.length === 0" class="empty-log">
                        <i class="fa fa-search search-icon"></i>
                        Esperando escaneo de etiqueta EI (SOXXXX/N)...
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
                        <small class="pagination-total">({{ so.length }} ordenes)</small>
                    </span>
                    <Button 
                        icon="fa fa-chevron-right" 
                        class="p-button-rounded p-button-text p-button-sm pagination-btn" 
                        :disabled="currentPage === totalPages" 
                        @click="currentPage++" 
                    />
                </div>
            </div>

        </template>
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
            scannerKey: 0,
            showConfirmation: false,
            targetBin: null,
            lastUsedBin: null,
            currentPage: 1,
            summaryCurrentPage: 1,

            // ── Carrier ──
            carrierList: [],
            carrierIdChoice: null,
            selectedCarrierId: null,
            selectedCarrierName: '',
            loadingCarriers: true,
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
        },
        totalPages() {
            return Math.ceil(this.so.length / 4) || 1;
        },
        paginatedSo() {
            const start = (this.currentPage - 1) * 4;
            return this.so.slice(start, start + 4);
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
        'so.length'(newVal, oldVal) {
            const maxPages = Math.ceil(newVal / 4) || 1;
            if (newVal > oldVal) {
                this.currentPage = maxPages;
            } else if (this.currentPage > maxPages) {
                this.currentPage = maxPages;
            }
        },
        'scanSummary.length'(newVal, oldVal) {
            const maxPages = Math.ceil(newVal / 4) || 1;
            if (newVal > oldVal) {
                this.summaryCurrentPage = maxPages;
            } else if (this.summaryCurrentPage > maxPages) {
                this.summaryCurrentPage = maxPages;
            }
        }

    },
    async mounted() {
        console.log("Action: BinComponent mounted");
        await this.fetchCarrierList();
        setTimeout(() => {
            this.ready = true;
            this.loadingCarriers = false;
        }, 500);
    },
    methods: {
        // ── Carrier ──
        async fetchCarrierList() {
            try {
                const res = await this.store.callOdoo("get_carrier_list", "", {});
                if (res && res.ok) {
                    this.carrierList = res.carriers;
                }
            } catch (e) {
                console.error("Error cargando carriers:", e);
            }
        },

        confirmCarrier() {
            const c = this.carrierList.find(x => x.id === this.carrierIdChoice);
            if (c) {
                this.selectedCarrierId = c.id;
                this.selectedCarrierName = c.name;
            }
        },

        changeCarrier() {
            this.selectedCarrierId = null;
            this.selectedCarrierName = '';
            this.carrierIdChoice = null;
        },

        // ── Existing methods ──
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
            this.showConfirmation = false;
            this.store.mandatory_uncompleted.doneMandatory();
        },
        async validateBin(data) {
            console.log("Action: validateBin data received:", data);
            
            try {
                let parsedData = typeof data === 'string' ? JSON.parse(data) : data;
                const binName = parsedData.name;
                
                let response = await this.store.callOdoo("validate_bin", "", {
                    bin: binName
                });

                if (response.valid) {
                    // Si estamos moviendo pedidos (so.length > 0), el BIN no debe tener productos de Fulfillment
                    if (this.so.length > 0 && response.has_full) {
                        this.$toast.add({ 
                            severity: 'error', 
                            summary: 'BIN con Fulfillment', 
                            detail: 'Este BIN ya contiene productos de Fulfillment y no se pueden mezclar con pedidos.', 
                            life: 5000 
                        });
                        return;
                    }

                    if (this.so.length > 0) {
                        this.targetBin = binName;
                        this.showConfirmation = true;
                        console.log("Action: Confirmation screen displayed for bin:", this.targetBin);
                    } else {
                        this.lastUsedBin = binName;
                        this.scan_bin = false;
                        this.$toast.add({ severity: 'info', summary: 'BIN seleccionado', detail: `El BIN ${binName} está listo para ser bloqueado.`, life: 3000 });
                    }
                } else {
                    this.$toast.add({ severity: 'error', summary: 'Error de BIN', detail: (response.error || 'BIN no válido.'), life: 3000 });
                }
            } catch (e) {
                console.log("Action: Error parsing bin data", e);
                this.$toast.add({ severity: 'error', summary: 'Error de Lectura', detail: 'El código del bin no es válido.', life: 3000 });
            }
        },
        async confirmMove() {
            console.log("Action: confirmMove triggered");
            try {
                const binName = this.targetBin;
                console.log("Action: Calling Odoo move_to_bin with bin:", binName);
                let response = await this.store.callOdoo("move_to_bin", "", {
                    bin: binName,
                    operator: this.store.role.email,
                    orders: this.so.map(o => o.name),
                    carrier_id: this.selectedCarrierId,
                });

                if (response.ok) {
                    console.log("Action: move_to_bin successful");
                    if (response.status === "queued") {
                        if (this.$toast) {
                            this.$toast.add({
                                severity: 'info',
                                summary: 'Movimiento Encolado',
                                detail: 'Debido a la cantidad de paquetes (>10), el traslado se procesará en segundo plano. Puedes continuar usando la app.',
                                life: 8000
                            });
                        }
                    } else {
                        if (this.$toast) {
                            this.$toast.add({
                                severity: 'success',
                                summary: 'Traslado Exitoso',
                                detail: 'Los paquetes han sido movidos al BIN.',
                                life: 4000
                            });
                        }
                    }
                    this.lastUsedBin = binName;
                    this.so = [];
                    this.scan_bin = false;
                    this.showConfirmation = false;
                    this.targetBin = null;
                    this.scannerKey++; 
                }

            } catch (e) {
                console.log("Action: Error in confirmMove", e);
                this.$toast.add({ severity: 'error', summary: 'Error de Servidor', detail: 'No se pudo realizar el movimiento en Odoo.', life: 3000 });
            }
        },
        async blockLastBin() {
            if (!this.lastUsedBin) return;
            try {
                let response = await this.store.callOdoo("block_bin", "", {
                    bin: this.lastUsedBin
                });
                if (response.ok) {
                    this.$toast.add({ severity: 'success', summary: 'BIN Bloqueado', detail: `El BIN ${this.lastUsedBin} ha sido bloqueado.`, life: 3000 });
                    this.lastUsedBin = null;
                } else {
                    this.$toast.add({ severity: 'error', summary: 'Error', detail: (response.error || 'No se pudo bloquear el BIN.'), life: 3000 });
                }
            } catch (e) {
                console.log("Action: Error in blockLastBin", e);
                this.$toast.add({ severity: 'error', summary: 'Error', detail: 'No se pudo bloquear el BIN.', life: 3000 });
            }
        },
        cancelConfirmation() {
            console.log("Action: cancelConfirmation triggered, returning to bin scanner");
            this.showConfirmation = false;
            this.targetBin = null;
            this.scannerKey++;
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
        removeOrder(order) {
            console.log("Action: removeOrder triggered for order:", order.name);
            const index = this.so.findIndex(o => o.name === order.name);
            if (index !== -1) {
                this.so.splice(index, 1);
            }
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

/* ── Carrier Selection ── */
.carrier-select-overlay {
    display: flex;
    justify-content: center;
    align-items: center;
    height: 100%;
}

.carrier-select-card {
    background: #2c3e50;
    border-radius: 12px;
    padding: 30px;
    display: flex;
    flex-direction: column;
    align-items: center;
    color: #ecf0f1;
    gap: 8px;
    min-width: 280px;
}

.carrier-dropdown {
    width: 100%;
    padding: 10px;
    border-radius: 6px;
    border: 1px solid #3498db;
    background: #34495e;
    color: #ecf0f1;
    font-size: 1rem;
    margin-bottom: 10px;
}

.carrier-dropdown option {
    background: #34495e;
    color: #ecf0f1;
}

.carrier-indicator {
    background: #3498db;
    color: white;
    padding: 6px 15px;
    border-radius: 6px;
    font-size: 0.85rem;
    font-weight: bold;
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
    text-align: center;
    padding: 20px;
}

.confirmation-icon {
    font-size: 3rem;
    color: #f1c40f;
    margin-bottom: 10px;
}

.confirmation-buttons {
    display: flex;
    gap: 15px;
    justify-content: center;
    margin-top: 20px;
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
    gap: 10px;
    justify-content: center;
    align-items: center;
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
</style>