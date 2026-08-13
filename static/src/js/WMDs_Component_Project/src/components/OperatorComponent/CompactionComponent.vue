<template>
    <div class="compaction-container">
        <!-- Header -->
        <div class="compaction-header">
            <div class="header-info">
                <h2>Compactación</h2>
                <span v-if="pickingName" class="picking-badge">{{ pickingName }}</span>
            </div>
            <button class="close-btn" @click="exitFlow">
                <i class="fa fa-times"></i>
            </button>
        </div>

        <!-- Main Body -->
        <div class="compaction-body">
            <!-- 1. Initial Loading state -->
            <div v-if="loadingPicking" class="loading-state">
                <i class="fa fa-spinner fa-spin loading-icon"></i>
                <p>Creando formulario de compactación...</p>
            </div>

            <!-- 2. Scan Origin Location -->
            <div v-else-if="state === 'scan_origin'" class="flow-step">
                <div class="instruction-card">
                    <i class="fa fa-map-marker step-icon"></i>
                    <h3>Paso 1: Ubicación Origen</h3>
                    <p>Escanea la ubicación desde donde vas a tomar los productos (A, B, C...)</p>
                </div>
                <div class="scanner-section">
                    <BarcodeScannerComponent 
                        :key="scannerKey"
                        instructions="Escanea ubicación origen"
                        :onScan="handleOriginScan"
                    />
                </div>
                <div v-if="confirmedMoves.length > 0" class="progress-section">
                    <h4>Productos reservados para compactar:</h4>
                    <div class="summary-list">
                        <div v-for="(item, index) in confirmedMoves" :key="index" class="summary-item">
                            <span class="item-loc">{{ item.location_name }}</span>
                            <span class="item-product">{{ item.product_name }}</span>
                            <span class="item-qty">Cant: {{ item.qty }}</span>
                        </div>
                    </div>
                </div>
            </div>

            <!-- 3. Scan Products & Quantities -->
            <div v-else-if="state === 'scan_products'" class="flow-step">
                <div class="location-banner">
                    <i class="fa fa-folder-open"></i> Ubicación Origen: <strong>{{ originLocation.name }}</strong>
                </div>

                <div class="products-list-card">
                    <h3>Selecciona Productos y Cantidades</h3>
                    <p class="subtitle">Ingresa la cantidad que vas a mover de cada producto:</p>

                    <div class="product-rows">
                        <div v-for="prod in originProducts" :key="prod.product_id" class="product-row">
                            <div class="product-info">
                                <span class="product-sku">{{ prod.sku }}</span>
                                <span class="product-name">{{ prod.product_name }}</span>
                                <span class="product-avail">Disponible: <strong>{{ prod.qty_available }}</strong></span>
                            </div>
                            <div class="quantity-controls">
                                <button 
                                    class="qty-btn" 
                                    @click="adjustQty(prod, -1)" 
                                    :disabled="!selectedQtys[prod.product_id]"
                                >-</button>
                                <input 
                                    type="number" 
                                    class="qty-input" 
                                    v-model.number="selectedQtys[prod.product_id]"
                                    min="0"
                                    :max="prod.qty_available"
                                >
                                <button 
                                    class="qty-btn" 
                                    @click="adjustQty(prod, 1)" 
                                    :disabled="selectedQtys[prod.product_id] >= prod.qty_available"
                                >+</button>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="action-buttons">
                    <button 
                        class="btn btn-primary" 
                        @click="confirmLocationClosure"
                        :disabled="!hasSelectedItems"
                    >
                        <i class="fa fa-check"></i> Confirmar y cerrar ubicación
                    </button>
                    <button class="btn btn-secondary" @click="cancelOriginSelection">
                        Cancelar / Cambiar Ubicación
                    </button>
                </div>
            </div>

            <!-- 4. Next Action Selection -->
            <div v-else-if="state === 'select_next_action'" class="flow-step text-center">
                <div class="success-card">
                    <i class="fa fa-check-circle success-icon"></i>
                    <h3>¡Ubicación cerrada con éxito!</h3>
                    <p>Los productos escaneados han sido reservados correctamente.</p>
                </div>

                <div class="action-card-grid">
                    <button class="action-card btn-outline" @click="scanAnotherOrigin">
                        <i class="fa fa-plus-circle"></i>
                        <span>Compactar otra ubicación origen</span>
                    </button>
                    <button class="action-card btn-success-card" @click="goToScanDest">
                        <i class="fa fa-arrow-right"></i>
                        <span>Escanear ubicación destino</span>
                    </button>
                </div>

                <div class="progress-section">
                    <h4>Resumen de productos listos para mover:</h4>
                    <div class="summary-list">
                        <div v-for="(item, index) in confirmedMoves" :key="index" class="summary-item">
                            <span class="item-loc">{{ item.location_name }}</span>
                            <span class="item-product">{{ item.product_name }}</span>
                            <span class="item-qty">Cant: {{ item.qty }}</span>
                        </div>
                    </div>
                </div>
            </div>

            <!-- 5. Scan Destination Location -->
            <div v-else-if="state === 'scan_dest'" class="flow-step">
                <div class="instruction-card dest">
                    <i class="fa fa-arrow-circle-right step-icon"></i>
                    <h3>Paso 2: Ubicación Destino</h3>
                    <p>Escanea la ubicación destino donde colocarás todos los productos (D)</p>
                </div>
                <div class="scanner-section">
                    <BarcodeScannerComponent 
                        :key="scannerKey"
                        instructions="Escanea ubicación destino"
                        :onScan="handleDestScan"
                    />
                </div>
                <div class="action-buttons">
                    <button class="btn btn-secondary" @click="backToNextAction">
                        <i class="fa fa-arrow-left"></i> Volver al resumen
                    </button>
                </div>
            </div>

            <!-- 6. Final Confirmation -->
            <div v-else-if="state === 'confirmation'" class="flow-step">
                <div class="confirmation-card">
                    <i class="fa fa-exchange confirmation-icon"></i>
                    <h3>Confirmar Compactación</h3>
                    <p>Estás a punto de completar el traslado de compactación:</p>

                    <div class="summary-box">
                        <div class="summary-section">
                            <strong>Origen:</strong>
                            <ul>
                                <li v-for="(item, index) in confirmedMoves" :key="index">
                                    {{ item.location_name }} → {{ item.product_name }} ({{ item.qty }} uds)
                                </li>
                            </ul>
                        </div>
                        <div class="summary-divider"></div>
                        <div class="summary-section">
                            <strong>Destino:</strong>
                            <div class="dest-loc-badge">
                                <i class="fa fa-map-marker"></i> {{ destLocation.name }}
                            </div>
                        </div>
                    </div>
                </div>

                <div class="action-buttons">
                    <button class="btn btn-success" @click="executeCompaction">
                        <i class="fa fa-check"></i> Confirmar y finalizar
                    </button>
                    <button class="btn btn-secondary" @click="reScanDest">
                        Re-escanear destino
                    </button>
                </div>
            </div>
        </div>
    </div>
</template>

<script>
import BarcodeScannerComponent from '../QRScannerComponent/BarcodeScannerComponent.vue';
import { useGeneralStore } from "../../store/index";

export default {
    name: "CompactionComponent",
    components: {
        BarcodeScannerComponent
    },
    data() {
        return {
            store: useGeneralStore(),
            loadingPicking: true,
            pickingId: null,
            pickingName: "",
            state: "scan_origin", // scan_origin, scan_products, select_next_action, scan_dest, confirmation
            scannerKey: 0,

            // Origin Location state
            originLocation: { id: null, name: "" },
            originProducts: [],
            selectedQtys: {}, // product_id -> quantity

            // Accumulated items
            confirmedMoves: [], // list of { location_id, location_name, product_id, product_name, qty }

            // Destination Location state
            destLocation: { id: null, name: "" }
        }
    },
    computed: {
        hasSelectedItems() {
            return Object.values(this.selectedQtys).some(qty => qty > 0);
        }
    },
    methods: {
        async initializeCompaction() {
            this.loadingPicking = true;
            try {
                const response = await this.store.callOdoo("compactacion_create", "", {
                    operator_email: this.store.role.email
                });

                if (response.status === "ok") {
                    this.pickingId = response.picking_id;
                    this.pickingName = response.picking_name;
                    this.state = "scan_origin";
                } else {
                    this.$toast.add({
                        severity: "error",
                        summary: "Error",
                        detail: response.message || "No se pudo crear la compactación.",
                        life: 5000
                    });
                    this.exitFlow();
                }
            } catch (err) {
                console.error(err);
                this.$toast.add({
                    severity: "error",
                    summary: "Error",
                    detail: "Error de red al inicializar la operación.",
                    life: 5000
                });
                this.exitFlow();
            } finally {
                this.loadingPicking = false;
            }
        },

        async handleOriginScan(barcode) {
            if (!barcode) return;
            this.store.loading = true;
            try {
                const response = await this.store.callOdoo("compactacion_validate_origin", "", {
                    location_barcode: barcode,
                    picking_id: this.pickingId
                });

                if (response.status === "ok") {
                    this.originLocation = {
                        id: response.location_id,
                        name: response.location_name
                    };
                    this.originProducts = response.products;
                    
                    // Initialize quantities to 0
                    this.selectedQtys = {};
                    response.products.forEach(p => {
                        this.selectedQtys[p.product_id] = 0;
                    });

                    this.state = "scan_products";
                } else {
                    this.$toast.add({
                        severity: "warn",
                        summary: "Restricción",
                        detail: response.message || "Ubicación de origen no válida.",
                        life: 6000
                    });
                    this.scannerKey++;
                }
            } catch (err) {
                console.error(err);
            } finally {
                this.store.loading = false;
            }
        },

        adjustQty(product, val) {
            const current = this.selectedQtys[product.product_id] || 0;
            const updated = Math.max(0, Math.min(product.qty_available, current + val));
            this.selectedQtys[product.product_id] = updated;
        },

        cancelOriginSelection() {
            this.originLocation = { id: null, name: "" };
            this.originProducts = [];
            this.selectedQtys = {};
            this.state = "scan_origin";
            this.scannerKey++;
        },

        async confirmLocationClosure() {
            const linesToSend = [];
            Object.entries(this.selectedQtys).forEach(([prodId, qty]) => {
                if (qty > 0) {
                    linesToSend.push({
                        product_id: parseInt(prodId),
                        qty: qty
                    });
                }
            });

            if (linesToSend.length === 0) return;

            this.store.loading = true;
            try {
                const response = await this.store.callOdoo("compactacion_add_lines", "", {
                    picking_id: this.pickingId,
                    location_src_id: this.originLocation.id,
                    lines: linesToSend
                });

                if (response.status === "ok") {
                    // Add items locally to confirmed list
                    linesToSend.forEach(line => {
                        const productObj = this.originProducts.find(p => p.product_id === line.product_id);
                        this.confirmedMoves.push({
                            location_id: this.originLocation.id,
                            location_name: this.originLocation.name,
                            product_id: line.product_id,
                            product_name: productObj ? productObj.product_name : `Producto ${line.product_id}`,
                            qty: line.qty
                        });
                    });

                    // Clear current scan details
                    this.originLocation = { id: null, name: "" };
                    this.originProducts = [];
                    this.selectedQtys = {};

                    // Advance
                    this.state = "select_next_action";
                } else {
                    this.$toast.add({
                        severity: "error",
                        summary: "Reserva Fallida",
                        detail: response.message || "El producto ya no está disponible o está reservado.",
                        life: 6000
                    });
                }
            } catch (err) {
                console.error(err);
            } finally {
                this.store.loading = false;
            }
        },

        scanAnotherOrigin() {
            this.state = "scan_origin";
            this.scannerKey++;
        },

        goToScanDest() {
            this.state = "scan_dest";
            this.scannerKey++;
        },

        backToNextAction() {
            this.state = "select_next_action";
        },

        async handleDestScan(barcode) {
            if (!barcode) return;
            this.store.loading = true;
            try {
                const response = await this.store.callOdoo("compactacion_validate_dest", "", {
                    location_barcode: barcode
                });

                if (response.status === "ok") {
                    this.destLocation = {
                        id: response.location_id,
                        name: response.location_name
                    };
                    this.state = "confirmation";
                } else {
                    this.$toast.add({
                        severity: "warn",
                        summary: "Restricción",
                        detail: response.message || "Ubicación de destino no válida.",
                        life: 6000
                    });
                    this.scannerKey++;
                }
            } catch (err) {
                console.error(err);
            } finally {
                this.store.loading = false;
            }
        },

        reScanDest() {
            this.destLocation = { id: null, name: "" };
            this.state = "scan_dest";
            this.scannerKey++;
        },

        async executeCompaction() {
            this.store.loading = true;
            try {
                const response = await this.store.callOdoo("compactacion_validate_picking", "", {
                    picking_id: this.pickingId,
                    location_dest_id: this.destLocation.id,
                    operator_email: this.store.role.email
                });

                if (response.status === "ok") {
                    this.$toast.add({
                        severity: "success",
                        summary: "Completado",
                        detail: "Compactación realizada con éxito.",
                        life: 4000
                    });
                    // Close flow and return to operator panel
                    this.store.mandatory_uncompleted.doneMandatory();
                } else {
                    this.$toast.add({
                        severity: "error",
                        summary: "Error de Validación",
                        detail: response.message || "Error al completar el traslado.",
                        life: 6000
                    });
                }
            } catch (err) {
                console.error(err);
            } finally {
                this.store.loading = false;
            }
        },

        exitFlow() {
            if (this.confirmedMoves.length > 0 || this.pickingId) {
                if (!confirm("Hay una operación de compactación en curso. ¿Estás seguro de que deseas salir y descartar?")) {
                    return;
                }
            }
            this.store.mandatory_uncompleted.doneMandatory();
        }
    },
    mounted() {
        this.initializeCompaction();
    }
}
</script>

<style scoped>
.compaction-container {
    display: flex;
    flex-direction: column;
    height: 100vh;
    background: #f8fafc;
    color: #1e293b;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
}

.compaction-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 1rem;
    background: #1e293b;
    color: #ffffff;
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.header-info {
    display: flex;
    align-items: center;
    gap: 10px;
}

.header-info h2 {
    margin: 0;
    font-size: 1.25rem;
    font-weight: 600;
}

.picking-badge {
    background: #3b82f6;
    font-size: 0.8rem;
    padding: 3px 8px;
    border-radius: 4px;
    font-weight: bold;
}

.close-btn {
    background: transparent;
    border: none;
    color: #94a3b8;
    font-size: 1.25rem;
    cursor: pointer;
    padding: 5px;
    transition: color 0.2s;
}

.close-btn:hover {
    color: #ffffff;
}

.compaction-body {
    flex: 1;
    overflow-y: auto;
    padding: 1rem;
    display: flex;
    flex-direction: column;
    gap: 1rem;
}

.loading-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 50vh;
    color: #64748b;
    gap: 10px;
}

.loading-icon {
    font-size: 2.5rem;
    color: #3b82f6;
}

.flow-step {
    display: flex;
    flex-direction: column;
    gap: 1rem;
    width: 100%;
}

.instruction-card {
    background: #eff6ff;
    border-left: 4px solid #3b82f6;
    padding: 1rem;
    border-radius: 6px;
}

.instruction-card.dest {
    background: #f0fdf4;
    border-left-color: #22c55e;
}

.instruction-card h3 {
    margin: 0 0 5px;
    font-size: 1.1rem;
    font-weight: 600;
}

.instruction-card p {
    margin: 0;
    font-size: 0.9rem;
    color: #475569;
}

.step-icon {
    font-size: 1.5rem;
    color: #3b82f6;
    margin-bottom: 5px;
}

.instruction-card.dest .step-icon {
    color: #22c55e;
}

.scanner-section {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    overflow: hidden;
    min-height: 250px;
    display: flex;
    flex-direction: column;
}

.progress-section {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 1rem;
}

.progress-section h4 {
    margin: 0 0 10px;
    font-size: 0.95rem;
    font-weight: 600;
    color: #475569;
}

.summary-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
    max-height: 200px;
    overflow-y: auto;
}

.summary-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: #f1f5f9;
    padding: 8px 12px;
    border-radius: 6px;
    font-size: 0.85rem;
    border-left: 3px solid #64748b;
}

.item-loc {
    font-weight: bold;
    color: #3b82f6;
    min-width: 80px;
}

.item-product {
    flex: 1;
    margin: 0 10px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.item-qty {
    font-weight: bold;
    color: #1e293b;
}

.location-banner {
    background: #1e293b;
    color: #ffffff;
    padding: 0.75rem 1rem;
    border-radius: 6px;
    font-size: 0.95rem;
}

.products-list-card {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 1rem;
}

.products-list-card h3 {
    margin: 0 0 4px;
    font-size: 1.05rem;
    font-weight: 600;
}

.products-list-card .subtitle {
    margin: 0 0 1rem;
    font-size: 0.85rem;
    color: #64748b;
}

.product-rows {
    display: flex;
    flex-direction: column;
    gap: 12px;
}

.product-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding-bottom: 12px;
    border-bottom: 1px solid #f1f5f9;
}

.product-row:last-child {
    border-bottom: none;
    padding-bottom: 0;
}

.product-info {
    display: flex;
    flex-direction: column;
    gap: 2px;
    flex: 1;
    margin-right: 15px;
}

.product-sku {
    font-size: 0.8rem;
    font-weight: 700;
    color: #3b82f6;
}

.product-name {
    font-size: 0.9rem;
    font-weight: 500;
    color: #1e293b;
}

.product-avail {
    font-size: 0.8rem;
    color: #64748b;
}

.quantity-controls {
    display: flex;
    align-items: center;
    gap: 6px;
}

.qty-btn {
    width: 32px;
    height: 32px;
    border-radius: 6px;
    border: 1px solid #cbd5e1;
    background: #f8fafc;
    color: #1e293b;
    font-size: 1.1rem;
    font-weight: 600;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.2s;
}

.qty-btn:hover:not(:disabled) {
    background: #e2e8f0;
    border-color: #94a3b8;
}

.qty-btn:disabled {
    opacity: 0.4;
    cursor: not-allowed;
}

.qty-input {
    width: 50px;
    height: 32px;
    border-radius: 6px;
    border: 1px solid #cbd5e1;
    text-align: center;
    font-size: 0.95rem;
    font-weight: 600;
}

.action-buttons {
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin-top: 10px;
}

.btn {
    width: 100%;
    padding: 0.85rem;
    border-radius: 6px;
    font-size: 0.95rem;
    font-weight: 600;
    cursor: pointer;
    border: none;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    transition: background 0.2s;
}

.btn-primary {
    background: #3b82f6;
    color: #ffffff;
}

.btn-primary:hover:not(:disabled) {
    background: #2563eb;
}

.btn-primary:disabled {
    background: #94a3b8;
    cursor: not-allowed;
}

.btn-secondary {
    background: #e2e8f0;
    color: #475569;
}

.btn-secondary:hover {
    background: #cbd5e1;
}

.btn-success {
    background: #22c55e;
    color: #ffffff;
}

.btn-success:hover {
    background: #16a34a;
}

.text-center {
    text-align: center;
}

.success-card {
    background: #f0fdf4;
    border: 1px solid #bbf7d0;
    border-radius: 8px;
    padding: 1.5rem;
    margin-bottom: 1rem;
}

.success-icon {
    font-size: 3rem;
    color: #22c55e;
    margin-bottom: 10px;
}

.success-card h3 {
    margin: 0 0 5px;
    color: #14532d;
}

.success-card p {
    margin: 0;
    font-size: 0.9rem;
    color: #166534;
}

.action-card-grid {
    display: flex;
    flex-direction: column;
    gap: 10px;
    margin-bottom: 1rem;
}

.action-card {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 12px;
    padding: 1.25rem;
    border-radius: 8px;
    border: 2px solid transparent;
    font-size: 1rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;
}

.btn-outline {
    background: #ffffff;
    border-color: #cbd5e1;
    color: #475569;
}

.btn-outline:hover {
    background: #f8fafc;
    border-color: #94a3b8;
}

.btn-success-card {
    background: #22c55e;
    color: #ffffff;
}

.btn-success-card:hover {
    background: #16a34a;
}

.confirmation-card {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 1.5rem;
    text-align: center;
}

.confirmation-icon {
    font-size: 2.5rem;
    color: #3b82f6;
    margin-bottom: 10px;
}

.confirmation-card h3 {
    margin: 0 0 5px;
}

.confirmation-card p {
    margin: 0 0 1.25rem;
    font-size: 0.9rem;
    color: #64748b;
}

.summary-box {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 6px;
    padding: 1rem;
    text-align: left;
}

.summary-section strong {
    font-size: 0.85rem;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: #64748b;
}

.summary-section ul {
    margin: 5px 0 0;
    padding-left: 20px;
    font-size: 0.9rem;
}

.summary-section li {
    margin-bottom: 4px;
}

.summary-divider {
    height: 1px;
    background: #e2e8f0;
    margin: 12px 0;
}

.dest-loc-badge {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    background: #e0f2fe;
    color: #0369a1;
    padding: 6px 12px;
    border-radius: 4px;
    font-weight: 700;
    font-size: 1rem;
    margin-top: 5px;
}
</style>
