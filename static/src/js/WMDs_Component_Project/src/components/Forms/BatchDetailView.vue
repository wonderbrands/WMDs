<template>
    <div class="batch_detail_view" v-if="batch_data">
        <div class="title_section mb-4 flex justify-content-between align-items-center">
            <h1 class="text-2xl font-bold">Plan de Pickeo: {{ batch_data.name }}</h1>
            <Button v-if="batch_data.state !== 'cancel' && batch_data.state !== 'done'" 
                label="Cancelar Plan" 
                icon="fa fa-trash" 
                severity="danger" 
                @click="showCancelDialog = true" 
            />
        </div>

        <!-- Cancel Confirmation Dialog -->
        <Dialog v-model:visible="showCancelDialog" header="Confirmar Cancelación" modal :style="{ width: '450px' }">
            <div class="confirmation-content flex align-items-center gap-3 p-3">
                <i class="fa fa-exclamation-triangle text-red-500" style="font-size: 2rem"></i>
                <div>
                    <p class="font-bold mb-2">¿Está seguro de cancelar este plan de pickeo?</p>
                    <p class="text-sm text-700">Esto regresará el producto a su ubicación en sistema de los traslados que ya se hayan completado, verifique que sus operadores dejen el producto donde estaba.</p>
                </div>
            </div>
            <template #footer>
                <Button label="No, mantener" icon="fa fa-times" @click="showCancelDialog = false" class="p-button-text" />
                <Button label="Sí, cancelar plan" icon="fa fa-check" severity="danger" @click="confirmCancelBatch" :loading="cancelling" />
            </template>
        </Dialog>

        <!-- Remove Picking Confirmation Dialog -->
        <Dialog v-model:visible="showRemoveDialog" header="Remover Orden del Lote" modal :style="{ width: '450px' }">
            <div class="flex flex-column gap-3 p-2">
                <div class="flex align-items-center gap-3">
                    <i class="fa fa-info-circle text-blue-500" style="font-size: 2rem"></i>
                    <p>Está por remover la orden <b>{{ pickingToRemove?.name }}</b> del lote.</p>
                </div>

                <!-- Warning if picking has progress -->
                <div v-if="hasPickingProgress(pickingToRemove?.id)" class="p-3 border-round bg-yellow-100 border-yellow-300 border-1 flex align-items-start gap-3">
                    <i class="fa fa-exclamation-triangle text-yellow-700 mt-1"></i>
                    <div>
                        <p class="font-bold text-yellow-900 mb-1">Advertencia: Orden en progreso</p>
                        <p class="text-sm text-yellow-800">Esta orden ya tiene productos recolectados. Al removerla, las cantidades en el sistema regresarán a su ubicación de origen. Asegúrese de que el operador devuelva físicamente el producto.</p>
                    </div>
                </div>

                <div class="flex flex-column gap-2">
                    <label for="reason" class="font-bold">Razón de remoción</label>
                    <textarea v-model="removalReason" rows="3" class="p-inputtext p-component w-full" placeholder="Ingrese el motivo por el cual se remueve esta orden..."></textarea>
                </div>
            </div>
            <template #footer>
                <Button label="Cancelar" icon="fa fa-times" @click="showRemoveDialog = false" class="p-button-text" />
                <Button label="Remover Orden" icon="fa fa-trash" severity="danger" @click="confirmRemovePicking" :loading="removing" :disabled="!removalReason || removalReason.trim().length < 5" />
            </template>
        </Dialog>

        <!-- BIN ASSIGNMENT (For all types when in progress or done) -->
        <div class="operator-assignment mb-4" v-if="['full', 'wholesale', 'sale'].includes(batch_data.pick_type) && ['in_progress', 'done'].includes(batch_data.state)">
            <div class="operator-field">
                <label class="block font-medium mb-2">BIN de destino</label>
                <div class="flex gap-2">
                    <Select v-model="selected_bin" 
                        :options="available_bins" 
                        optionLabel="name" 
                        dataKey="id"
                        placeholder="Seleccionar BIN" 
                        class="w-full"
                        filter
                    />
                    <Button label="Asignar BIN" icon="fa fa-archive" severity="success" @click="assignBinToBatch" :disabled="!selected_bin || (batch_data.bin && selected_bin.id === batch_data.bin.id)" />
                </div>
            </div>
        </div>

        <!-- PACKER ASSIGNMENT (Only for sale and done) -->
        <div class="operator-assignment mb-4" v-if="batch_data.pick_type === 'sale' && batch_data.state === 'done'">
            <div class="operator-field">
                <label class="block font-medium mb-2">Mesa de empaque</label>
                <div class="flex gap-2">
                    <Select v-model="selected_packer" 
                        :options="operators" 
                        optionLabel="name" 
                        dataKey="id"
                        placeholder="Seleccionar mesa de empaque" 
                        class="w-full"
                        filter
                        @filter="onFilterOperators"
                    />
                    <Button label="Asignar Mesa" icon="fa fa-box" severity="warning" @click="assignPackerToAll" :disabled="!selected_packer || (batch_data.packer && selected_packer.id === batch_data.packer.id)" />
                </div>
            </div>
        </div>

        <!-- OPERATOR ASSIGNMENT -->
        <div class="operator-assignment mb-4">
            <div class="operator-field">
                <label class="block font-medium mb-2">Operador Asignado</label>
                <div class="flex gap-2">
                    <Select v-model="selected_operator" 
                        :options="operators" 
                        optionLabel="name" 
                        dataKey="id"
                        placeholder="Seleccionar operador" 
                        class="w-full"
                        filter
                        @filter="onFilterOperators"
                    />
                    <Button label="Reasignar" icon="fa fa-user" severity="info" @click="reassignOperator" :disabled="!selected_operator || selected_operator.id === (batch_data.operator ? batch_data.operator.id : null) || (batch_data.state !== 'draft' && batch_data.state !== 'in_progress')" />
                </div>
            </div>
        </div>

        <!-- Main Content Row: Products and Logs side by side -->
        <div class="content-row">
            <!-- Left Column: Pick-Products (50%) -->
            <div class="column products-column">
                <h3 class="text-lg font-semibold mb-3">Órdenes y Productos</h3>
                <div class="picks-container overflow-y-auto" style="max-height: 65vh;">
                    <div v-for="pick in batch_data.picks" :key="pick.id" class="mb-4 p-3 surface-100 border-round shadow-1">
                        <div class="flex justify-content-between align-items-center mb-2">
                            <div class="flex flex-column">
                                <span class="font-bold text-blue-700 text-lg">{{ pick.name }}</span>
                                <span class="text-sm text-gray-600">Pedido: {{ pick.origin }}</span>
                            </div>
                            <Button icon="fa fa-minus-circle" 
                                severity="danger" 
                                class="p-button-rounded p-button-text" 
                                v-tooltip="'Remover del lote'"
                                @click="requestRemovePicking(pick)"
                                v-if="batch_data.state !== 'cancel' && batch_data.state !== 'done'"
                            />
                        </div>
                        
                        <DataTable :value="products[pick.id]" v-if="products[pick.id]" class="p-datatable-sm shadow-1 border-round overflow-hidden">
                            <Column field="product_id" header="Producto"></Column>
                            <Column field="sku" header="SKU"></Column>
                            <Column field="product_uom_qty" header="Cant." class="text-center"></Column>
                            <Column field="product_uom" header="UM"></Column>
                        </DataTable>
                        <div v-else class="flex justify-content-center p-4">
                            <i class="fa fa-spin fa-spinner" style="font-size: 1.5rem"></i>
                        </div>
                    </div>
                    <div v-if="batch_data.picks.length === 0" class="text-center p-4 text-gray-500">
                        Sin órdenes asignadas
                    </div>
                </div>
            </div>

            <!-- Right Column: Timeline (50%) -->
            <div class="column logs-column">
                <h3 class="text-lg font-semibold mb-3">Línea de Tiempo (Logs)</h3>
                <div class="timeline-container overflow-y-auto" style="max-height: 65vh;">
                    <Timeline :value="batch_data.logs" class="customized-timeline">
                        <template #opposite="slotProps">
                            <small class="text-gray-500">{{ store.formatDate(slotProps.item.date) }}</small>
                        </template>
                        <template #content="slotProps">
                            <div class="p-3 border-round surface-card shadow-1 mb-3">
                                <div class="font-bold text-blue-600 mb-1">{{ slotProps.item.user }}</div>
                                <div class="text-700">{{ slotProps.item.log }}</div>
                            </div>
                        </template>
                    </Timeline>
                </div>
            </div>
        </div>
    </div>
    <div v-else class="flex justify-content-center align-items-center h-full">
        <i class="fa fa-spin fa-spinner" style="font-size: 2rem"></i>
    </div>
</template>

<script>
import Select from 'primevue/select';
import Button from 'primevue/button';
import DataTable from 'primevue/datatable';
import Column from 'primevue/column';
import Timeline from 'primevue/timeline';
import Dialog from 'primevue/dialog';
import { useGeneralStore } from "../../store/index";

export default {
    name: "BatchDetailView",
    components: { Select, Button, DataTable, Column, Timeline, Dialog },
    data() {
        return {
            store: useGeneralStore(),
            batch_data: null,
            operators: [],
            available_bins: [],
            selected_operator: null,
            selected_packer: null,
            selected_bin: null,
            debounceTimeout: null,
            products: {},
            showCancelDialog: false,
            cancelling: false,
            showRemoveDialog: false,
            removalReason: "",
            pickingToRemove: null,
            removing: false
        }
    },
    methods: {
        async loadBatchData() {
            const batch_id = this.store.form_context.data.id;
            const result = await this.store.callOdoo("batch_details", "", { id: batch_id });
            if (!result.error) {
                this.batch_data = result;
                if (result.operator) {
                    this.selected_operator = result.operator;
                    // Ensure assigned operator is in the list
                    if (!this.operators.some(o => o.id === result.operator.id)) {
                        this.operators.push(result.operator);
                    }
                }
                if (result.packer) {
                    this.selected_packer = result.packer;
                    // Ensure assigned packer is in the list
                    if (!this.operators.some(o => o.id === result.packer.id)) {
                        this.operators.push(result.packer);
                    }
                }
                if (result.bin) {
                    this.selected_bin = result.bin;
                    if (!this.available_bins.some(b => b.id === result.bin.id)) {
                        this.available_bins.push(result.bin);
                    }
                }
                
                // Fetch products for all picks in parallel
                const productPromises = result.picks.map(async (pick) => {
                    const prodResult = await this.store.callOdoo("pick_products", "", { id: pick.id });
                    if (!prodResult.error) {
                        this.products[pick.id] = prodResult.data;
                    }
                });
                await Promise.all(productPromises);
            }
        },
        async loadOperators(term = "*") {
            const results = await this.store.callOdoo("operadores", term);
            this.operators = results || [];
        },
        async loadBins() {
            const results = await this.store.callOdoo("get_available_bins", "", {});
            this.available_bins = results || [];
        },
        onFilterOperators(event) {
            clearTimeout(this.debounceTimeout);
            this.debounceTimeout = setTimeout(() => {
                this.loadOperators(event.value);
            }, 500);
        },
        async reassignOperator() {
            if (!this.selected_operator) return;
            
            const payload = {
                id: this.batch_data.id,
                is_batch: true,
                responsible: { id: this.selected_operator.id }
            };
            
            const result = await this.store.callOdoo("assign_pick", "", payload);
            if (result.saved) {
                await this.loadBatchData();
            }
        },
        async assignPackerToAll() {
            if (!this.selected_packer) return;
            
            const payload = {
                id: this.batch_data.id,
                is_batch: true,
                operation_type: "Pack",
                operator: { id: this.selected_packer.id }
            };
            
            const result = await this.store.callOdoo("assign_pick", "", payload);
            if (!result.error) {
                this.store.toast.add({ severity: 'success', summary: 'Asignado', detail: 'Mesa de empaque asignada exitosamente a todos los pedidos.', life: 3000 });
                await this.loadBatchData();
            }
        },
        async assignBinToBatch() {
            if (!this.selected_bin) return;
            
            const payload = {
                id: this.batch_data.id,
                is_batch: true,
                bin_id: { id: this.selected_bin.id }
            };
            
            const result = await this.store.callOdoo("assign_pick", "", payload);
            if (!result.error) {
                this.store.toast.add({ severity: 'success', summary: 'Asignado', detail: 'BIN asignado exitosamente al lote.', life: 3000 });
                await this.loadBatchData();
            }
        },
        async confirmCancelBatch() {
            this.cancelling = true;
            try {
                const result = await this.store.callOdoo("cancel_batch", "", { id: this.batch_data.id });
                if (!result.error) {
                    this.store.toast.add({ severity: 'success', summary: 'Cancelado', detail: result.message, life: 3000 });
                    this.showCancelDialog = false;
                    await this.loadBatchData();
                } else {
                    this.store.toast.add({ severity: 'error', summary: 'Error', detail: result.error_msg, life: 5000 });
                }
            } finally {
                this.cancelling = false;
            }
        },
        hasPickingProgress(pickId) {
            if (!pickId || !this.products[pickId]) return false;
            return this.products[pickId].some(p => p.wmds_picked_qty > 0);
        },
        requestRemovePicking(pick) {
            this.pickingToRemove = pick;
            this.removalReason = "";
            this.showRemoveDialog = true;
        },
        async confirmRemovePicking() {
            if (!this.removalReason || this.removalReason.trim().length < 5) return;
            
            this.removing = true;
            try {
                const payload = {
                    batch_id: this.batch_data.id,
                    picking_id: this.pickingToRemove.id,
                    reason: this.removalReason
                };
                
                const result = await this.store.callOdoo("remove_picking_from_batch", "", payload);
                if (!result.error) {
                    this.store.toast.add({ severity: 'success', summary: 'Éxito', detail: result.message, life: 3000 });
                    this.showRemoveDialog = false;
                    await this.loadBatchData();
                } else {
                    this.store.toast.add({ severity: 'error', summary: 'Error', detail: result.error_msg, life: 5000 });
                }
            } finally {
                this.removing = false;
            }
        }
    },
    async mounted() {
        await this.loadBatchData();
        await this.loadOperators();
        await this.loadBins();
    }
}
</script>

<style scoped>
.batch_detail_view {
    padding: 1rem;
    height: 100%;
    overflow-y: auto;
    width: 100%;
}

.operator-assignment {
    width: 100%;
    display: flex;
    justify-content: flex-start;
}

.operator-field {
    width: 50%; /* Same width as columns for consistency */
    min-width: 300px;
}

.content-row {
    display: flex;
    flex-wrap: wrap;
    width: 100%;
    gap: 2rem;
}

.column {
    flex: 1;
    min-width: 300px;
}

.customized-timeline {
    margin-top: 1rem;
}

.timeline-container, .picks-container {
    padding-right: 15px;
    padding-left: 5px;
}
</style>