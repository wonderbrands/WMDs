<template>
    <div class="test-flow-container">
        <div class="individual-mode">
            <!-- Info Panel Descriptivo -->
            <div class="info-panel">
                <span class="font-bold text-lg text-blue-300 block mb-2">
                    <i class="fa fa-info-circle"></i> Despacho Fulfillment y Mayoreo
                </span>
                <p>
                    Este componente permite registrar la entrega a paquetería de dos tipos de flujos de salida:
                </p>
                <ul>
                    <li><strong>Flujo Fulfillment (B2C):</strong> Escanea la etiqueta de traslado <code>WH/DFUL/XXXXX</code> para abrir la confirmación de la operación y validar el despacho de artículos individuales.</li>
                    <li><strong>Flujo de Mayoreo (Wholesale):</strong> Escanea el código de barras del pedido <code>SOXXXXXXXX</code> para validar directamente la salida total (OUT), quitar el pedido del dock y opcionalmente imprimir su hoja de confirmación.</li>
                </ul>
            </div>

            <div class="scanner-col">
                <div v-if="ready" class="scanner-wrapper">
                    <BarcodeScannerComponent 
                        :key="scannerKey"
                        instructions="Escanea la operación WH/DFUL/xxxxx o pedido SOXXXX para despacho"
                        :onScan="(data) => handleScan(data)"
                    />
                </div>
            </div>

            <div class="buttons-col">
                <Button 
                    @click="exitFlow"
                    class="p-button-text p-button-danger p-button-sm" 
                    label="Salir / Finalizar" 
                    icon="fa fa-times"
                />
            </div>

            <div class="log-col">
                <div class="log-header">
                    <span class="log-title">Despacho Fulfillment / Mayoreo</span>
                </div>
                
                <div class="log-list">
                    <div v-if="scans.length > 0" class="scanned-list w-full">
                        <div v-for="scan in scans" :key="scan.time" class="scan-item">
                            <div class="scan-item-header">
                                <span class="scan-name"><i class="fa fa-check-circle text-success"></i> {{ scan.name }}</span>
                                <span class="scan-time">{{ scan.time }}</span>
                            </div>
                            <div class="scan-msg">{{ scan.message }}</div>
                        </div>
                    </div>
                    <div v-else-if="loading" class="empty-log">
                        <i class="fa fa-spin fa-spinner search-icon"></i>
                        Validando operación...
                    </div>
                    <div v-else class="empty-log">
                        <i class="fa fa-barcode search-icon"></i>
                        Esperando escaneo de operación WH/DFUL o pedido SO de Mayoreo...
                    </div>
                </div>
            </div>
        </div>

        <!-- DIALOG 1: Confirm Dispatch of Wholesale SO -->
        <Dialog 
            v-model:visible="showConfirmDialog" 
            modal 
            header="Confirmar Despacho" 
            :style="{ width: '350px' }" 
            :closable="false"
        >
            <div class="p-3 text-center">
                <i class="fa fa-question-circle text-primary text-5xl mb-3"></i>
                <p class="font-bold text-lg mb-2">¿Confirmar despacho de Pedido?</p>
                <p class="text-sm text-secondary">Se validará y cerrará el traslado de salida (OUT) para el pedido <strong>{{ scannedWholesaleSO?.name }}</strong>.</p>
            </div>
            <template #footer>
                <div class="flex justify-content-between w-full gap-2">
                    <Button label="Cancelar" class="p-button-text p-button-secondary flex-1" @click="cancelWholesaleDispatch" />
                    <Button label="Confirmar" class="p-button-success flex-1" @click="confirmWholesaleDispatch" :loading="loading" />
                </div>
            </template>
        </Dialog>

        <!-- DIALOG 2: Ask to print confirmation sheet -->
        <Dialog 
            v-model:visible="showPrintDialog" 
            modal 
            header="Imprimir Confirmación" 
            :style="{ width: '350px' }" 
            :closable="false"
        >
            <div class="p-3 text-center">
                <i class="fa fa-print text-success text-5xl mb-3"></i>
                <p class="font-bold text-lg mb-2">¡Pedido Despachado!</p>
                <p class="text-sm text-secondary">¿Deseas imprimir la Hoja de Salida (Confirmación) para el pedido <strong>{{ scannedWholesaleSO?.name }}</strong>?</p>
            </div>
            <template #footer>
                <div class="flex justify-content-between w-full gap-2">
                    <Button label="No, Finalizar" class="p-button-text p-button-secondary flex-1" @click="closePrintDialog" />
                    <Button label="Sí, Imprimir" class="p-button-success flex-1" @click="printWholesaleConfirmSheet" :loading="loading" />
                </div>
            </template>
        </Dialog>
    </div>
</template>

<script>
import BarcodeScannerComponent from '../QRScannerComponent/BarcodeScannerComponent.vue';
import Button from 'primevue/button';
import Dialog from 'primevue/dialog';
import { useGeneralStore } from "../../store/index";

export default {
    name: "DispatchComponentFul",
    components: {
        BarcodeScannerComponent,
        Button,
        Dialog
    },
    data() {
        return {
            store: useGeneralStore(),
            ready: false,
            scannerKey: 0,
            loading: false,
            scans: [],
            showConfirmDialog: false,
            showPrintDialog: false,
            scannedWholesaleSO: null
        }
    },
    mounted() {
        console.log("DispatchComponentFul: mounted");
        setTimeout(() => {
            this.ready = true;
        }, 500);
    },
    methods: {
        async handleScan(data) {
            console.log("DispatchComponentFul: Scanned", data);
            if (this.loading) return;
            this.loading = true;
            const toast = this.$toast || this.store.toast;
            
            try {
                // Validate if it's a WH/DFUL picking and in correct state (or a wholesale SO)
                const validation = await this.store.callOdoo("validate_dfull_pick", "", {
                    pick_name: data
                });

                if (validation && validation.valid) {
                    if (validation.is_wholesale_so) {
                        if (validation.need_confirmation) {
                            this.scannedWholesaleSO = {
                                name: data,
                                id: validation.so_id
                            };
                            this.showConfirmDialog = true;
                            return;
                        }
                        
                        console.log("DispatchComponentFul: Wholesale SO dispatched successfully");
                        if (toast) {
                            toast.add({
                                severity: 'success',
                                summary: 'Despachado',
                                detail: validation.message,
                                life: 4000
                            });
                        }
                        this.scans.unshift({
                            name: data,
                            time: new Date().toLocaleTimeString(),
                            message: validation.message
                        });
                        this.restartScanner();
                    } else {
                        console.log("DispatchComponentFul: Validated successfully, getting URL");
                        // Get the barcode URL and redirect
                        const url = await this.store.callOdoo("get_barcode_url", "", { 
                            pick_name: data 
                        });
                        
                        if (url) {
                            console.log("DispatchComponentFul: Redirecting to", url);
                            window.location.href = url;
                        } else {
                            console.error("DispatchComponentFul: No URL returned");
                            if (toast) {
                                toast.add({ 
                                    severity: 'error', 
                                    summary: 'Error de Redirección', 
                                    detail: 'No se pudo obtener la dirección de la operación. Sin URL de retorno.', 
                                    life: 4000 
                                });
                            }
                            this.restartScanner();
                        }
                    }
                } else {
                    console.warn("DispatchComponentFul: Validation failed", validation.message);
                    if (toast) {
                        toast.add({ 
                            severity: 'error', 
                            summary: 'Operación Inválida', 
                            detail: 'La operación no es válida. ' + (validation.message || 'Estado incorrecto o tipo de pick inválido'), 
                            life: 5000 
                        });
                    }
                    this.restartScanner();
                }
            } catch (e) {
                console.error("DispatchComponentFul: Error in handleScan", e);
                if (toast) {
                    toast.add({ 
                        severity: 'error', 
                        summary: 'Error en Escaneo', 
                        detail: 'Ocurrió un error al procesar el código escaneado. ' + (e.message || 'Error de conexión'), 
                        life: 4000 
                    });
                }
                this.restartScanner();
            } finally {
                this.loading = false;
            }
        },
        async confirmWholesaleDispatch() {
            if (!this.scannedWholesaleSO) return;
            this.loading = true;
            const toast = this.$toast || this.store.toast;
            try {
                const res = await this.store.callOdoo("validate_dfull_pick", "", {
                    pick_name: this.scannedWholesaleSO.name,
                    confirm_dispatch: true
                });

                if (res && res.valid) {
                    this.showConfirmDialog = false;
                    if (toast) {
                        toast.add({
                            severity: 'success',
                            summary: 'Despachado',
                            detail: res.message,
                            life: 4000
                        });
                    }
                    this.scans.unshift({
                        name: this.scannedWholesaleSO.name,
                        time: new Date().toLocaleTimeString(),
                        message: res.message
                    });
                    
                    // Proceed to ask if they want to print the confirmation sheet
                    this.showPrintDialog = true;
                } else {
                    this.showConfirmDialog = false;
                    if (toast) {
                        toast.add({
                            severity: 'error',
                            summary: 'Fallo al despachar',
                            detail: res.message || 'No se pudo completar el despacho.',
                            life: 5000
                        });
                    }
                    this.scannedWholesaleSO = null;
                    this.restartScanner();
                }
            } catch (e) {
                this.showConfirmDialog = false;
                console.error("Error confirming wholesale dispatch", e);
                if (toast) {
                    toast.add({
                        severity: 'error',
                        summary: 'Error de Red/Conexión',
                        detail: e.message || 'Error al conectar con el servidor',
                        life: 4000
                    });
                }
                this.scannedWholesaleSO = null;
                this.restartScanner();
            } finally {
                this.loading = false;
            }
        },
        cancelWholesaleDispatch() {
            this.showConfirmDialog = false;
            this.scannedWholesaleSO = null;
            this.restartScanner();
        },
        async printWholesaleConfirmSheet() {
            if (!this.scannedWholesaleSO) return;
            this.loading = true;
            this.showPrintDialog = false;
            const toast = this.$toast || this.store.toast;
            try {
                const e = await this.store.callOdoo("print_wholesale_dispatch_sheet", "", {
                    so_id: this.scannedWholesaleSO.id,
                    operator_login: this.store.role.email
                });
                if (e && e.ok && e.action) {
                    console.log("Acción nativa recibida para Hoja de Salida en Despacho Ful.");
                    let n = null;
                    if (window.odoo && window.odoo.__WOWL_DEBUG__ && window.odoo.__WOWL_DEBUG__.root && (n = window.odoo.__WOWL_DEBUG__.root.env.services.action), !n) {
                        const i = document.querySelector(".o_web_client");
                        if (i && i.__owl__) {
                            const r = i.__owl__;
                            r.app && r.app.env ? n = r.app.env.services.action : r.env && (n = r.env.services.action)
                        }
                    }
                    n && (await n.doAction(e.action));
                    const o = window.location.origin + `/report/pdf/wmds.report_dispatch_sheet_document/${e.session_id}`;
                    window.open(o, "_blank");
                    if (toast) {
                        toast.add({
                            severity: 'success',
                            summary: 'Hoja de Salida',
                            detail: 'Previsualización y orden de impresión enviadas.',
                            life: 3000
                        });
                    }
                } else {
                    if (toast) {
                        toast.add({
                            severity: 'error',
                            summary: 'Error al Imprimir',
                            detail: (e && e.error) || 'No se pudo generar la acción de impresión.',
                            life: 4000
                        });
                    }
                }
            } catch (err) {
                console.error("Error printing wholesale dispatch sheet from operator", err);
                if (toast) {
                    toast.add({
                        severity: 'error',
                        summary: 'Error',
                        detail: err.message || 'Error de conexión',
                        life: 4000
                    });
                }
            } finally {
                this.loading = false;
                this.scannedWholesaleSO = null;
                this.restartScanner();
            }
        },
        closePrintDialog() {
            this.showPrintDialog = false;
            this.scannedWholesaleSO = null;
            this.restartScanner();
        },
        restartScanner() {
            this.scannerKey++;
        },
        exitFlow() {
            console.log("DispatchComponentFul: Exiting flow");
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
    height: calc(100vh - var(--o-we-toolbar-height, 46px));
    padding: 10px;
    box-sizing: border-box;
    overflow-y: auto;
}

.individual-mode {
    display: flex;
    flex-direction: column;
    gap: 1rem;
    height: 100%;
    overflow: hidden;
}

.scanner-col {
    flex: 0 0 auto;
    display: flex;
    gap: 10px;
}

.scanner-wrapper {
    flex: 1;
    overflow: hidden;
    position: relative;
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

.log-title {
    font-weight: bold;
}

.log-list {
    background: #34495e;
    border-radius: 4px;
    padding: 10px;
    display: flex;
    align-items: flex-start;
    justify-content: flex-start;
}

.empty-log {
    text-align: center;
    color: #7f8c8d;
    width: 100%;
}

.scanned-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
    width: 100%;
}

.scan-item {
    background: #2c3e50;
    border-left: 4px solid #2ecc71;
    border-radius: 4px;
    padding: 8px 12px;
    font-size: 0.95rem;
}

.scan-item-header {
    display: flex;
    justify-content: space-between;
    font-weight: bold;
    margin-bottom: 4px;
}

.scan-name {
    color: #2ecc71;
}

.scan-time {
    font-size: 0.8rem;
    color: #bdc3c7;
}

.scan-msg {
    color: #ecf0f1;
}

.text-success {
    color: #2ecc71;
}

.search-icon {
    font-size: 2.5rem;
    display: block;
    margin-bottom: 10px;
}

.info-panel {
    background-color: #1e293b;
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 15px;
    margin-bottom: 15px;
    color: #f1f5f9;
}
.info-panel p {
    margin: 0 0 10px 0;
    font-size: 0.85rem;
    line-height: 1.4;
    color: #cbd5e1;
}
.info-panel ul {
    margin: 0;
    padding-left: 20px;
    font-size: 0.8rem;
    color: #cbd5e1;
}
.info-panel li {
    margin-bottom: 6px;
}
.info-panel code {
    background-color: #0f172a;
    color: #38bdf8;
    padding: 2px 5px;
    border-radius: 4px;
    font-family: monospace;
}
</style>