<template>
    <div class="location-preview-container">
        <!-- Top Navigation / Header -->
        <div class="preview-header">
            <div class="header-titles">
                <h2 class="title">
                    <i class="fa fa-info-circle mr-2 text-primary"></i> Información de la Ubicación
                </h2>
                <p class="subtitle">Consulta de stock teórico, bloqueos, conteos y reservas</p>
            </div>
            <Button 
                icon="fa fa-times" 
                class="p-button-rounded p-button-text p-button-secondary close-btn" 
                @click="exitFlow" 
                title="Cerrar y volver a tareas"
            />
        </div>

        <!-- Scanning / Input State -->
        <div v-if="!locationData" class="scanner-body">
            <div class="scanner-card shadow-1">
                <QRScannerComponent 
                    :key="scannerKey"
                    instructions="Apunta la cámara o pistola láser al código de la ubicación"
                    :can_close="false"
                    :onScan="handleLocationScan"
                    :disableFocus="isManualFocused"
                />
            </div>

            <!-- Manual input fallback -->
            <div class="manual-input-section shadow-1">
                <span class="manual-label">¿Problemas con el código? Ingrésalo manualmente:</span>
                <div class="input-row">
                    <InputText 
                        v-model="manualBarcode" 
                        placeholder="Ej. A-01-01, P1-R02-N1" 
                        class="p-inputtext-sm manual-input"
                        :disabled="isSearching"
                        @focus="isManualFocused = true"
                        @blur="onManualBlur"
                        @keyup.enter="submitManual"
                    />
                    <Button 
                        label="Consultar" 
                        icon="fa fa-search" 
                        class="p-button-primary p-button-sm btn-submit" 
                        :loading="isSearching"
                        :disabled="!manualBarcode.trim() || isSearching"
                        @click="submitManual"
                    />
                </div>
            </div>
        </div>

        <!-- Result / Detail State -->
        <div v-else class="result-body">
            <!-- Location Identification Card -->
            <div class="location-card shadow-2">
                <div class="location-main-row">
                    <div class="location-badge-icon">
                        <i class="fa fa-map-marker"></i>
                    </div>
                    <div class="location-title-box">
                        <h3 class="location-name">{{ locationData.location.complete_name }}</h3>
                        <span class="location-barcode-text" v-if="locationData.location.barcode">
                            <i class="fa fa-barcode mr-1"></i> {{ locationData.location.barcode }}
                        </span>
                    </div>
                </div>

                <!-- Status Chips / Indicators -->
                <div class="status-chips-grid">
                    <!-- Empty / Stock chip -->
                    <div 
                        :class="['status-chip', locationData.empty_status.is_empty ? 'chip-empty' : 'chip-has-stock']"
                        @click="activeTab = locationData.empty_status.is_empty ? 'empty' : 'stock'"
                    >
                        <i :class="['fa', locationData.empty_status.is_empty ? 'fa-inbox' : 'fa-cubes']"></i>
                        <span>
                            {{ locationData.empty_status.is_empty ? 'Vacía (' + locationData.empty_status.empty_duration + ')' : ('Stock: ' + locationData.stock_summary.total_units + ' uds') }}
                        </span>
                    </div>

                    <!-- Block chip -->
                    <div 
                        :class="['status-chip', !locationData.blocking.is_blocked ? 'chip-unblocked' : (locationData.blocking.is_block_expired ? 'chip-expired' : 'chip-blocked')]"
                        @click="activeTab = 'blocking'"
                    >
                        <i :class="['fa', !locationData.blocking.is_blocked ? 'fa-unlock' : 'fa-lock']"></i>
                        <span>
                            {{ !locationData.blocking.is_blocked ? 'Sin Bloqueo' : (locationData.blocking.is_block_expired ? 'Bloqueo Expirado' : ('Bloqueada: ' + (locationData.blocking.block_reason_type || 'Bloqueo'))) }}
                        </span>
                    </div>

                    <!-- Cycle Count chip -->
                    <div 
                        :class="['status-chip', locationData.cycle_count.in_cycle_count ? 'chip-cycle' : 'chip-muted']"
                        @click="activeTab = 'cycle'"
                    >
                        <i class="fa fa-refresh"></i>
                        <span>
                            {{ locationData.cycle_count.in_cycle_count ? 'En Conteo Cíclico' : 'Sin Conteo' }}
                        </span>
                    </div>

                    <!-- Reservations chip -->
                    <div 
                        :class="['status-chip', locationData.reservations.has_pending_reservations ? 'chip-reservations' : 'chip-muted']"
                        @click="activeTab = 'reservations'"
                    >
                        <i class="fa fa-clock-o"></i>
                        <span>
                            {{ locationData.reservations.has_pending_reservations ? (locationData.reservations.reservations_count + ' Reservas') : 'Sin Reservas' }}
                        </span>
                    </div>
                </div>
            </div>

            <!-- Tab Navigation Buttons -->
            <div class="tab-buttons-container">
                <button 
                    :class="['tab-btn', { active: activeTab === 'stock' }]"
                    @click="activeTab = 'stock'"
                >
                    <i class="fa fa-cubes"></i> Stock ({{ locationData.stock_summary.products_count }})
                </button>
                <button 
                    :class="['tab-btn', { active: activeTab === 'blocking' }]"
                    @click="activeTab = 'blocking'"
                >
                    <i class="fa fa-lock"></i> Bloqueo
                </button>
                <button 
                    :class="['tab-btn', { active: activeTab === 'cycle' }]"
                    @click="activeTab = 'cycle'"
                >
                    <i class="fa fa-refresh"></i> Conteo Cíclico
                </button>
                <button 
                    :class="['tab-btn', { active: activeTab === 'reservations' }]"
                    @click="activeTab = 'reservations'"
                >
                    <i class="fa fa-clock-o"></i> Reservas ({{ locationData.reservations.reservations_count }})
                </button>
                <button 
                    :class="['tab-btn', { active: activeTab === 'empty' }]"
                    @click="activeTab = 'empty'"
                >
                    <i class="fa fa-inbox"></i> Antigüedad
                </button>
            </div>

            <!-- Tab Content -->
            <div class="tab-content-card shadow-1">
                <!-- TAB 1: STOCK -->
                <div v-if="activeTab === 'stock'" class="tab-pane">
                    <div v-if="locationData.stock_summary.items.length === 0" class="empty-state-box">
                        <i class="fa fa-inbox empty-icon"></i>
                        <h4>Ubicación Vacía</h4>
                        <p class="text-secondary">Odoo indica que actualmente no hay existencias ni quants en esta ubicación.</p>
                    </div>

                    <div v-else>
                        <div class="stock-totals-bar">
                            <div class="total-metric">
                                <span class="metric-num">{{ locationData.stock_summary.products_count }}</span>
                                <span class="metric-label">Productos</span>
                            </div>
                            <div class="total-metric">
                                <span class="metric-num font-blue">{{ locationData.stock_summary.total_units }}</span>
                                <span class="metric-label">A mano</span>
                            </div>
                            <div class="total-metric">
                                <span class="metric-num font-orange">{{ locationData.stock_summary.total_reserved }}</span>
                                <span class="metric-label">Reservadas</span>
                            </div>
                            <div class="total-metric">
                                <span class="metric-num font-green">{{ locationData.stock_summary.total_available }}</span>
                                <span class="metric-label">Disponibles</span>
                            </div>
                        </div>

                        <div class="product-cards-list">
                            <div 
                                v-for="item in locationData.stock_summary.items" 
                                :key="item.quant_id"
                                class="product-item-card"
                            >
                                <div class="product-card-flex">
                                    <div class="product-thumb-container">
                                        <img 
                                            v-if="item.image_url" 
                                            :src="item.image_url" 
                                            :alt="item.product_name"
                                            class="product-thumb-img" 
                                            loading="lazy"
                                            @error="onImgError"
                                        />
                                        <div class="product-thumb-fallback">
                                            <i class="fa fa-cube"></i>
                                        </div>
                                    </div>
                                    <div class="product-details-col">
                                        <div class="item-header">
                                            <span class="product-code" v-if="item.default_code">{{ item.default_code }}</span>
                                            <span class="product-lot" v-if="item.lot_name && item.lot_name !== 'Sin lote'">
                                                <i class="fa fa-tag mr-1"></i> {{ item.lot_name }}
                                            </span>
                                        </div>
                                        <div class="product-name">{{ item.product_name }}</div>
                                        <div class="item-quantities-row">
                                            <span class="qty-pill">Total: <strong>{{ item.quantity }}</strong> {{ item.uom }}</span>
                                            <span class="qty-pill reserved" v-if="item.reserved_quantity > 0">
                                                Reservado: <strong>{{ item.reserved_quantity }}</strong>
                                            </span>
                                            <span class="qty-pill available">
                                                Disp: <strong>{{ item.available_quantity }}</strong>
                                            </span>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- TAB 2: BLOQUEO -->
                <div v-if="activeTab === 'blocking'" class="tab-pane">
                    <div v-if="!locationData.blocking.is_blocked" class="empty-state-box">
                        <i class="fa fa-unlock-alt ok-icon"></i>
                        <h4>Sin Bloqueos</h4>
                        <p class="text-secondary">Esta ubicación está completamente operativa para recepciones, movimientos y conteos.</p>
                    </div>

                    <div v-else class="block-detail-wrapper">
                        <div :class="['alert-banner', locationData.blocking.is_block_expired ? 'alert-warning' : 'alert-danger']">
                            <i :class="['fa', locationData.blocking.is_block_expired ? 'fa-exclamation-triangle' : 'fa-lock']"></i>
                            <div>
                                <h4 class="alert-title">
                                    {{ locationData.blocking.is_block_expired ? 'Bloqueo Expirado' : 'Ubicación Bloqueada' }}
                                </h4>
                                <span class="alert-desc">
                                    {{ locationData.blocking.is_block_expired ? 'La fecha de expiración ha vencido. Requiere revisión de supervisor.' : 'Esta ubicación no permite operaciones estándar de almacén.' }}
                                </span>
                            </div>
                        </div>

                        <div class="info-table-card">
                            <div class="info-data-row" v-if="locationData.blocking.block_reason_type">
                                <span class="data-label">Tipo de Bloqueo:</span>
                                <span class="data-value font-bold">{{ locationData.blocking.block_reason_type }}</span>
                            </div>
                            <div class="info-data-row" v-if="locationData.blocking.block_reason">
                                <span class="data-label">Motivo:</span>
                                <span class="data-value">{{ locationData.blocking.block_reason }}</span>
                            </div>
                            <div class="info-data-row" v-if="locationData.blocking.block_date">
                                <span class="data-label">Bloqueada desde:</span>
                                <span class="data-value">
                                    {{ locationData.blocking.block_date }} 
                                    <span class="time-relative">({{ locationData.blocking.block_date_relative }})</span>
                                </span>
                            </div>
                            <div class="info-data-row" v-if="locationData.blocking.block_user">
                                <span class="data-label">Bloqueada por:</span>
                                <span class="data-value">{{ locationData.blocking.block_user }}</span>
                            </div>
                            <div class="info-data-row" v-if="locationData.blocking.block_ticket">
                                <span class="data-label">Ticket:</span>
                                <span class="data-value font-bold">{{ locationData.blocking.block_ticket }}</span>
                            </div>
                            <div class="info-data-row" v-if="locationData.blocking.block_expiration_date">
                                <span class="data-label">Fecha de Expiración:</span>
                                <span :class="['data-value', locationData.blocking.is_block_expired ? 'text-danger font-bold' : '']">
                                    {{ locationData.blocking.block_expiration_date }}
                                    <span v-if="locationData.blocking.is_block_expired"> (¡Expirado!)</span>
                                </span>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- TAB 3: CONTEO CÍCLICO -->
                <div v-if="activeTab === 'cycle'" class="tab-pane">
                    <div v-if="!locationData.cycle_count.in_cycle_count" class="empty-state-box">
                        <i class="fa fa-check-circle-o ok-icon"></i>
                        <h4>Sin Conteo Cíclico Activo</h4>
                        <p class="text-secondary">Esta ubicación no se encuentra actualmente en ningún ciclo de conteo en progreso.</p>
                    </div>

                    <div v-else class="cycle-counts-list">
                        <div 
                            v-for="cc in locationData.cycle_count.cycle_counts" 
                            :key="cc.id"
                            class="cycle-count-card shadow-1"
                        >
                            <div class="cc-header">
                                <span class="cc-code"><i class="fa fa-refresh mr-1"></i> {{ cc.name }}</span>
                                <span class="cc-state-badge">{{ cc.state_label || cc.state }}</span>
                            </div>
                            <div class="cc-body">
                                <div class="info-data-row">
                                    <span class="data-label">Olas asociadas:</span>
                                    <span class="data-value">{{ cc.wave_names }}</span>
                                </div>
                                <div class="info-data-row">
                                    <span class="data-label">Operador(es):</span>
                                    <span class="data-value">{{ cc.operators }}</span>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- TAB 4: RESERVAS PENDIENTES -->
                <div v-if="activeTab === 'reservations'" class="tab-pane">
                    <div v-if="!locationData.reservations.has_pending_reservations" class="empty-state-box">
                        <i class="fa fa-check-circle-o ok-icon"></i>
                        <h4>Sin Reservas Pendientes</h4>
                        <p class="text-secondary">No existen movimientos o pedidos con reservas activas en esta posición.</p>
                    </div>

                    <div v-else class="reservations-list">
                        <div 
                            v-for="res in locationData.reservations.reservations" 
                            :key="res.line_id"
                            class="reservation-item-card shadow-1"
                        >
                            <div class="res-card-flex">
                                <div class="product-thumb-container mini-thumb" v-if="res.image_url">
                                    <img 
                                        :src="res.image_url" 
                                        :alt="res.product_name"
                                        class="product-thumb-img"
                                        loading="lazy"
                                        @error="onImgError"
                                    />
                                    <div class="product-thumb-fallback">
                                        <i class="fa fa-cube"></i>
                                    </div>
                                </div>
                                <div class="res-details-col">
                                    <div class="res-header">
                                        <span class="res-picking">{{ res.picking_name }}</span>
                                        <span class="res-qty font-orange">{{ res.quantity }} {{ res.uom }}</span>
                                    </div>
                                    <div class="res-product">{{ res.product_name }}</div>
                                    <div class="res-details-row">
                                        <span class="res-origin" v-if="res.origin"><i class="fa fa-file-text-o"></i> {{ res.origin }}</span>
                                        <span class="res-type" v-if="res.picking_type"><i class="fa fa-tag"></i> {{ res.picking_type }}</span>
                                        <span class="res-date" v-if="res.scheduled_date"><i class="fa fa-calendar"></i> {{ res.scheduled_date }}</span>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- TAB 5: ANTIGÜEDAD DE VACÍO -->
                <div v-if="activeTab === 'empty'" class="tab-pane">
                    <div v-if="!locationData.empty_status.is_empty" class="stock-occupied-box">
                        <i class="fa fa-cubes text-primary occupied-icon"></i>
                        <h4>Ubicación con Stock</h4>
                        <p class="text-secondary">
                            Esta ubicación cuenta actualmente con <strong>{{ locationData.stock_summary.total_units }}</strong> unidades registradas.
                        </p>
                    </div>

                    <div v-else class="empty-age-wrapper">
                        <div class="empty-age-hero shadow-1">
                            <i class="fa fa-calendar-check-o hero-icon text-success"></i>
                            <h3 class="hero-duration">{{ locationData.empty_status.empty_duration }}</h3>
                            <span class="hero-date">Vacía desde: <strong>{{ locationData.empty_status.empty_since }}</strong></span>
                        </div>

                        <div class="info-table-card mt-3">
                            <div class="info-data-row">
                                <span class="data-label">Causa / Referencia:</span>
                                <span class="data-value font-bold">{{ locationData.empty_status.empty_reason }}</span>
                            </div>
                            <div class="info-data-row flex-align-center" v-if="locationData.empty_status.last_product">
                                <span class="data-label">Último producto retirado:</span>
                                <span class="data-value last-product-val">
                                    <img 
                                        v-if="locationData.empty_status.last_product_image_url" 
                                        :src="locationData.empty_status.last_product_image_url" 
                                        class="last-prod-thumb" 
                                        loading="lazy"
                                        @error="onImgError"
                                    />
                                    <span>{{ locationData.empty_status.last_product }}</span>
                                </span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Action Buttons Footer -->
            <div class="action-buttons-group">
                <Button 
                    label="Escanear otra ubicación" 
                    icon="fa fa-refresh" 
                    class="p-button-primary btn-scan-another" 
                    @click="resetScan"
                />
                <Button 
                    label="Volver a Tareas" 
                    icon="fa fa-arrow-left" 
                    class="p-button-secondary p-button-outlined btn-back" 
                    @click="exitFlow"
                />
            </div>
        </div>
    </div>
</template>

<script>
import QRScannerComponent from '../QRScannerComponent/QRScannerComponent.vue';
import Button from 'primevue/button';
import InputText from 'primevue/inputtext';
import { useGeneralStore } from "../../store/index";

export default {
    name: 'LocationPreviewComponent',
    components: {
        QRScannerComponent,
        Button,
        InputText
    },
    data() {
        return {
            store: useGeneralStore(),
            scannerKey: 1,
            manualBarcode: "",
            isSearching: false,
            isManualFocused: false,
            locationData: null,
            activeTab: 'stock'
        };
    },
    methods: {
        onManualBlur() {
            setTimeout(() => {
                this.isManualFocused = false;
            }, 250);
        },
        onImgError(event) {
            if (event && event.target) {
                event.target.style.display = 'none';
                if (event.target.nextElementSibling) {
                    event.target.nextElementSibling.style.display = 'flex';
                }
            }
        },
        exitFlow() {
            this.manualBarcode = "";
            this.locationData = null;
            this.store.mandatory_uncompleted.doneMandatory();
        },
        resetScan() {
            this.manualBarcode = "";
            this.locationData = null;
            this.activeTab = 'stock';
            this.scannerKey++;
        },
        async handleLocationScan(data) {
            if (this.isSearching) return;
            let barcode = "";
            try {
                let parsed = typeof data === 'string' ? JSON.parse(data) : data;
                barcode = (parsed && (parsed.barcode || parsed.name)) ? (parsed.barcode || parsed.name) : String(data);
            } catch (e) {
                barcode = String(data);
            }
            barcode = barcode.trim();
            if (!barcode) return;
            await this.fetchLocationInfo(barcode);
        },
        async submitManual() {
            const clean = this.manualBarcode.trim();
            if (!clean || this.isSearching) return;
            await this.fetchLocationInfo(clean);
        },
        async fetchLocationInfo(barcode) {
            this.isSearching = true;
            try {
                const clientTimeZone = Intl.DateTimeFormat().resolvedOptions().timeZone;
                const res = await this.store.callOdoo("location_preview", "", {
                    barcode: barcode,
                    tz: clientTimeZone
                });

                if (res && res.status === 'ok') {
                    this.locationData = res;
                    // Determinar pestaña inicial inteligente
                    if (res.empty_status.is_empty) {
                        this.activeTab = 'empty';
                    } else {
                        this.activeTab = 'stock';
                    }
                    if (this.$toast) {
                        this.$toast.add({
                            severity: 'success',
                            summary: 'Ubicación Encontrada',
                            detail: res.location.complete_name,
                            life: 2500
                        });
                    }
                } else {
                    const errMsg = (res && res.message) ? res.message : "No se encontró la ubicación.";
                    if (this.$toast) {
                        this.$toast.add({
                            severity: 'error',
                            summary: 'Error',
                            detail: errMsg,
                            life: 4000
                        });
                    }
                }
            } catch (e) {
                if (this.$toast) {
                    this.$toast.add({
                        severity: 'error',
                        summary: 'Error de Conexión',
                        detail: 'No se pudo consultar la información de la ubicación.',
                        life: 4000
                    });
                }
            } finally {
                this.isSearching = false;
            }
        }
    }
};
</script>

<style scoped>
.location-preview-container {
    width: 100vw;
    min-height: calc(100vh - var(--o-we-toolbar-height, 46px));
    height: 100%;
    background-color: #f8f9fa;
    display: flex;
    flex-direction: column;
    overflow-y: auto;
    padding-bottom: 3rem;
}

.preview-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 1rem 1.25rem;
    background-color: #ffffff;
    border-bottom: 1px solid #e9ecef;
}

.header-titles .title {
    margin: 0;
    font-size: 1.2rem;
    font-weight: 700;
    color: #212529;
    display: flex;
    align-items: center;
}

.header-titles .subtitle {
    margin: 0.2rem 0 0 0;
    font-size: 0.85rem;
    color: #6c757d;
}

.close-btn {
    font-size: 1.2rem;
    color: #6c757d;
}

.scanner-body {
    padding: 1rem;
    display: flex;
    flex-direction: column;
    gap: 1.25rem;
    max-width: 650px;
    margin: 0 auto;
    width: 100%;
}

.scanner-card {
    background: #fff;
    border-radius: 12px;
    overflow: hidden;
    padding: 0.5rem;
}

.manual-input-section {
    background: #ffffff;
    border-radius: 12px;
    padding: 1.25rem;
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
}

.manual-label {
    font-size: 0.9rem;
    font-weight: 600;
    color: #495057;
}

.input-row {
    display: flex;
    gap: 0.5rem;
}

.manual-input {
    flex: 1;
}

.result-body {
    padding: 1rem;
    display: flex;
    flex-direction: column;
    gap: 1rem;
    max-width: 800px;
    margin: 0 auto;
    width: 100%;
}

.location-card {
    background: #ffffff;
    border-radius: 12px;
    padding: 1.25rem;
    border: 1px solid #dee2e6;
}

.location-main-row {
    display: flex;
    align-items: center;
    gap: 0.85rem;
    margin-bottom: 1rem;
}

.location-badge-icon {
    width: 48px;
    height: 48px;
    background: #e7f1ff;
    color: #0d6efd;
    border-radius: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.5rem;
    flex-shrink: 0;
}

.location-title-box {
    display: flex;
    flex-direction: column;
}

.location-name {
    margin: 0;
    font-size: 1.2rem;
    font-weight: 700;
    color: #212529;
    word-break: break-word;
}

.location-barcode-text {
    font-size: 0.85rem;
    color: #6c757d;
    margin-top: 0.2rem;
}

.status-chips-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 0.6rem;
}

.status-chip {
    padding: 0.6rem 0.85rem;
    border-radius: 8px;
    font-size: 0.82rem;
    font-weight: 600;
    display: flex;
    align-items: center;
    gap: 0.5rem;
    cursor: pointer;
    transition: transform 0.15s ease;
}

.status-chip:active {
    transform: scale(0.98);
}

.chip-empty {
    background: #d1e7dd;
    color: #0f5132;
    border: 1px solid #badbcc;
}

.chip-has-stock {
    background: #cfe2ff;
    color: #084298;
    border: 1px solid #b6d4fe;
}

.chip-unblocked {
    background: #e2f0d9;
    color: #276a3c;
    border: 1px solid #c5e0b4;
}

.chip-blocked {
    background: #f8d7da;
    color: #842029;
    border: 1px solid #f5c2c7;
}

.chip-expired {
    background: #fff3cd;
    color: #664d03;
    border: 1px solid #ffecb5;
}

.chip-cycle {
    background: #e8d5f5;
    color: #59257d;
    border: 1px solid #d8b8ee;
}

.chip-reservations {
    background: #ffe8cc;
    color: #8f4b00;
    border: 1px solid #ffd8a8;
}

.chip-muted {
    background: #e9ecef;
    color: #6c757d;
    border: 1px solid #dee2e6;
}

.tab-buttons-container {
    display: flex;
    gap: 0.4rem;
    overflow-x: auto;
    padding-bottom: 0.25rem;
}

.tab-btn {
    border: none;
    background: #ffffff;
    border: 1px solid #ced4da;
    border-radius: 8px;
    padding: 0.55rem 0.85rem;
    font-size: 0.82rem;
    font-weight: 600;
    color: #495057;
    white-space: nowrap;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 0.4rem;
    transition: all 0.2s ease;
}

.tab-btn.active {
    background: #0d6efd;
    color: #ffffff;
    border-color: #0d6efd;
}

.tab-content-card {
    background: #ffffff;
    border-radius: 12px;
    padding: 1.25rem;
    min-height: 220px;
}

.empty-state-box, .stock-occupied-box {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    text-align: center;
    padding: 2.5rem 1rem;
}

.empty-icon {
    font-size: 3rem;
    color: #adb5bd;
    margin-bottom: 1rem;
}

.ok-icon {
    font-size: 3rem;
    color: #198754;
    margin-bottom: 1rem;
}

.occupied-icon {
    font-size: 3rem;
    margin-bottom: 1rem;
}

.stock-totals-bar {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    background: #f8f9fa;
    border: 1px solid #e9ecef;
    border-radius: 8px;
    padding: 0.75rem 0.5rem;
    margin-bottom: 1rem;
    text-align: center;
}

.total-metric {
    display: flex;
    flex-direction: column;
}

.metric-num {
    font-size: 1.15rem;
    font-weight: 700;
}

.metric-label {
    font-size: 0.75rem;
    color: #6c757d;
    text-transform: uppercase;
}

.font-blue { color: #0d6efd; }
.font-orange { color: #fd7e14; }
.font-green { color: #198754; }

.product-cards-list {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
}

.product-item-card {
    background: #fdfdfd;
    border: 1px solid #e9ecef;
    border-radius: 8px;
    padding: 0.85rem;
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
}

.item-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 0.8rem;
}

.product-code {
    background: #e9ecef;
    color: #495057;
    padding: 2px 6px;
    border-radius: 4px;
    font-family: monospace;
    font-weight: 700;
}

.product-lot {
    color: #6c757d;
}

.product-name {
    font-size: 0.95rem;
    font-weight: 600;
    color: #212529;
}

.item-quantities-row {
    display: flex;
    gap: 0.5rem;
    font-size: 0.8rem;
    margin-top: 0.2rem;
}

.qty-pill {
    background: #e9ecef;
    padding: 3px 8px;
    border-radius: 12px;
}

.qty-pill.reserved {
    background: #fff3cd;
    color: #856404;
}

.qty-pill.available {
    background: #d1e7dd;
    color: #0f5132;
}

.alert-banner {
    display: flex;
    align-items: center;
    gap: 0.85rem;
    padding: 1rem;
    border-radius: 8px;
    margin-bottom: 1rem;
}

.alert-danger {
    background: #f8d7da;
    border: 1px solid #f5c2c7;
    color: #842029;
}

.alert-warning {
    background: #fff3cd;
    border: 1px solid #ffecb5;
    color: #664d03;
}

.alert-banner i {
    font-size: 1.6rem;
}

.alert-title {
    margin: 0;
    font-size: 1rem;
    font-weight: 700;
}

.alert-desc {
    font-size: 0.82rem;
}

.info-table-card {
    background: #fdfdfd;
    border: 1px solid #e9ecef;
    border-radius: 8px;
    padding: 0.75rem 1rem;
}

.info-data-row {
    display: flex;
    justify-content: space-between;
    padding: 0.5rem 0;
    border-bottom: 1px solid #f1f3f5;
    font-size: 0.88rem;
}

.info-data-row:last-child {
    border-bottom: none;
}

.data-label {
    color: #6c757d;
}

.data-value {
    color: #212529;
    text-align: right;
}

.time-relative {
    color: #0d6efd;
    font-weight: 600;
}

.cycle-count-card, .reservation-item-card {
    background: #fdfdfd;
    border: 1px solid #e9ecef;
    border-radius: 8px;
    padding: 0.85rem;
    margin-bottom: 0.75rem;
}

.cc-header, .res-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.4rem;
}

.cc-code, .res-picking {
    font-weight: 700;
    color: #0d6efd;
    font-size: 0.95rem;
}

.cc-state-badge {
    background: #e8d5f5;
    color: #59257d;
    padding: 2px 8px;
    border-radius: 12px;
    font-size: 0.75rem;
    font-weight: 600;
}

.res-product {
    font-weight: 600;
    font-size: 0.9rem;
    margin-bottom: 0.4rem;
}

.res-details-row {
    display: flex;
    flex-wrap: wrap;
    gap: 0.75rem;
    font-size: 0.78rem;
    color: #6c757d;
}

.empty-age-hero {
    display: flex;
    flex-direction: column;
    align-items: center;
    text-align: center;
    padding: 1.5rem 1rem;
    background: #d1e7dd;
    border-radius: 10px;
    border: 1px solid #badbcc;
}

.hero-icon {
    font-size: 2.5rem;
    margin-bottom: 0.5rem;
}

.hero-duration {
    margin: 0;
    font-size: 1.4rem;
    font-weight: 800;
    color: #0f5132;
}

.hero-date {
    font-size: 0.85rem;
    color: #146c43;
    margin-top: 0.25rem;
}

.product-card-flex, .res-card-flex {
    display: flex;
    align-items: center;
    gap: 0.85rem;
}

.product-thumb-container {
    width: 60px;
    height: 60px;
    min-width: 60px;
    min-height: 60px;
    border-radius: 8px;
    overflow: hidden;
    background: #f1f3f5;
    border: 1px solid #e9ecef;
    display: flex;
    align-items: center;
    justify-content: center;
    position: relative;
    flex-shrink: 0;
}

.product-thumb-container.mini-thumb {
    width: 44px;
    height: 44px;
    min-width: 44px;
    min-height: 44px;
    border-radius: 6px;
}

.product-thumb-img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
}

.product-thumb-fallback {
    display: none;
    width: 100%;
    height: 100%;
    align-items: center;
    justify-content: center;
    background: #e9ecef;
    color: #adb5bd;
    font-size: 1.25rem;
}

.product-details-col, .res-details-col {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
}

.last-product-val {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    justify-content: flex-end;
}

.last-prod-thumb {
    width: 32px;
    height: 32px;
    border-radius: 4px;
    object-fit: cover;
    border: 1px solid #dee2e6;
}

.action-buttons-group {
    display: flex;
    flex-direction: column;
    gap: 0.6rem;
    margin-top: 0.5rem;
}

.btn-scan-another, .btn-back {
    width: 100%;
}
</style>
