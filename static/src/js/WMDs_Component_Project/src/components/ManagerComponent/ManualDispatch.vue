<template>
    <div class="manual-dispatch-container">
        <div class="header">
            <h2>Gestión Manual de Salidas</h2>
            <Button icon="fa fa-refresh" severity="secondary" rounded text @click="refreshAll" :loading="loading" title="Actualizar todo" />
        </div>

        <!-- SECCIÓN DE BÚSQUEDA -->
        <div class="search-section">
            <div class="search-bar">
                <div class="p-inputgroup flex-1">
                    <InputText v-model="searchTerm" placeholder="Buscar por SO, EI o Tracking..." @keyup.enter="searchOrders" class="search-input-large" />
                    <Button icon="fa fa-search" @click="searchOrders" :loading="searching" label="Buscar Pedido" class="search-button-large" />
                </div>
            </div>

            <div v-if="searchResults.length > 0" class="search-results-container">
                <Accordion :value="['0']" multiple>
                    <AccordionPanel v-for="(order, index) in searchResults" :key="order.id" :value="index.toString()">
                        <AccordionHeader>
                            <div class="order-header-large">
                                <span class="order-name-tag"><i class="fa fa-shopping-cart"></i> {{ order.name }}</span>
                                <Tag v-if="order.is_wholesale" value="Mayoreo" severity="contrast" class="ml-2" />
                                <span class="order-info-tag"><i class="fa fa-truck"></i> {{ order.carrier }}</span>
                                <span class="order-info-tag tracking" v-if="order.tracking && order.tracking !== 'N/A'"><i class="fa fa-barcode"></i> {{ order.tracking }}</span>
                            </div>
                        </AccordionHeader>
                        <AccordionContent>
                             <div v-if="order.is_wholesale" class="wholesale-dispatch-banner p-3 mb-3 border-round bg-blue-50 border-blue-200 border-1 flex justify-content-between align-items-center w-full">
                                 <div>
                                     <h4 class="m-0 text-blue-900 font-bold" style="font-size: 1.15rem;"><i class="fa fa-info-circle"></i> Pedido de Mayoreo</h4>
                                     <p class="m-0 mt-1 text-sm text-blue-700">Este pedido se despacha a nivel de productos. Puedes despacharlo manualmente aquí o enviar el código de barras a la IoT Box para escanearlo.</p>
                                 </div>
                                 <div class="flex gap-2">
                                     <Button label="Imprimir Hoja de Salida (IoT)" icon="fa fa-print" severity="info" @click="printWholesaleDispatchSheet(order)" :loading="printingWholesaleSheet[order.id]" />
                                     <Button label="Despachar Pedido Completo" icon="fa fa-paper-plane" severity="success" @click="dispatchWholesaleOrder(order)" :loading="dispatchingWholesale[order.id]" />
                                 </div>
                             </div>

                             <div class="order-detail-container">
                                 <div class="detail-column" v-if="!order.is_wholesale">
                                    <div class="detail-header">
                                        <i class="fa fa-cubes"></i>
                                        <h4>Paquetes (EIs)</h4>
                                    </div>
                                    <DataTable :value="order.eis" class="p-datatable-sm custom-table" stripedRows>
                                        <Column field="name" header="Paquete"></Column>
                                        <Column field="status" header="Estado">
                                            <template #body="slotProps">
                                                <Tag :severity="getStatusSeverity(slotProps.data.status)" :value="slotProps.data.status" class="status-tag" />
                                            </template>
                                        </Column>
                                        <Column field="location" header="Ubicación"></Column>
                                        <Column header="Acciones">
                                            <template #body="slotProps">
                                                <Button 
                                                    v-if="slotProps.data.status !== 'Despachado'"
                                                    label="Despacho Manual" 
                                                    icon="fa fa-paper-plane" 
                                                    severity="success"
                                                    size="small"
                                                    @click="manualDispatchEI(slotProps.data, order)"
                                                    :loading="dispatching"
                                                    class="dispatch-btn"
                                                />
                                            </template>
                                        </Column>
                                    </DataTable>
                                 </div>

                                 <div class="detail-column">
                                    <div class="detail-header">
                                        <i class="fa fa-list"></i>
                                        <h4>Productos</h4>
                                    </div>
                                    <DataTable :value="order.products" class="p-datatable-sm custom-table" stripedRows>
                                        <Column field="name" header="Producto"></Column>
                                        <Column field="qty" header="Pedida" class="text-center"></Column>
                                        <Column field="qty_done" header="Hecha" class="text-center"></Column>
                                        <Column field="state" header="Estado"></Column>
                                    </DataTable>
                                 </div>
                             </div>
                        </AccordionContent>
                    </AccordionPanel>
                </Accordion>
            </div>
            <div v-else-if="searched && !searching" class="empty-results">
                <i class="fa fa-info-circle"></i> No se encontraron resultados para "{{ searchTerm }}"
            </div>
        </div>

        <div class="grid-container">
            <!-- SECCIÓN BINS -->
            <div class="section-card">
                <div class="section-header">
                    <i class="fa fa-archive"></i>
                    <h3>BINS con Productos</h3>
                </div>
                <div class="section-content">
                    <div v-if="activeBins.length === 0" class="empty-state">No hay Bins ocupados.</div>
                    <div v-for="bin in activeBins" :key="bin.id" class="item-row clickable" @click="selectBin(bin)">
                        <div class="item-info">
                            <span class="item-name">{{ bin.name }}</span>
                            <span class="item-detail">{{ bin.total_items }} paquetes | {{ bin.carrier_name }}</span>
                        </div>
                        <i class="fa fa-chevron-right"></i>
                    </div>
                </div>
            </div>

            <!-- SECCIÓN DOCKS -->
            <div class="section-card">
                <div class="section-header">
                    <i class="fa fa-truck"></i>
                    <h3>DOCKS con Productos</h3>
                </div>
                <div class="section-content">
                    <div v-if="activeDocks.length === 0" class="empty-state">No hay Docks con productos.</div>
                    <div v-for="dock in activeDocks" :key="dock.id" class="item-row clickable" @click="selectDock(dock)">
                        <div class="item-info">
                            <span class="item-name">{{ dock.name }}</span>
                            <span class="item-detail">{{ dock.total_items }} paquetes</span>
                        </div>
                        <i class="fa fa-chevron-right"></i>
                    </div>
                </div>
            </div>
        </div>

        <!-- DIALOG DETALLE BIN -->
        <Dialog v-model:visible="showBinDialog" :header="'Detalle de BIN: ' + (selectedBin?.name || '')" :style="{ width: '55vw' }" :breakpoints="{ '960px': '75vw', '640px': '95vw' }" modal>
            <div v-if="selectedBinContents" class="dialog-content">
                <DataTable 
                    v-model:selection="selectedBinPackages" 
                    :value="selectedBinContents.package_details" 
                    stripedRows 
                    class="p-datatable-sm"
                    dataKey="name"
                >
                    <Column selectionMode="multiple" headerStyle="width: 3rem"></Column>
                    <Column field="name" header="Referencia"></Column>
                    <Column field="so" header="Pedido/Origen"></Column>
                    <Column field="is_full" header="Tipo">
                        <template #body="slotProps">
                            <Tag :severity="slotProps.data.is_full ? 'warning' : 'info'" :value="slotProps.data.is_full ? 'Fulfillment' : 'Pedido'"></Tag>
                        </template>
                    </Column>
                </DataTable>
                <div class="dialog-actions">
                    <Select v-model="targetDockId" :options="availableDocks" optionLabel="name" optionValue="name" placeholder="Seleccionar DOCK destino" class="w-full" />
                    <Button 
                        :label="selectedBinPackages.length > 0 ? 'Mover seleccionados (' + selectedBinPackages.length + ')' : 'Mover todo el BIN'" 
                        icon="fa fa-exchange" 
                        @click="moveToDock" 
                        :disabled="!targetDockId" 
                        :loading="processing" 
                    />
                </div>
            </div>
        </Dialog>

        <!-- DIALOG DETALLE DOCK -->
        <Dialog v-model:visible="showDockDialog" :header="'Detalle de DOCK: ' + (selectedDock?.name || '')" :style="{ width: '55vw' }" :breakpoints="{ '960px': '75vw', '640px': '95vw' }" modal>
            <div v-if="selectedDockContents" class="dialog-content">
                <DataTable 
                    v-model:selection="selectedDockPackages" 
                    :value="selectedDockContents.package_details" 
                    stripedRows 
                    class="p-datatable-sm"
                    dataKey="name"
                >
                    <Column selectionMode="multiple" headerStyle="width: 3rem"></Column>
                    <Column field="name" header="Referencia"></Column>
                    <Column field="so" header="Pedido/Origen"></Column>
                    <Column field="is_full" header="Tipo">
                        <template #body="slotProps">
                            <Tag :severity="slotProps.data.is_full ? 'warning' : 'info'" :value="slotProps.data.is_full ? 'Fulfillment' : 'Pedido'"></Tag>
                        </template>
                    </Column>
                </DataTable>
                <div class="dialog-actions">
                    <Button 
                        :label="selectedDockPackages.length > 0 ? 'DESPACHAR SELECCIONADOS (' + selectedDockPackages.length + ')' : 'DESPACHAR TODO EL DOCK'" 
                        icon="fa fa-paper-plane" 
                        severity="success" 
                        @click="dispatchFromDock" 
                        :loading="processing" 
                        class="w-full" 
                    />
                </div>
            </div>
        </Dialog>
    </div>
</template>

<script>
import { useGeneralStore } from "../../store/index";
import Button from 'primevue/button';
import Dialog from 'primevue/dialog';
import DataTable from 'primevue/datatable';
import Column from 'primevue/column';
import Tag from 'primevue/tag';
import Select from 'primevue/select';
import InputText from 'primevue/inputtext';
import Accordion from 'primevue/accordion';
import AccordionPanel from 'primevue/accordionpanel';
import AccordionHeader from 'primevue/accordionheader';
import AccordionContent from 'primevue/accordioncontent';

export default {
    name: "ManualDispatch",
    components: {
        Button,
        Dialog,
        DataTable,
        Column,
        Tag,
        Select,
        InputText,
        Accordion,
        AccordionPanel,
        AccordionHeader,
        AccordionContent
    },
    data() {
        return {
            store: useGeneralStore(),
            loading: false,
            processing: false,
            activeBins: [],
            activeDocks: [],
            availableDocks: [],
            selectedBin: null,
            selectedBinContents: null,
            selectedBinPackages: [],
            showBinDialog: false,
            targetDockId: null,
            selectedDock: null,
            selectedDockContents: null,
            selectedDockPackages: [],
            showDockDialog: false,
            // Búsqueda
            searchTerm: '',
            searching: false,
            searched: false,
            searchResults: [],
            dispatching: false,
            printingWholesaleSheet: {},
            dispatchingWholesale: {}
        }
    },
    async mounted() {
        await this.refreshAll();
    },
    methods: {
        async refreshAll() {
            this.loading = true;
            try {
                const [bins, docks, availDocks] = await Promise.all([
                    this.store.callOdoo("get_active_bins", "", {}),
                    this.store.callOdoo("get_active_docks", "", {}),
                    this.store.callOdoo("get_available_docks", "", {})
                ]);
                this.activeBins = bins || [];
                this.activeDocks = docks || [];
                this.availableDocks = availDocks || [];
            } catch (e) {
                console.error("Error refreshing manual dispatch data", e);
            } finally {
                this.loading = false;
            }
        },
        async searchOrders() {
            if (!this.searchTerm) return;
            this.searching = true;
            this.searched = true;
            try {
                const res = await this.store.callOdoo("search_manual_dispatch", "", { term: this.searchTerm });
                this.searchResults = res || [];
            } catch (e) {
                console.error("Error searching orders", e);
            } finally {
                this.searching = false;
            }
        },
        async manualDispatchEI(ei, order) {
            this.dispatching = true;
            try {
                const res = await this.store.callOdoo("dispatch_orders", "", {
                    operator_login: this.store.role.email,
                    picks_ids: [ei.name]
                });
                if (res.status === 'success') {
                    this.store.toast.add({ severity: 'success', summary: 'Éxito', detail: `Paquete ${ei.name} despachado`, life: 3000 });
                    if (res.warning) {
                        this.store.toast.add({ severity: 'warn', summary: 'Atención', detail: res.warning, life: 5000 });
                    }
                    // Actualizar resultados de búsqueda
                    await this.searchOrders();
                    await this.refreshAll();
                } else {
                    this.store.toast.add({ severity: 'error', summary: 'Error', detail: res.message, life: 5000 });
                }
            } finally {
                this.dispatching = false;
            }
        },
        async printWholesaleDispatchSheet(order) {
            this.printingWholesaleSheet[order.id] = true;
            try {
                const response = await this.store.callOdoo("print_wholesale_dispatch_sheet", "", {
                    so_id: order.id,
                    operator_login: this.store.role.email
                });
                if (response && response.ok && response.action) {
                    console.log("Acción nativa recibida para Hoja de Salida. Buscando el puente con Odoo OWL...");
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
                        console.log("Enviando silenciosamente a IoT Box / Impresora...");
                        await actionService.doAction(response.action);
                        this.store.toast.add({ severity: 'success', summary: 'Impresión enviada', detail: 'Hoja de salida enviada a la impresora.', life: 3000 });
                    }
                    
                    // Abrir siempre la previsualización del PDF en una nueva pestaña
                    const pdfUrl = window.location.origin + `/report/pdf/wmds.report_dispatch_sheet_document/${response.session_id}`;
                    window.open(pdfUrl, '_blank');
                } else {
                    this.store.toast.add({ severity: 'error', summary: 'Error de impresión', detail: response?.error || 'No se pudo generar la acción de impresión.', life: 4000 });
                }
            } catch (e) {
                console.error("Error printing wholesale dispatch sheet", e);
                this.store.toast.add({ severity: 'error', summary: 'Error', detail: e.message || 'Error de conexión', life: 4000 });
            } finally {
                this.printingWholesaleSheet[order.id] = false;
            }
        },
        async dispatchWholesaleOrder(order) {
            this.dispatchingWholesale[order.id] = true;
            try {
                const res = await this.store.callOdoo("dispatch_wholesale_order", "", {
                    so_id: order.id,
                    operator_login: this.store.role.email
                });
                if (res.status === 'success') {
                    this.store.toast.add({ severity: 'success', summary: 'Éxito', detail: res.message || 'Pedido de Mayoreo despachado correctamente.', life: 3000 });
                    await this.searchOrders();
                    await this.refreshAll();
                } else {
                    this.store.toast.add({ severity: 'error', summary: 'Error', detail: res.message, life: 5000 });
                }
            } catch (e) {
                console.error("Error dispatching wholesale order", e);
                this.store.toast.add({ severity: 'error', summary: 'Error', detail: e.message || 'Error de conexión', life: 4000 });
            } finally {
                this.dispatchingWholesale[order.id] = false;
            }
        },
        getStatusSeverity(status) {
            switch (status) {
                case 'Despachado': return 'success';
                case 'En Dock': return 'info';
                case 'En Bin': return 'warn';
                default: return 'secondary';
            }
        },
        async selectBin(bin) {
            this.selectedBin = bin;
            this.targetDockId = null;
            this.selectedBinPackages = [];
            this.loading = true;
            try {
                const res = await this.store.callOdoo("validate_bin", "", { bin: bin.name, purpose: 'out' });
                if (res && res.valid) {
                    this.selectedBinContents = res;
                    this.showBinDialog = true;
                }
            } finally {
                this.loading = false;
            }
        },
        async selectDock(dock) {
            this.selectedDock = dock;
            this.selectedDockPackages = [];
            this.loading = true;
            try {
                const res = await this.store.callOdoo("get_dock_contents", "", { dock: dock.name });
                if (res && !res.error) {
                    this.selectedDockContents = res;
                    this.showDockDialog = true;
                }
            } finally {
                this.loading = false;
            }
        },
        async moveToDock() {
            if (!this.targetDockId || !this.selectedBin) return;
            this.processing = true;
            try {
                const res = await this.store.callOdoo("move_bin_to_dock", "", {
                    bin: this.selectedBin.name,
                    dock: this.targetDockId,
                    operator: this.store.role.email,
                    selected_packages: this.selectedBinPackages
                });
                if (res && res.ok) {
                    this.showBinDialog = false;
                    this.store.toast.add({ severity: 'success', summary: 'Éxito', detail: 'Paquetes movidos a Dock correctamente', life: 3000 });
                    await this.refreshAll();
                }
            } finally {
                this.processing = false;
            }
        },
        async dispatchFromDock() {
            if (!this.selectedDockContents) return;
            
            const packagesToProcess = this.selectedDockPackages.length > 0 
                ? this.selectedDockPackages 
                : this.selectedDockContents.package_details;

            if (packagesToProcess.length === 0) return;

            this.processing = true;
            try {
                let success = true;
                
                const ecommercePackages = packagesToProcess.filter(p => !p.is_full);
                const fulfillmentPackages = packagesToProcess.filter(p => p.is_full);

                // E-commerce dispatch
                if (ecommercePackages.length > 0) {
                    const picksIds = ecommercePackages.map(p => p.name);
                    
                    const res = await this.store.callOdoo("dispatch_orders", "", {
                        operator_login: this.store.role.email,
                        picks_ids: picksIds
                    });
                    if (res.status !== 'success') {
                        success = false;
                        this.store.toast.add({ severity: 'error', summary: 'Error Pedidos', detail: res.message, life: 5000 });
                    }
                }

                // Fulfillment dispatch
                if (fulfillmentPackages.length > 0) {
                    const items = fulfillmentPackages.map(p => ({ move_id: p.move_id, qty: p.qty }));
                    
                    const res = await this.store.callOdoo("dispatch_full_items", "", {
                        operator_login: this.store.role.email,
                        items: items
                    });
                    if (res.status !== 'success') {
                        success = false;
                        this.store.toast.add({ severity: 'error', summary: 'Error Fulfillment', detail: res.message, life: 5000 });
                    }
                }

                if (success) {
                    this.showDockDialog = false;
                    this.store.toast.add({ severity: 'success', summary: 'Éxito', detail: 'Productos despachados correctamente', life: 3000 });
                    await this.refreshAll();
                }
            } finally {
                this.processing = false;
            }
        }
    }
}
</script>

<style scoped>
.manual-dispatch-container {
    width: 100%;
    max-width: 1200px;
    height: calc(100vh - var(--o-we-toolbar-height, 60px));
    display: flex;
    flex-direction: column;
    overflow-y: auto;
    padding-bottom: 2rem;
}

.header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1rem;
    height: 4em;
    flex-shrink: 0;
}

.search-section {
    margin: 1rem 2rem 2rem 2rem;
    background: #ffffff;
    padding: 2rem;
    border-radius: 12px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.08);
    border: 1px solid #e2e8f0;
}

.search-bar {
    display: flex;
    gap: 1rem;
    margin-bottom: 1.5rem;
}

.search-input-large {
    font-size: 1.2rem !important;
    padding: 1rem !important;
}

.search-button-large {
    padding-left: 2rem !important;
    padding-right: 2rem !important;
    font-weight: bold !important;
}

.search-results-container {
    max-height: 500px;
    overflow-y: auto;
    border-radius: 8px;
    border: 1px solid #edf2f7;
    padding: 0.5rem;
    background: #f7fafc;
}

.order-header-large {
    display: flex;
    gap: 2.5rem;
    align-items: center;
    width: 100%;
    padding: 0.5rem 0;
}

.order-name-tag {
    font-weight: 800;
    font-size: 1.25rem;
    color: #1a202c;
    background: #ebf8ff;
    padding: 0.4rem 1rem;
    border-radius: 6px;
    border-left: 4px solid #3182ce;
}

.order-info-tag {
    color: #4a5568;
    font-size: 1rem;
    display: flex;
    align-items: center;
    gap: 0.5rem;
}

.order-info-tag.tracking {
    color: #2c5282;
    font-weight: 600;
}

.order-detail-container {
    display: flex;
    gap: 2rem;
    padding: 1rem;
    background: white;
    border-radius: 8px;
}

.detail-column {
    flex: 1;
    min-width: 0;
}

.detail-header {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    margin-bottom: 1rem;
    color: #2d3748;
    border-bottom: 2px solid #edf2f7;
    padding-bottom: 0.5rem;
}

.detail-header i {
    font-size: 1.2rem;
    color: #4a5568;
}

.detail-header h4 {
    margin: 0;
    font-size: 1.1rem;
    font-weight: 700;
}

.custom-table {
    border: 1px solid #edf2f7;
    border-radius: 4px;
}

.status-tag {
    font-weight: 600;
    text-transform: uppercase;
    font-size: 0.75rem;
}

.dispatch-btn {
    white-space: nowrap;
}

.empty-results {
    text-align: center;
    padding: 3rem;
    color: #a0aec0;
    font-size: 1.1rem;
    background: #f8fafc;
    border-radius: 8px;
}

.grid-container {
    display: flex;
    flex-direction: row;
    flex: 1;
    min-height: 400px;
    overflow: hidden;
}

.section-card {
    background: white;
    border-radius: 8px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
    padding: 1.5rem;
    display: flex;
    flex-direction: column;
    margin: 0 2rem 2rem 2rem;
    width: 50%;
    height: auto;
    max-height: 600px;
    overflow-y: auto;
}

.section-header {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 1.5rem;
    color: #2c3e50;
    border-bottom: 2px solid #3498db;
    padding-bottom: 0.5rem;
}

.section-header i {
    font-size: 1.5rem;
    color: #3498db;
}

.section-header h3 {
    margin: 0;
}

.item-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 1rem;
    border-bottom: 1px solid #ecf0f1;
    transition: background 0.2s;
}

.item-row.clickable:hover {
    background: #f8f9fa;
    cursor: pointer;
}

.item-info {
    display: flex;
    flex-direction: column;
}

.item-name {
    font-weight: bold;
    font-size: 1.1rem;
}

.item-detail {
    font-size: 0.85rem;
    color: #7f8c8d;
}

.empty-state {
    text-align: center;
    color: #bdc3c7;
    margin-top: 3rem;
}

.dialog-content {
    display: flex;
    flex-direction: column;
    gap: 1.5rem;
    margin-top: 1rem;
}

.dialog-actions {
    display: flex;
    flex-direction: column;
    gap: 1rem;
    padding-top: 1rem;
    border-top: 1px solid #ecf0f1;
}

@media screen and (max-width: 768px) {
    .manual-dispatch-container {
        height: auto;
        padding: 0.5rem;
    }
    .search-section {
        margin: 0.5rem;
        padding: 1rem;
    }
    .search-bar {
        flex-direction: column;
    }
    .order-header-large {
        flex-direction: column;
        align-items: flex-start;
        gap: 0.5rem;
    }
    .order-name-tag {
        font-size: 1.1rem;
        padding: 0.25rem 0.5rem;
        width: 100%;
    }
    .order-detail-container {
        flex-direction: column;
        gap: 1rem;
        padding: 0.5rem;
    }
    .grid-container {
        flex-direction: column;
        min-height: auto;
        overflow: visible;
    }
    .section-card {
        width: calc(100% - 1rem);
        margin: 0.5rem;
        max-height: 400px;
    }
    .wholesale-dispatch-banner {
        flex-direction: column;
        gap: 1rem;
        align-items: flex-start !important;
    }
    .wholesale-dispatch-banner .flex {
        width: 100%;
        flex-direction: column;
    }
    .wholesale-dispatch-banner button {
        width: 100%;
    }
}
</style>
