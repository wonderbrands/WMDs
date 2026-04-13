<template>
    <div class="manual-dispatch-container">
        <div class="header">
            <h2>Gestión Manual de Salidas</h2>
            <Button icon="fa fa-refresh" severity="secondary" rounded text @click="refreshAll" :loading="loading" title="Actualizar todo" />
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
        <Dialog v-model:visible="showBinDialog" :header="'Detalle de BIN: ' + (selectedBin?.name || '')" :style="{ width: '55vw' }" modal>
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
        <Dialog v-model:visible="showDockDialog" :header="'Detalle de DOCK: ' + (selectedDock?.name || '')" :style="{ width: '55vw' }" modal>
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

export default {
    name: "ManualDispatch",
    components: {
        Button,
        Dialog,
        DataTable,
        Column,
        Tag,
        Select
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
}

.header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 2rem;
}

.grid-container {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 2rem;
}

.section-card {
    background: white;
    border-radius: 8px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
    padding: 1.5rem;
    display: flex;
    flex-direction: column;
    min-height: 400px;
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
</style>
