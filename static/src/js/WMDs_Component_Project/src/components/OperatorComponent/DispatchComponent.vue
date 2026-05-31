<template>
    <div 
        class="test-flow-container"
        @touchstart="handleTouchStart"
        @touchmove="handleTouchMove"
        @touchend="handleTouchEnd"
    >
        <!-- Pull to refresh indicator -->
        <div v-if="pulling" class="pull-to-refresh-indicator" :style="{ height: pullDistance + 'px', opacity: pullDistance / 100 }">
            <i class="fa fa-refresh" :class="{ 'fa-spin': refreshing }"></i>
            <span>{{ refreshing ? 'Actualizando...' : 'Tire para actualizar' }}</span>
        </div>

        <!-- ═══════════ MODO INDIVIDUAL (ESCANEO) ═══════════ -->
        <div v-if="dispatchMode === 'individual' && !showPrintView" class="individual-mode">

            <!--seleccion de carrier-->
            <div v-if="!sessionCarrierId && !loadingSession" class="carrier-select-overlay">
                <div class="carrier-select-card">
                    <i class="fa fa-truck" style="font-size: 2.5rem; color: #3498db; margin-bottom: 10px;"></i>
                    <h3 style="margin: 0 0 5px;">Seleccione el Carrier</h3>
                    <span style="font-size: 0.8rem; color: #95a5a6; margin-bottom: 15px;">
                        La sesión será exclusiva para este carrier
                    </span>
                    <select v-model="selectedCarrierId" class="carrier-dropdown">
                        <option :value="null" disabled>-- Seleccionar --</option>
                        <option v-for="c in carrierList" :key="c.id" :value="c.id">{{ c.name }}</option>
                    </select>
                    <Button
                        label="Iniciar Sesión"
                        icon="fa fa-check"
                        class="p-button-success"
                        :disabled="!selectedCarrierId"
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

            <!-- ── Loading session ── -->
            <div v-else-if="loadingSession" class="carrier-select-overlay">
                <div class="carrier-select-card">
                    <i class="fa fa-spin fa-spinner" style="font-size: 2rem;"></i>
                    <span>Recuperando sesión...</span>
                </div>
            </div>

            <!-- ── Contenido principal (solo si hay carrier seleccionado) ── -->
            <template v-if="sessionCarrierId">

                <!-- Session recovery banner -->
                <div v-if="sessionRecovered" class="session-banner">
                    <i class="fa fa-info-circle"></i>
                    Sesión recuperada — {{ so.length }} escaneo(s) previo(s) restaurados.
                    <span style="margin-left: 8px; font-weight: bold;">| Carrier: {{ sessionCarrierName }}</span>
                    <Button icon="fa fa-times" class="p-button-text p-button-sm session-banner-close" @click="sessionRecovered = false" />
                </div>

                <!-- Carrier indicator -->
                <div class="carrier-indicator flex justify-content-between align-items-center">
                    <div>
                        <i class="fa fa-truck"></i> {{ sessionCarrierName }}
                        <Button
                            v-if="so.length === 0"
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
                    <div v-if="ready" class="scanner-wrapper">
                        <BarcodeScannerComponent 
                            :key="scannerKey"
                            instructions="Escanea la guía para despacho"
                            :onScan="(data) => searchAndValidateSO(data)"
                            :disableFocus="cancelledModal.show"
                        />
                    </div>
                </div>

                <div class="buttons-col">
                    <Button v-if="so.length > 0"
                        @click="dispatchToCarrier"
                        class="p-button-success p-button-sm" 
                        label="Entregar a paquetería" 
                        icon="fa fa-truck"
                        :loading="dispatching"
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
                            <span class="log-title">Resumen de Despacho</span>
                            <Button icon="fa fa-trash" class="p-button-danger p-button-text p-button-sm" label="Limpiar Todo" @click="clearAllOrders" v-if="so.length > 0"/>
                        </div>
                    </div>

                    <!-- Cancelled orders: now handled by modal -->

                    <!-- Visualization of n/total -->
                    <div class="scan-summary-grid" v-if="scanSummary.length > 0">
                        <div v-for="item in paginatedScanSummary" :key="item.so_name" class="summary-card">
                            <div class="summary-so">{{ item.so_name }}</div>
                            <div class="summary-carrier" v-if="item.carrier_name">
                                <i class="fa fa-truck"></i> {{ item.carrier_name }}
                            </div>
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
                        <div v-for="order in paginatedSo" :key="order.name" class="log-item" :class="{ 'log-item-cancelled': order.so_state === 'cancel' }">
                            <div class="log-item-info">
                                <div>
                                    <i class="fa fa-barcode barcode-icon"></i>
                                    {{ order.name }}
                                    <small class="text-info ml-2">({{ order.current }}/{{ order.total }})</small>
                                    <span v-if="order.so_state === 'cancel'" class="badge-cancelled">CANCELADO</span>
                                </div>
                                <div v-if="order.product_name" class="log-item-product">
                                    <small>{{ order.product_name }}</small>
                                </div>
                            </div>
                            <Button v-if="order.so_state !== 'cancel'" icon="fa fa-times" class="p-button-rounded p-button-danger p-button-text" @click="removeOrder(order)" />
                        </div>

                        
                        <div v-if="so.length === 0" class="empty-log">
                            <i class="fa fa-archive search-icon"></i>
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

        <!-- ═══════════ VISTA DE IMPRESION (HOJA DE SALIDA) ═══════════ -->
        <div v-if="showPrintView" class="print-overlay">
            <div class="print-actions no-print">
                <Button 
                    label="Imprimir Hoja de Salida" 
                    icon="fa fa-print" 
                    class="p-button-success p-button-lg"
                    @click="printSheet"
                />
                <Button 
                    label="Cerrar y Finalizar" 
                    icon="fa fa-check-circle" 
                    class="p-button-info p-button-lg"
                    @click="finishAndExit"
                />
            </div>

            <div class="print-sheet" ref="printSheet">
                <div class="sheet-header">
                    <div class="sheet-logo">
                        <h1>HOJA DE SALIDA</h1>
                        <span class="sheet-subtitle">Registro de Despacho a Paquetería</span>
                    </div>
                    <div class="sheet-meta">
                        <div><strong>Carrier:</strong> {{ printData.carrier_name || 'N/A' }}</div>
                        <div><strong>Fecha de Despacho:</strong> {{ printData.date_end_formatted }}</div>
                        <div><strong>Operador:</strong> {{ printData.operator_name }}</div>
                        <div><strong>Sesión ID:</strong> #{{ printData.session_id }}</div>
                        <div><strong>Total Paquetes:</strong> {{ printData.total_lines }}</div>
                    </div>
                </div>

                <div class="sheet-divider"></div>

                <!-- Resumen por Orden -->
                <div class="sheet-section">
                    <h3>Resumen por Orden</h3>
                    <table class="sheet-table summary-table">
                        <thead>
                            <tr>
                                <th>#</th>
                                <th>Orden SO</th>
                                <th>Carrier</th>
                                <th>Producto(s)</th>
                                <th>EI Escaneadas</th>
                                <th>Total EI</th>
                                <th>Estado</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr v-for="(summary, idx) in printData.so_summary" :key="idx">
                                <td>{{ idx + 1 }}</td>
                                <td><strong>{{ summary.so_name }}</strong></td>
                                <td>{{ summary.carrier_name || 'N/A' }}</td>
                                <td class="product-cell">{{ summary.product_name || 'N/A' }}</td>
                                <td>{{ summary.scanned_count }}</td>
                                <td>{{ summary.total_ei }}</td>
                                <td>
                                    <span :class="summary.scanned_count >= summary.total_ei ? 'status-complete' : 'status-partial'">
                                        {{ summary.scanned_count >= summary.total_ei ? 'COMPLETA' : 'PARCIAL' }}
                                    </span>
                                </td>
                            </tr>
                        </tbody>
                    </table>
                </div>

                <!-- Detalle de Escaneos -->
                <div class="sheet-section">
                    <h3>Detalle de Escaneos</h3>
                    <table class="sheet-table detail-table">
                        <thead>
                            <tr>
                                <th>#</th>
                                <th>Etiqueta EI</th>
                                <th>Orden SO</th>
                                <th>Producto</th>
                                <th>Carrier</th>
                                <th>Fecha/Hora Escaneo</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr v-for="(line, idx) in printData.lines" :key="idx">
                                <td>{{ idx + 1 }}</td>
                                <td><strong>{{ line.ei_name }}</strong></td>
                                <td>{{ line.so_name }}</td>
                                <td class="product-cell">{{ line.product_name || 'N/A' }}</td>
                                <td>{{ line.carrier_name || 'N/A' }}</td>
                                <td>{{ formatDateTime(line.scan_datetime) }}</td>
                            </tr>
                        </tbody>
                    </table>
                </div>

                <!-- Firmas -->
                <div class="sheet-signatures">
                    <div class="signature-box">
                        <div class="signature-line"></div>
                        <span>Operador de Despacho</span>
                    </div>
                    <div class="signature-box">
                        <div class="signature-line"></div>
                        <span>Recibe Paquetería</span>
                    </div>
                </div>
            </div>
        </div>
    <!-- ═══════════ MODAL CANCELADOS ═══════════ -->
    <CancelledModalComponent
        :show="cancelledModal.show"
        :pending="cancelledModal.pending"
        :confirmed="cancelledModal.confirmed"
        :lastError="cancelledModal.lastError"
        :onScanCancelled="confirmCancelledScan"
    />
    </div>

</template>

<script>
import BarcodeScannerComponent from '../QRScannerComponent/BarcodeScannerComponent.vue';
import CancelledModalComponent from './CancelledModalComponent.vue';
import Button from 'primevue/button';
import { useGeneralStore } from "../../store/index";

export default {
    name: "DispatchComponent",
    components: {
        BarcodeScannerComponent,
        CancelledModalComponent,
        Button
    },
    data() {
        return {
            store: useGeneralStore(),
            so: [],
            ready: false,
            scannerKey: 0,
            dispatchMode: 'individual',
            pendingFullItems: [],
            sessionId: null,
            loadingSession: true,
            sessionRecovered: false,
            currentPage: 1,
            summaryCurrentPage: 1,

            // ── Carrier ──
            carrierList: [],
            selectedCarrierId: null,
            sessionCarrierId: null,
            sessionCarrierName: '',
            // ── Impresión ──
            showPrintView: false,
            printData: {
                session_id: null,
                operator_name: '',
                carrier_name: '',
                date_start: '',
                date_end_formatted: '',
                lines: [],
                so_summary: [],
                total_lines: 0
            },
            dispatching: false,
            // Pull to refresh state
            startY: 0,
            pullDistance: 0,
            pulling: false,
            refreshing: false,
            maxPullDistance: 100,
            // ── Modal cancelados ──
            cancelledModal: {
                show: false,
                pending: [],       // [{ name, so_name }]
                confirmed: [],     // nombres EI ya escaneados
                inputValue: '',
                lastError: '',
                onFinish: null,    // callback opcional tras completar
            }
        }
    },
    computed: {
        scanSummary() {
            const summaryMap = {};
            this.so.forEach(item => {
                if (!summaryMap[item.so_name]) {
                    summaryMap[item.so_name] = { 
                        so_name: item.so_name, 
                        scanned: item.dispatched_count || 0, 
                        total: item.total,
                        newly_scanned: 0,
                        carrier_name: item.carrier_name || ''
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
        },
        cancelledOrdersList() {
            const cancelled = this.so.filter(o => o.so_state === 'cancel');
            return [...new Set(cancelled.map(o => o.so_name))];
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
        console.log("Action: DispatchComponent mounted");

        await this.fetchCarrierList();
        await this.recoverSession();

        setTimeout(() => {
            this.ready = true;
            this.loadingSession = false;
            console.log("Action: Component ready state set to true");
        }, 500);
        
        if (this.dispatchMode === 'full') {
            this.fetchPendingFullItems();
        }
    },
    methods: {
        async refreshData() {
            this.loadingSession = true;
            await this.recoverSession();
            if (this.dispatchMode === 'full') {
                await this.fetchPendingFullItems();
            }
            this.loadingSession = false;
            this.scannerKey++;
        },
        // ═══════════════════════════════════════════
        // CARRIER — Selección y carga
        // ═══════════════════════════════════════════

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
            const c = this.carrierList.find(x => x.id === this.selectedCarrierId);
            if (c) {
                this.sessionCarrierId = c.id;
                this.sessionCarrierName = c.name;
            }
        },

        // ═══════════════════════════════════════════
        // SESIÓN PERSISTENTE — Métodos principales
        // ═══════════════════════════════════════════

        async recoverSession() {
            try {
                const response = await this.store.callOdoo("get_dispatch_session", "", {
                    operator_login: this.store.role.email
                });

                if (response && response.active && response.lines && response.lines.length > 0) {
                    this.sessionId = response.session_id;

                    // Restaurar carrier de la sesión
                    if (response.carrier_id) {
                        this.sessionCarrierId = response.carrier_id;
                        this.sessionCarrierName = response.carrier_name || '';
                    }
                    
                    this.so = response.lines.map(line => ({
                        name: line.ei_name,
                        so_name: line.so_name,
                        so_state: line.so_state,
                        total: line.total_ei,
                        current: line.sequence_number,
                        dispatched_count: line.dispatched_count,
                        product_name: line.product_name,
                        carrier_name: line.carrier_name,
                        scan_datetime: line.scan_datetime,
                        line_id: line.line_id,
                    }));

                    this.sessionRecovered = true;
                    this.$nextTick(() => {
                        this.currentPage = 1;
                        this.summaryCurrentPage = 1;
                    });
                    console.log(`Action: Sesión ${this.sessionId} recuperada con ${this.so.length} líneas`);

                    // Abrir modal si hay canceladas en la sesión recuperada
                    const cancelledLines = this.so.filter(o => o.so_state === 'cancel');
                    if (cancelledLines.length > 0) {
                        this.openCancelledModal(
                            cancelledLines.map(o => ({ name: o.name, so_name: o.so_name })),
                            null // sin callback especial al recuperar sesión
                        );
                    }
                    
                    if (this.$toast) {
                        this.$toast.add({ 
                            severity: 'info', 
                            summary: 'Sesión recuperada', 
                            detail: `Se restauraron ${this.so.length} escaneo(s) de tu sesión anterior.`, 
                            life: 4000 
                        });
                    }
                } else if (response && response.active) {
                    this.sessionId = response.session_id;
                    if (response.carrier_id) {
                        this.sessionCarrierId = response.carrier_id;
                        this.sessionCarrierName = response.carrier_name || '';
                    }
                }
            } catch (e) {
                console.error("Error recuperando sesión:", e);
            }
        },

        async persistScanToSession(orderData) {
            try {
                const response = await this.store.callOdoo("save_dispatch_session_line", "", {
                    operator_login: this.store.role.email,
                    ei_name: orderData.name,
                    so_name: orderData.so_name,
                    total: orderData.total,
                    current: orderData.current,
                    dispatched_count: orderData.dispatched_count || 0,
                    carrier_id: this.sessionCarrierId,
                });

                // Carrier mismatch — rechazado por el backend
                if (response && response.carrier_mismatch) {
                    const idx = this.so.findIndex(o => o.name === orderData.name);
                    if (idx !== -1) this.so.splice(idx, 1);
                    if (this.$toast) {
                        this.$toast.add({
                            severity: 'error',
                            summary: 'Carrier No Coincide',
                            detail: response.mismatch_message,
                            life: 6000
                        });
                    }
                    return;
                }

                if (response && response.ok) {
                    this.sessionId = response.session_id;
                    const idx = this.so.findIndex(o => o.name === orderData.name);
                    if (idx !== -1) {
                        this.so[idx].line_id = response.line_id;
                        this.so[idx].product_name = response.product_name || '';
                        this.so[idx].carrier_name = response.carrier_name || '';
                    }
                }
            } catch (e) {
                console.error("Error persistiendo escaneo:", e);
            }
        },

        async removeFromSession(eiName, cancelledRemoval = false) {
            try {
                await this.store.callOdoo("remove_dispatch_session_line", "", {
                    operator_login: this.store.role.email,
                    ei_name: eiName,
                    cancelled_removal: cancelledRemoval,
                });
            } catch (e) {
                console.error("Error eliminando de sesión:", e);
            }
        },

        async clearSession() {
            try {
                await this.store.callOdoo("clear_dispatch_session", "", {
                    operator_login: this.store.role.email,
                });
            } catch (e) {
                console.error("Error limpiando sesión:", e);
            }
        },

        async completeSession() {
            try {
                const response = await this.store.callOdoo("complete_dispatch_session", "", {
                    operator_login: this.store.role.email,
                });

                if (response && response.ok) {
                    this.printData = {
                        session_id: response.session_id,
                        operator_name: response.operator_name,
                        carrier_name: response.carrier_name || this.sessionCarrierName || '',
                        date_start: response.date_start,
                        date_end_formatted: this.formatDateTime(response.date_end),
                        lines: response.lines,
                        so_summary: response.so_summary,
                        total_lines: response.total_lines,
                    };
                    return true;
                }
                return false;
            } catch (e) {
                console.error("Error completando sesión:", e);
                return false;
            }
        },

        async cancelSession() {
            try {
                await this.store.callOdoo("cancel_dispatch_session", "", {
                    operator_login: this.store.role.email,
                });
                this.sessionId = null;
            } catch (e) {
                console.error("Error cancelando sesión:", e);
            }
        },

        async changeCarrier() {
            await this.cancelSession();
            this.sessionCarrierId = null;
            this.sessionCarrierName = '';
            this.selectedCarrierId = null;
            this.so = [];
        },

        async removeCancelledOrders() {
            const cancelled = this.so.filter(o => o.so_state === 'cancel');
            for (const order of cancelled) {
                await this.removeFromSession(order.name);
                const idx = this.so.findIndex(o => o.name === order.name);
                if (idx !== -1) {
                    this.so.splice(idx, 1);
                }
            }
            if (this.$toast) {
                this.$toast.add({
                    severity: 'success',
                    summary: 'Pedidos removidos',
                    detail: 'Se han removido los pedidos cancelados de la lista.',
                    life: 3000
                });
            }
        },



        setMode(mode) {
            this.dispatchMode = mode;
            if (mode === 'full') {
                this.fetchPendingFullItems();
            }
        },

        async fetchPendingFullItems() {
            try {
                const response = await this.store.callOdoo("pending_full_dispatch", "", {});
                if (response && Array.isArray(response)) {
                    this.pendingFullItems = response.map(item => ({
                        ...item,
                        dispatchQty: item.qty
                    }));
                }
            } catch (e) {
                console.error("Error fetching full items", e);
            }
        },

        async searchAndValidateSO(data) {
            try {
                if (this.so.some(o => o.name === data)) {
                    if (this.$toast) {
                        this.$toast.add({ 
                            severity: 'warn', 
                            summary: 'Duplicado', 
                            detail: `La etiqueta ${data} ya fue escaneada en esta sesión.`, 
                            life: 3000 
                        });
                    }
                    this.restartScanner();
                    return;
                }

                let response = await this.store.callOdoo("validate_attachment_guide", "", {
                    attachment_id: data,
                });

                if (response.valid) {
                    if (response.so_state === 'cancel') {
                        if(this.$toast) {
                            this.$toast.add({ 
                                severity: 'error', 
                                summary: 'Pedido cancelado', 
                                detail: `El pedido ${response.so} está cancelado. Se agregará a la lista en rojo para que proceda a removerlo físicamente.`, 
                                life: 6000 
                            });
                        }
                        const newItem = {
                            name: response.name,
                            so_name: response.so,
                            so_state: 'cancel',
                            total: response.total,
                            current: response.current,
                            dispatched_count: response.dispatched_count || 0,
                            product_name: '',
                            carrier_name: '',
                            scan_datetime: new Date().toISOString(),
                            line_id: null,
                        };
                        this.so.push(newItem);
                        await this.persistScanToSession(newItem);

                        const cancelledLines = this.so.filter(o => o.so_state === 'cancel');
                        if (cancelledLines.length > 0) {
                            this.openCancelledModal(
                                cancelledLines.map(o => ({ name: o.name, so_name: o.so_name })),
                                null
                            );
                        }
                    } else if (response.state && response.state.dispatched) {

                        if(this.$toast) {
                            this.$toast.add({ 
                                severity: 'error', 
                                summary: 'Guía ya Despachada', 
                                detail: `La guía ${data} ya ha sido procesada anteriormente.`, 
                                life: 4000 
                            });
                        }
                    } else if (response.state && !response.state.on_dock) {
                        if(this.$toast) {
                            this.$toast.add({ 
                                severity: 'error', 
                                summary: 'Ubicación incorrecta', 
                                detail: `La guía ${data} no se encuentra en un DOCK y no puede ser despachada.`, 
                                life: 4000 
                            });
                        }
                    } else {
                        const newItem = {
                            name: response.name,
                            so_name: response.so,
                            so_state: response.so_state,
                            total: response.total,
                            current: response.current,
                            dispatched_count: response.dispatched_count || 0,
                            product_name: '',
                            carrier_name: '',
                            scan_datetime: new Date().toISOString(),
                            line_id: null,
                        };
                        this.so.push(newItem);

                        // ── Persistir en backend (valida carrier) ──
                        await this.persistScanToSession(newItem);
                    }
                } else {
                    if(this.$toast) {
                        this.$toast.add({ 
                            severity: 'error', 
                            summary: 'Guía inválida', 
                            detail: 'El código escaneado no corresponde a una guía válida para despacho o el formato es incorrecto.', 
                            life: 4000 
                        });
                    }
                }
                
                this.restartScanner();
            } catch (e) {
                this.restartScanner();
            }
        },

        restartScanner() {
            this.scannerKey++;
            // Silent refresh after each scan
            this.recoverSession();
        },

        async dispatchToCarrier() {
            if (this.so.length === 0) {
                return;
            }

            const cancelledOrders = this.so.filter(o => o.so_state === 'cancel');
            if (cancelledOrders.length > 0) {
                // Abrir modal obligatorio antes de poder despachar
                this.openCancelledModal(
                    cancelledOrders.map(o => ({ name: o.name, so_name: o.so_name })),
                    () => this.dispatchToCarrier() // reintentar despacho tras confirmar
                );
                return;
            }
            
            this.dispatching = true;

            try {
                const picks_ids = this.so.map(o => o.name);
                let response = await this.store.callOdoo("dispatch_orders", "", {
                    operator_login: this.store.role.email,
                    picks_ids: picks_ids 
                });

                if (response.status === "success" || response.status === "queued") {
                    if (response.status === "queued") {
                        if (this.$toast) {
                            this.$toast.add({
                                severity: 'info',
                                summary: 'Despacho encolado',
                                detail: 'Debido al volumen de paquetes (>10), el despacho se procesará en segundo plano. Puedes continuar usando la app.',
                                life: 8000
                            });
                        }
                    } else if (response.warning) {
                        this.$toast.add({ 
                            severity: 'warn', 
                            summary: 'Entrega parcial', 
                            detail: 'Se procesaron las guías, pero hay advertencias: ' + response.warning, 
                            life: 6000 
                        });
                    } else {
                        const isManager = this.store.role && (this.store.role.role === 'WMDs Manager' || (this.store.role.permissions && this.store.role.permissions.includes('WMDs Manager')));
                        if (!isManager) {
                            this.$toast.add({ 
                                severity: 'success', 
                                summary: 'Despacho completado', 
                                detail: 'Todas las órdenes han sido entregadas. Generando hoja de salida...', 
                                life: 4000 
                            });
                        }
                    }

                    const sessionCompleted = await this.completeSession();
                    
                    if (sessionCompleted) {
                        this.showPrintView = true;
                    } else {
                        this.generatePrintDataFromLocal();
                        this.showPrintView = true;
                    }

                    this.restartScanner(); 
                } else {

                    throw new Error(response.message || "Error desconocido");
                }
            } catch (e) {
                if(this.$toast) {
                    this.$toast.add({ 
                        severity: 'error', 
                        summary: 'Error de entrega', 
                        detail: 'No se pudo completar la entrega a paquetería. Detalle técnico: ' + (e.message || 'Error desconocido'), 
                        life: 5000 
                    });
                }
            } finally {
                this.dispatching = false;
            }
        },

        generatePrintDataFromLocal() {
            const now = new Date();
            const soSummary = {};

            this.so.forEach(item => {
                if (!soSummary[item.so_name]) {
                    soSummary[item.so_name] = {
                        so_name: item.so_name,
                        carrier_name: item.carrier_name || '',
                        product_name: item.product_name || '',
                        total_ei: item.total,
                        scanned_count: 0,
                        ei_list: []
                    };
                }
                soSummary[item.so_name].scanned_count++;
                soSummary[item.so_name].ei_list.push(item.name);
            });

            this.printData = {
                session_id: this.sessionId || 'N/A',
                operator_name: this.store.role.user || this.store.role.name || '',
                carrier_name: this.sessionCarrierName || '',
                date_start: '',
                date_end_formatted: this.formatDateTime(now.toISOString()),
                lines: this.so.map(item => ({
                    ei_name: item.name,
                    so_name: item.so_name,
                    product_name: item.product_name || '',
                    carrier_name: item.carrier_name || '',
                    scan_datetime: item.scan_datetime || '',
                })),
                so_summary: Object.values(soSummary),
                total_lines: this.so.length,
            };
        },

        // ═══════════════════════════════════════════
        // IMPRESIÓN — Hoja de Salida A4
        // ═══════════════════════════════════════════

       async printSheet() {
            this.iotPrinting = true;
            try {
                const response = await this.store.callOdoo("print_dispatch_sheet", "", {
                    session_id: this.printData.session_id,
                });
        
                if (response && response.ok && response.action) {
                    console.log("Acción nativa recibida. Buscando el puente con Odoo OWL...");

                    let actionService = null;

                    if (window.odoo && window.odoo.__WOWL_DEBUG__ && window.odoo.__WOWL_DEBUG__.root) {
                        actionService = window.odoo.__WOWL_DEBUG__.root.env.services.action;
                    }

                    if (!actionService) {
                        const webClient = document.querySelector('.o_web_client');
                        if (webClient && webClient.__owl__) {
                            const owlInstance = webClient.__owl__;
                            if (owlInstance.app && owlInstance.app.env) {
                                actionService = owlInstance.app.env.services.action;
                            } else if (owlInstance.env) {
                                actionService = owlInstance.env.services.action;
                            }
                        }
                    }

                    if (actionService) {
                        console.log("¡Puente Odoo-Vue encontrado! Enviando silenciosamente a IoT Box...");
                        await actionService.doAction(response.action);
                        
                        if (this.$toast) {
                            this.$toast.add({ severity: 'success', summary: 'Impresión enviada', detail: 'Hoja de salida enviada correctamente.', life: 3000 });
                        }
                    } else {
                        console.warn("No se pudo conectar Vue con el ActionManager de Odoo. Abriendo PDF...");
                        const pdfUrl = window.location.origin + `/report/pdf/wmds.report_dispatch_sheet_document/${this.printData.session_id}`;
                        window.open(pdfUrl, '_blank');
                    }

                } else {
                    console.error("Error del servidor:", response?.error);
                    if (this.$toast) {
                        this.$toast.add({ severity: 'error', summary: 'Error de impresión', detail: response?.error || 'No se recibió la acción.', life: 4000 });
                    }
                }
            } catch (e) {
                console.error("Error crítico en printSheet:", e);
            } finally {
                this.iotPrinting = false;
            }
        },

        finishAndExit() {
            this.showPrintView = false;
            this.so = [];
            this.sessionId = null;
            this.sessionCarrierId = null;
            this.sessionCarrierName = '';
            this.selectedCarrierId = null;
            this.printData = { session_id: null, operator_name: '', carrier_name: '', date_start: '', date_end_formatted: '', lines: [], so_summary: [], total_lines: 0 };
            this.store.mandatory_uncompleted.doneMandatory();
        },

        formatDateTime(isoString) {
            if (!isoString) return 'N/A';
            try {
                const d = new Date(isoString);
                if (isNaN(d.getTime())) return isoString;
                return d.toLocaleString('es-MX', {
                    year: 'numeric', month: '2-digit', day: '2-digit',
                    hour: '2-digit', minute: '2-digit', second: '2-digit',
                    hour12: false
                });
            } catch {
                return isoString;
            }
        },

        // ═══════════════════════════════════════════
        // ACCIONES DE LISTA — Con persistencia
        // ═══════════════════════════════════════════
       
        async exitFlow() {
            if (this.so.length > 0) {
                const action = confirm(
                    "Tienes escaneos en esta sesión.\n\n" +
                    "• Aceptar = Salir y CANCELAR la sesión actual\n" +
                    "• Cancelar = Volver al escaneo"
                );
                if (!action) return;
                await this.cancelSession();
            }
            this.so = [];
            this.sessionCarrierId = null;
            this.sessionCarrierName = '';
            this.selectedCarrierId = null;
            this.store.mandatory_uncompleted.doneMandatory();
        },

        async clearAllOrders() {
            if (!confirm("¿Estás seguro de limpiar todos los escaneos?\nEsto también cancelará la sesión actual.")) {
                return;
            }
            await this.clearSession();
            this.so = [];
        },

        async removeOrder(order) {
            const index = this.so.findIndex(o => o.name === order.name);
            if (index !== -1) {
                const eiName = this.so[index].name;
                this.so.splice(index, 1);
                await this.removeFromSession(eiName);
            }
        },

        async dispatchFullItem(item) {
            if (item.dispatchQty <= 0) return;
            if (item.dispatchQty > item.qty) {
                item.dispatchQty = item.qty;
                this.$toast.add({ severity: 'warn', summary: 'Cantidad ajustada', detail: 'Se ha ajustado automáticamente al máximo disponible.', life: 3000 });
            }
            try {
                const response = await this.store.callOdoo("dispatch_full_items", "", {
                    operator_login: this.store.role.email,
                    items: [{ move_id: item.id, qty: item.dispatchQty }]
                });
                if (response.status === "success") {
                    const isManager = this.store.role && (this.store.role.role === 'WMDs Manager' || (this.store.role.permissions && this.store.role.permissions.includes('WMDs Manager')));
                    if (!isManager) {
                        this.$toast.add({ severity: 'success', summary: 'Producto Despachado', detail: `${item.product} despachado correctamente.`, life: 2000 });
                    }
                    this.fetchPendingFullItems();
                }
            } catch (e) {
                this.$toast.add({ severity: 'error', summary: 'Error de despacho', detail: 'Detalle técnico: ' + (e.message || 'Error desconocido'), life: 4000 });
            }
        },

        async dispatchSelectedFull() {
            let itemsToDispatch = this.pendingFullItems.filter(i => i.dispatchQty > 0);
            if (itemsToDispatch.length === 0) return;
            let adjusted = false;
            itemsToDispatch = itemsToDispatch.map(i => {
                if (i.dispatchQty > i.qty) { i.dispatchQty = i.qty; adjusted = true; }
                return { move_id: i.id, qty: i.dispatchQty };
            });
            if (adjusted) {
                this.$toast.add({ severity: 'warn', summary: 'Ajuste de cantidades', detail: 'Algunas cantidades fueron ajustadas.', life: 3000 });
            }
            try {
                const response = await this.store.callOdoo("dispatch_full_items", "", {
                    operator_login: this.store.role.email,
                    items: itemsToDispatch
                });
                if (response.status === "success") {
                    const isManager = this.store.role && (this.store.role.role === 'WMDs Manager' || (this.store.role.permissions && this.store.role.permissions.includes('WMDs Manager')));
                    if (!isManager) {
                        this.$toast.add({ severity: 'success', summary: 'Despacho exitoso', detail: 'Productos despachados correctamente.', life: 3000 });
                    }
                    this.fetchPendingFullItems();
                }
            } catch (e) {
                this.$toast.add({ severity: 'error', summary: 'Error en despacho masivo', detail: 'Detalle técnico: ' + (e.message || 'Error desconocido'), life: 4000 });
            }
        },

        // Pull to refresh handlers
        handleTouchStart(e) {
            const logCol = this.$el.querySelector('.log-col');
            if (logCol && logCol.scrollTop === 0) {
                this.startY = e.touches[0].pageY;
                this.pulling = true;
            }
        },
        handleTouchMove(e) {
            if (!this.pulling || this.refreshing) return;
            const currentY = e.touches[0].pageY;
            const diff = currentY - this.startY;
            if (diff > 0) {
                this.pullDistance = Math.min(diff, this.maxPullDistance);
                if (diff > 10) e.preventDefault(); 
            }
        },
        async handleTouchEnd() {
            if (!this.pulling) return;
            if (this.pullDistance >= 60) {
                this.refreshing = true;
                await this.refreshData();
                this.refreshing = false;
            }
            this.pulling = false;
            this.pullDistance = 0;
        },

        // ═══════════════════════════════════════════
        // MODAL CANCELADOS
        // ═══════════════════════════════════════════

        openCancelledModal(cancelledItems, onFinishCallback) {
            this.cancelledModal.pending = cancelledItems;
            this.cancelledModal.confirmed = [];
            this.cancelledModal.inputValue = '';
            this.cancelledModal.lastError = '';
            this.cancelledModal.onFinish = onFinishCallback || null;
            this.cancelledModal.show = true;
        },

        async confirmCancelledScan(scanned) {
            if (!scanned) return;
            scanned = scanned.trim();
            if (!scanned) return;

            this.cancelledModal.lastError = '';

            try {
                // Consultar al backend para validar y obtener el nombre limpio del bulto/guía
                let response = await this.store.callOdoo("validate_attachment_guide", "", {
                    attachment_id: scanned,
                });

                if (response && response.valid) {
                    const resolvedName = response.name;

                    // Verificar que el código es uno de los pendientes no confirmados aún
                    const match = this.cancelledModal.pending.find(
                        p => p.name === resolvedName && !this.cancelledModal.confirmed.includes(p.name)
                    );
                    if (!match) {
                        if (this.cancelledModal.pending.some(p => p.name === resolvedName)) {
                            this.cancelledModal.lastError = `"${resolvedName}" ya fue removida.`;
                        } else {
                            this.cancelledModal.lastError = `"${resolvedName}" no corresponde a ninguna guía cancelada pendiente.`;
                        }
                        this.cancelledModal.inputValue = '';
                        return;
                    }

                    // Remover inmediatamente de la sesión y de la lista local
                    await this.removeFromSession(resolvedName, true); // true = cancelled_removal
                    const idx = this.so.findIndex(o => o.name === resolvedName);
                    if (idx !== -1) this.so.splice(idx, 1);

                    this.cancelledModal.confirmed.push(resolvedName);
                    this.cancelledModal.inputValue = '';
                    this.cancelledModal.lastError = '';

                    // Si ya se removieron todas, cerrar el modal automáticamente
                    if (this.cancelledModal.confirmed.length === this.cancelledModal.pending.length) {
                        setTimeout(async () => {
                            this.cancelledModal.show = false;
                            const cb = this.cancelledModal.onFinish;
                            this.cancelledModal.onFinish = null;
                            if (cb) await cb();
                        }, 800); // pequeña pausa para que el operador vea el feedback verde
                        return;
                    }
                } else {
                    this.cancelledModal.lastError = `Guía inválida o no encontrada: "${scanned}".`;
                    this.cancelledModal.inputValue = '';
                }
            } catch (e) {
                this.cancelledModal.lastError = "Error al validar la guía.";
                this.cancelledModal.inputValue = '';
            }
        }
    }
}
</script>

<style scoped>
.test-flow-container {
    display: flex;
    flex-direction: column;
    gap: 1rem;
    height: calc(100vh - var(--o-we-toolbar-height, 46px));
    padding: 10px;
    box-sizing: border-box;
    overflow-y: auto;
    position: relative;
    overscroll-behavior-y: contain;
    background: #fff;
}

.pull-to-refresh-indicator {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    overflow: hidden;
    background: rgba(59, 130, 246, 0.1);
    color: #3B82F6;
    z-index: 1000;
    transition: height 0.1s ease;
    font-size: 0.8rem;
    font-weight: bold;
    gap: 5px;
}

.pull-to-refresh-indicator i {
    font-size: 1.2rem;
}

.individual-mode {
    display: flex;
    flex-direction: column;
    gap: 1rem;
}

.scanner-col {
    flex: 0 0 auto;
    display: flex;
    gap: 10px;
}

.scanner-wrapper {
    flex: 1;
    position: relative;
}

.loading-session {
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    background: #2c3e50;
    border-radius: 8px;
    color: #ecf0f1;
    gap: 10px;
}

.loading-icon {
    font-size: 2rem;
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
    overflow-y: auto;
    min-height: 50vh;
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
    width: 100%;
    justify-content: space-between;
}

.log-title {
    font-weight: bold;
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
    color: #000000;
    font-size: 1rem;
    margin-bottom: 10px;
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

/* ── Session Banner ── */
.session-banner {
    background: #2980b9;
    color: white;
    padding: 8px 15px;
    border-radius: 6px;
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 0.85rem;
    animation: slideDown 0.3s ease;
}

.session-banner-close {
    margin-left: auto;
    color: white !important;
}

@keyframes slideDown {
    from { transform: translateY(-10px); opacity: 0; }
    to { transform: translateY(0); opacity: 1; }
}

/* ── Summary Cards ── */
.scan-summary-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
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

.summary-carrier {
    font-size: 0.7rem;
    color: #95a5a6;
    margin-top: 2px;
}

.summary-carrier i {
    font-size: 0.65rem;
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

/* ── Log List ── */
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

.log-item-info {
    display: flex;
    flex-direction: column;
    gap: 2px;
}

.log-item-product {
    color: #95a5a6;
    padding-left: 26px;
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

/* ═══════════════════════════════════════════
   HOJA DE SALIDA — VISTA DE IMPRESIÓN
   ═══════════════════════════════════════════ */

.print-overlay {
    display: flex;
    flex-direction: column;
    height: 100%;
    overflow-y: auto;
}

.print-actions {
    display: flex;
    gap: 15px;
    justify-content: center;
    padding: 15px;
    background: #ecf0f1;
    border-radius: 8px;
    margin-bottom: 15px;
    flex-shrink: 0;
}

.print-sheet {
    background: white;
    color: #2c3e50;
    padding: 30px;
    border-radius: 4px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 11pt;
    max-width: 210mm;
    margin: 0 auto;
}

.sheet-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 15px;
}

.sheet-logo h1 {
    margin: 0;
    font-size: 20pt;
    color: #2c3e50;
}

.sheet-subtitle {
    font-size: 9pt;
    color: #7f8c8d;
}

.sheet-meta {
    text-align: right;
    font-size: 9pt;
    line-height: 1.6;
    color: #34495e;
}

.sheet-divider {
    border-bottom: 2px solid #2c3e50;
    margin-bottom: 20px;
}

.sheet-section {
    margin-bottom: 20px;
}

.sheet-section h3 {
    font-size: 12pt;
    color: #2c3e50;
    border-bottom: 1px solid #bdc3c7;
    padding-bottom: 5px;
    margin-bottom: 10px;
}

.sheet-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 9pt;
}

.sheet-table th {
    background: #2c3e50;
    color: white;
    padding: 6px 8px;
    text-align: left;
    font-weight: 600;
}

.sheet-table td {
    padding: 5px 8px;
    border-bottom: 1px solid #ddd;
}

.sheet-table tr:nth-child(even) {
    background: #f8f9fa;
}

.product-cell {
    max-width: 200px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.status-complete {
    color: #27ae60;
    font-weight: bold;
}

.status-partial {
    color: #e67e22;
    font-weight: bold;
}

.sheet-signatures {
    display: flex;
    justify-content: space-around;
    margin-top: 50px;
    padding-top: 20px;
}

.signature-box {
    text-align: center;
    width: 40%;
}

.signature-line {
    border-bottom: 1px solid #2c3e50;
    margin-bottom: 8px;
    height: 50px;
}

.signature-box span {
    font-size: 9pt;
    color: #7f8c8d;
}

/* ═══════════════════════════════════════════
   @MEDIA PRINT — Solo la hoja de salida
   ═══════════════════════════════════════════ */

@media print {
    body * {
        visibility: hidden !important;
    }
    
    .print-sheet,
    .print-sheet * {
        visibility: visible !important;
    }

    .print-sheet {
        position: absolute;
        left: 0;
        top: 0;
        width: 210mm;
        padding: 15mm;
        box-shadow: none;
        border-radius: 0;
        font-size: 10pt;
    }

    .no-print {
        display: none !important;
    }

    .sheet-table th {
        background: #2c3e50 !important;
        color: white !important;
        -webkit-print-color-adjust: exact;
        print-color-adjust: exact;
    }

    .sheet-table tr:nth-child(even) {
        background: #f0f0f0 !important;
        -webkit-print-color-adjust: exact;
        print-color-adjust: exact;
    }

    .status-complete {
        color: #27ae60 !important;
        -webkit-print-color-adjust: exact;
        print-color-adjust: exact;
    }

    .status-partial {
        color: #e67e22 !important;
        -webkit-print-color-adjust: exact;
        print-color-adjust: exact;
    }

    .sheet-signatures {
        page-break-inside: avoid;
    }

    @page {
        size: A4;
        margin: 10mm;
    }
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

.cancelled-banner {
    background-color: #e74c3c;
    color: white;
    padding: 10px 15px;
    border-radius: 6px;
    margin-bottom: 15px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 0.9rem;
    line-height: 1.4;
    border-left: 5px solid #c0392b;
}

.log-item-cancelled {
    background-color: #fadbd8 !important;
    border-left: 4px solid #e74c3c !important;
    color: #78281f !important;
}

.badge-cancelled {
    background-color: #e74c3c;
    color: white;
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 0.7rem;
    font-weight: bold;
    margin-left: 8px;
    display: inline-block;
    vertical-align: middle;
}

/* ═══════════════════════════════════════════
   MODAL CANCELADOS
   ═══════════════════════════════════════════ */

.cancelled-modal-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.75);
    z-index: 9999;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 1rem;
    backdrop-filter: blur(4px);
}

.cancelled-modal {
    background: #1a1a2e;
    border-radius: 16px;
    padding: 2rem;
    width: 100%;
    max-width: 520px;
    max-height: 90vh;
    overflow-y: auto;
    box-shadow: 0 20px 60px rgba(0,0,0,0.6), 0 0 0 1px rgba(231,76,60,0.3);
    display: flex;
    flex-direction: column;
    gap: 1.25rem;
    animation: modalIn 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
}

@keyframes modalIn {
    from { opacity: 0; transform: scale(0.85) translateY(20px); }
    to   { opacity: 1; transform: scale(1) translateY(0); }
}

.cancelled-modal-header {
    display: flex;
    align-items: flex-start;
    gap: 1rem;
}

.cancelled-modal-icon {
    font-size: 2.5rem;
    color: #e74c3c;
    animation: pulse 1.5s infinite;
    flex-shrink: 0;
    margin-top: 4px;
}

@keyframes pulse {
    0%, 100% { opacity: 1; }
    50%       { opacity: 0.5; }
}

.cancelled-modal-title {
    margin: 0 0 4px;
    color: #e74c3c;
    font-size: 1.2rem;
    font-weight: 700;
}

.cancelled-modal-subtitle {
    margin: 0;
    color: #bdc3c7;
    font-size: 0.9rem;
    line-height: 1.4;
}

.cancelled-modal-list {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    max-height: 220px;
    overflow-y: auto;
}

.cancelled-modal-item {
    background: #2c2c54;
    border: 1px solid #e74c3c;
    border-radius: 8px;
    padding: 0.6rem 1rem;
    display: flex;
    align-items: center;
    gap: 0.75rem;
    transition: all 0.3s ease;
}

.cancelled-modal-item.item-confirmed {
    background: #1a3a2a;
    border-color: #2ecc71;
    opacity: 0.8;
}

.cancelled-modal-item .fa-times-circle {
    color: #e74c3c;
    font-size: 1.2rem;
    flex-shrink: 0;
}

.cancelled-modal-item .fa-check-circle {
    color: #2ecc71;
    font-size: 1.2rem;
    flex-shrink: 0;
}

.cancelled-modal-item-info {
    display: flex;
    flex-direction: column;
    flex: 1;
}

.item-ei {
    font-family: monospace;
    font-size: 0.95rem;
    font-weight: bold;
    color: #ecf0f1;
}

.item-so {
    font-size: 0.78rem;
    color: #95a5a6;
}

.item-badge-pending {
    font-size: 0.7rem;
    background: #e74c3c;
    color: white;
    padding: 2px 8px;
    border-radius: 20px;
    font-weight: 600;
    white-space: nowrap;
}

.item-badge-ok {
    font-size: 0.7rem;
    background: #2ecc71;
    color: #1a3a2a;
    padding: 2px 8px;
    border-radius: 20px;
    font-weight: 600;
    white-space: nowrap;
}

.cancelled-modal-progress {
    display: flex;
    flex-direction: column;
    gap: 6px;
}

.progress-label {
    font-size: 0.85rem;
    color: #bdc3c7;
    text-align: right;
}

.progress-track {
    height: 8px;
    background: #2c3e50;
    border-radius: 4px;
    overflow: hidden;
}

.progress-track-fill {
    height: 100%;
    background: linear-gradient(90deg, #e74c3c, #f39c12, #2ecc71);
    border-radius: 4px;
    transition: width 0.4s ease;
}

.cancelled-modal-scanner {
    display: flex;
    flex-direction: column;
    gap: 0.6rem;
    background: #16213e;
    border-radius: 10px;
    padding: 1rem;
    border: 1px solid #34495e;
}

.scanner-label {
    font-size: 0.85rem;
    color: #bdc3c7;
    display: flex;
    align-items: center;
    gap: 6px;
}

.scanner-input-row {
    display: flex;
    gap: 8px;
    align-items: center;
}

.cancelled-scan-input {
    flex: 1;
    background: #0f3460;
    border: 2px solid #3498db;
    border-radius: 8px;
    color: #ecf0f1;
    padding: 0.6rem 1rem;
    font-size: 1rem;
    font-family: monospace;
    outline: none;
    transition: border-color 0.2s;
}

.cancelled-scan-input:focus {
    border-color: #f39c12;
    box-shadow: 0 0 0 3px rgba(243,156,18,0.2);
}

.cancelled-scan-input:disabled {
    opacity: 0.4;
    cursor: not-allowed;
}

.scanner-error {
    color: #e74c3c;
    font-size: 0.82rem;
    display: flex;
    align-items: center;
    gap: 6px;
    animation: shake 0.3s ease;
}

@keyframes shake {
    0%, 100% { transform: translateX(0); }
    25%       { transform: translateX(-6px); }
    75%       { transform: translateX(6px); }
}

.cancelled-modal-footer {
    display: flex;
    justify-content: center;
    animation: fadeIn 0.4s ease;
}

@keyframes fadeIn {
    from { opacity: 0; transform: translateY(8px); }
    to   { opacity: 1; transform: translateY(0); }
}
</style>