<template>
    <div class="test-flow-container">

        <!-- ═══════════ MODO INDIVIDUAL (ESCANEO) ═══════════ -->
        <div v-if="dispatchMode === 'individual' && !showPrintView" class="individual-mode">
            
            <!-- Session recovery banner -->
            <div v-if="sessionRecovered" class="session-banner">
                <i class="fa fa-info-circle"></i>
                Sesión recuperada — {{ so.length }} escaneo(s) previo(s) restaurados.
                <Button icon="fa fa-times" class="p-button-text p-button-sm session-banner-close" @click="sessionRecovered = false" />
            </div>

            <div class="scanner-col">
                <div v-if="ready && !loadingSession" class="scanner-wrapper">
                    <BarcodeScannerComponent 
                        :key="scannerKey"
                        instructions="Escanea la guía para despacho"
                        :onScan="(data) => searchAndValidateSO(data)"
                    />
                </div>
                <div v-else-if="loadingSession" class="scanner-wrapper loading-session">
                    <i class="fa fa-spin fa-spinner loading-icon"></i>
                    <span>Recuperando sesión...</span>
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

                <!-- Visualization of n/total -->
                <div class="scan-summary-grid" v-if="scanSummary.length > 0">
                    <div v-for="item in scanSummary" :key="item.so_name" class="summary-card">
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

                <div class="log-list">
                    <div v-for="(order, index) in so" :key="index" class="log-item">
                        <div class="log-item-info">
                            <div>
                                <i class="fa fa-barcode barcode-icon"></i>
                                {{ order.name }}
                                <small class="text-info ml-2">({{ order.current }}/{{ order.total }})</small>
                            </div>
                            <div v-if="order.product_name" class="log-item-product">
                                <small>{{ order.product_name }}</small>
                            </div>
                        </div>
                        <Button icon="fa fa-times" class="p-button-rounded p-button-danger p-button-text" @click="removeOrder(index)" />
                    </div>
                    
                    <div v-if="so.length === 0" class="empty-log">
                        <i class="fa fa-archive search-icon"></i>
                        Esperando escaneo de etiqueta EI (SOXXXX/N)...
                    </div>
                </div>
            </div>
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

    </div>
</template>

<script>
import BarcodeScannerComponent from '../QRScannerComponent/BarcodeScannerComponent.vue';
import Button from 'primevue/button';
import { useGeneralStore } from "../../store/index";

export default {
    name: "DispatchComponent",
    components: {
        BarcodeScannerComponent,
        Button
    },
    data() {
        return {
            store: useGeneralStore(),
            so: [], // Array of objects: { name, so_name, total, current, dispatched_count, product_name, carrier_name, scan_datetime, line_id }
            ready: false,
            scannerKey: 0,
            dispatchMode: 'individual',
            pendingFullItems: [],
            // ── Sesión persistente ──
            sessionId: null,
            loadingSession: true,
            sessionRecovered: false,
            // ── Impresión ──
            showPrintView: false,
            printData: {
                session_id: null,
                operator_name: '',
                date_start: '',
                date_end_formatted: '',
                lines: [],
                so_summary: [],
                total_lines: 0
            },
            dispatching: false,
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
        }
    },
    async mounted() {
        console.log("Action: DispatchComponent mounted");
        localStorage.removeItem("mandatory_uncompleted");

        // ── Intentar recuperar sesión activa ──
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
                    
                    // Restaurar el array so[] desde las líneas guardadas
                    this.so = response.lines.map(line => ({
                        name: line.ei_name,
                        so_name: line.so_name,
                        total: line.total_ei,
                        current: line.sequence_number,
                        dispatched_count: line.dispatched_count,
                        product_name: line.product_name,
                        carrier_name: line.carrier_name,
                        scan_datetime: line.scan_datetime,
                        line_id: line.line_id,
                    }));

                    this.sessionRecovered = true;
                    console.log(`Action: Sesión ${this.sessionId} recuperada con ${this.so.length} líneas`);
                    
                    if (this.$toast) {
                        this.$toast.add({ 
                            severity: 'info', 
                            summary: 'Sesión Recuperada', 
                            detail: `Se restauraron ${this.so.length} escaneo(s) de tu sesión anterior.`, 
                            life: 4000 
                        });
                    }
                } else if (response && response.active) {
                    // Sesión activa pero sin líneas
                    this.sessionId = response.session_id;
                }
            } catch (e) {
                console.error("Error recuperando sesión:", e);
                // No bloquear la UI si falla la recuperación
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
                });

                if (response && response.ok) {
                    this.sessionId = response.session_id;
                    // Actualizar el item en el array con la info del backend
                    const idx = this.so.findIndex(o => o.name === orderData.name);
                    if (idx !== -1) {
                        this.so[idx].line_id = response.line_id;
                        this.so[idx].product_name = response.product_name || '';
                        this.so[idx].carrier_name = response.carrier_name || '';
                    }
                    console.log(`Action: Línea ${orderData.name} persistida en sesión ${this.sessionId}`);
                }
            } catch (e) {
                console.error("Error persistiendo escaneo:", e);
                // El escaneo ya está en memoria, no bloquear
            }
        },

        async removeFromSession(eiName) {
            try {
                await this.store.callOdoo("remove_dispatch_session_line", "", {
                    operator_login: this.store.role.email,
                    ei_name: eiName,
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

        // ═══════════════════════════════════════════
        // ESCANEO — Lógica existente + persistencia
        // ═══════════════════════════════════════════

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
            console.log("Action: searchAndValidateSO triggered with data:", data);
            try {
                if (this.so.some(o => o.name === data)) {
                    console.log("Action: Duplicate guide detected, restarting scanner");
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

                console.log("Action: Calling Odoo validate_attachment_guide");
                let response = await this.store.callOdoo("validate_attachment_guide", "", {
                    attachment_id: data,
                });

                if (response.valid) {
                    if (response.so_state === 'cancel') {
                        console.log("Action: Order is cancelled");
                        if(this.$toast) {
                            this.$toast.add({ 
                                severity: 'error', 
                                summary: 'Pedido Cancelado', 
                                detail: `El pedido ${response.so} está cancelado y no puede ser despachado.`, 
                                life: 5000 
                            });
                        }
                    } else if (response.state && response.state.dispatched) {
                        console.log("Action: Guide already dispatched");
                        if(this.$toast) {
                            this.$toast.add({ 
                                severity: 'error', 
                                summary: 'Guía ya Despachada', 
                                detail: `La guía ${data} ya ha sido procesada anteriormente.`, 
                                life: 4000 
                            });
                        }
                    } else if (response.state && !response.state.on_dock) {
                        console.log("Action: Guide not on dock");
                        if(this.$toast) {
                            this.$toast.add({ 
                                severity: 'error', 
                                summary: 'Ubicación Incorrecta', 
                                detail: `La guía ${data} no se encuentra en un DOCK y no puede ser despachada.`, 
                                life: 4000 
                            });
                        }
                    } else {
                        console.log("Action: Validation successful, pushing to array");
                        const newItem = {
                            name: response.name,
                            so_name: response.so,
                            total: response.total,
                            current: response.current,
                            dispatched_count: response.dispatched_count || 0,
                            product_name: '',
                            carrier_name: '',
                            scan_datetime: new Date().toISOString(),
                            line_id: null,
                        };
                        this.so.push(newItem);

                        // ── Persistir en backend ──
                        await this.persistScanToSession(newItem);
                    }
                } else {
                    console.log("Action: Validation failed");
                    if(this.$toast) {
                        this.$toast.add({ 
                            severity: 'error', 
                            summary: 'Guía Inválida', 
                            detail: 'El código escaneado no corresponde a una guía válida para despacho o el formato es incorrecto.', 
                            life: 4000 
                        });
                    }
                }
                
                this.restartScanner();
            } catch (e) {
                console.log("Action: Error in searchAndValidateSO", e);
                this.restartScanner();
            }
        },

        restartScanner() {
            console.log("Action: restartScanner triggered");
            this.scannerKey++;
        },

        // ═══════════════════════════════════════════
        // DESPACHO — Entregar + completar sesión
        // ═══════════════════════════════════════════

        async dispatchToCarrier() {
            console.log("Action: dispatchToCarrier triggered");
            if (this.so.length === 0) {
                console.log("Action: No guides to dispatch, returning");
                return;
            }
            
            this.dispatching = true;

            try {
                const picks_ids = this.so.map(o => o.name);
                console.log("Action: Calling Odoo dispatch_orders with picks_ids:", picks_ids);
                let response = await this.store.callOdoo("dispatch_orders", "", {
                    operator_login: this.store.role.email,
                    picks_ids: picks_ids 
                });

                if (response.status === "success") {
                    console.log("Action: Dispatch successful");

                    if (response.warning) {
                        this.$toast.add({ 
                            severity: 'warn', 
                            summary: 'Entrega Parcial', 
                            detail: 'Se procesaron las guías, pero hay advertencias: ' + response.warning, 
                            life: 6000 
                        });
                    } else {
                        const isManager = this.store.role && (this.store.role.role === 'WMDs Manager' || (this.store.role.permissions && this.store.role.permissions.includes('WMDs Manager')));
                        if (!isManager) {
                            this.$toast.add({ 
                                severity: 'success', 
                                summary: 'Despacho Completado', 
                                detail: 'Todas las órdenes han sido entregadas. Generando hoja de salida...', 
                                life: 4000 
                            });
                        }
                    }

                    // ── Completar sesión y mostrar vista de impresión ──
                    const sessionCompleted = await this.completeSession();
                    
                    if (sessionCompleted) {
                        this.showPrintView = true;
                    } else {
                        // Si falló completar sesión, generar printData desde la data local
                        this.generatePrintDataFromLocal();
                        this.showPrintView = true;
                    }

                    this.restartScanner(); 
                } else {
                    console.log("Action: Dispatch returned non-success status", response);
                    throw new Error(response.message || "Error desconocido");
                }
            } catch (e) {
                console.log("Action: Error in dispatchToCarrier", e);
                if(this.$toast) {
                    this.$toast.add({ 
                        severity: 'error', 
                        summary: 'Error de Entrega', 
                        detail: 'No se pudo completar la entrega a paquetería. Detalle técnico: ' + (e.message || 'Error desconocido'), 
                        life: 5000 
                    });
                }
            } finally {
                this.dispatching = false;
            }
        },

        generatePrintDataFromLocal() {
            // Fallback: generar datos de impresión desde la data local cuando el backend falla
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

        printSheet() {
            window.print();
        },

        finishAndExit() {
            this.showPrintView = false;
            this.so = [];
            this.sessionId = null;
            this.printData = { session_id: null, operator_name: '', date_start: '', date_end_formatted: '', lines: [], so_summary: [], total_lines: 0 };
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
       
        exitFlow() {
            console.log("Action: exitFlow triggered");
            if (this.so.length > 0 || (this.dispatchMode === 'full' && this.pendingFullItems.some(i => i.dispatchQty < i.qty))) {
                const action = confirm(
                    "Tienes escaneos en esta sesión.\n\n" +
                    "• Aceptar = Salir SIN cancelar la sesión (podrás retomarla después)\n" +
                    "• Cancelar = Volver al escaneo"
                );
                if (!action) {
                    console.log("Action: exitFlow cancelled by user");
                    return;
                }

                // La sesión queda ACTIVA en el backend para poder recuperarla
                console.log("Action: Saliendo sin cancelar sesión — se puede retomar");
            }
            console.log("Action: Finalizing flow");
            this.so = [];
            this.store.mandatory_uncompleted.doneMandatory();
        },

        async clearAllOrders() {
            console.log("Action: clearAllOrders triggered");
            if (!confirm("¿Estás seguro de limpiar todos los escaneos?\nEsto también cancelará la sesión actual.")) {
                return;
            }
            // ── Limpiar en backend ──
            await this.clearSession();
            this.so = [];
        },

        async removeOrder(index) {
            console.log("Action: removeOrder triggered for index:", index);
            const eiName = this.so[index].name;
            this.so.splice(index, 1);
            // ── Eliminar del backend ──
            await this.removeFromSession(eiName);
        },

        // ═══════════════════════════════════════════
        // DESPACHO FULL (sin cambios relevantes)
        // ═══════════════════════════════════════════

        async dispatchFullItem(item) {
            if (item.dispatchQty <= 0) return;
            if (item.dispatchQty > item.qty) {
                item.dispatchQty = item.qty;
                this.$toast.add({ severity: 'warn', summary: 'Cantidad Ajustada', detail: 'Se ha ajustado automáticamente al máximo disponible.', life: 3000 });
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
                this.$toast.add({ severity: 'error', summary: 'Error de Despacho', detail: 'Detalle técnico: ' + (e.message || 'Error desconocido'), life: 4000 });
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
                this.$toast.add({ severity: 'warn', summary: 'Ajuste de Cantidades', detail: 'Algunas cantidades fueron ajustadas.', life: 3000 });
            }
            try {
                const response = await this.store.callOdoo("dispatch_full_items", "", {
                    operator_login: this.store.role.email,
                    items: itemsToDispatch
                });
                if (response.status === "success") {
                    const isManager = this.store.role && (this.store.role.role === 'WMDs Manager' || (this.store.role.permissions && this.store.role.permissions.includes('WMDs Manager')));
                    if (!isManager) {
                        this.$toast.add({ severity: 'success', summary: 'Despacho Exitoso', detail: 'Productos despachados correctamente.', life: 3000 });
                    }
                    this.fetchPendingFullItems();
                }
            } catch (e) {
                this.$toast.add({ severity: 'error', summary: 'Error en Despacho Masivo', detail: 'Detalle técnico: ' + (e.message || 'Error desconocido'), life: 4000 });
            }
        },
    }
}
</script>

<style scoped>
.test-flow-container {
    display: flex;
    flex-direction: column;
    gap: 1rem;
    min-height: 100%;
    padding: 10px;
    box-sizing: border-box;
    overflow-y: auto;
}

.individual-mode {
    display: flex;
    flex-direction: column;
    gap: 1rem;
    height: calc(100% - 50px);
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
    height: 10%;
    display: flex;
    flex-direction: column;
    gap: 10px;
    justify-content: center;
    align-items: center;
}

.log-col {
    height: 60%;
    display: flex;
    flex-direction: column;
    background: #2c3e50;
    border-radius: 8px;
    padding: 15px;
    color: #ecf0f1;
    overflow: hidden;
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
    flex: 1;
    overflow-y: auto;
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
    /* Ocultar todo excepto la hoja */
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
</style>