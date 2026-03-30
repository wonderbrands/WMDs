<template>
    <div class="batch_detail_view" v-if="batch_data">
        <div class="title_section mb-4">
            <h1 class="text-2xl font-bold">Plan de Pickeo: {{ batch_data.name }}</h1>
        </div>

        <div class="operator-assignment mb-4">
            <div class="operator-field">
                <label class="block font-medium mb-2">Operador Asignado</label>
                <div class="flex gap-2">
                    <Select v-model="selected_operator" 
                        :options="operators" 
                        optionLabel="name" 
                        placeholder="Seleccionar operador" 
                        class="w-full"
                        filter
                        @filter="onFilterOperators"
                    />
                    <Button label="Reasignar" icon="pi pi-user-edit" severity="info" @click="reassignOperator" :disabled="!selected_operator || selected_operator.id === batch_data.operator?.id" />
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
                            <span class="font-bold text-blue-700">{{ pick.name }}</span>
                            <span class="text-sm text-gray-600">Pedido: {{ pick.origin }}</span>
                        </div>
                        
                        <DataTable :value="products[pick.id]" v-if="products[pick.id]" class="p-datatable-sm shadow-1 border-round overflow-hidden">
                            <Column field="product_id" header="Producto"></Column>
                            <Column field="sku" header="SKU"></Column>
                            <Column field="product_uom_qty" header="Cant." class="text-center"></Column>
                            <Column field="product_uom" header="UM"></Column>
                        </DataTable>
                        <div v-else class="flex justify-content-center p-4">
                            <i class="pi pi-spin pi-spinner" style="font-size: 1.5rem"></i>
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
        <i class="pi pi-spin pi-spinner" style="font-size: 2rem"></i>
    </div>
</template>

<script>
import Select from 'primevue/select';
import Button from 'primevue/button';
import DataTable from 'primevue/datatable';
import Column from 'primevue/column';
import Timeline from 'primevue/timeline';
import { useGeneralStore } from "../../store/index";

export default {
    name: "BatchDetailView",
    components: { Select, Button, DataTable, Column, Timeline },
    data() {
        return {
            store: useGeneralStore(),
            batch_data: null,
            operators: [],
            selected_operator: null,
            debounceTimeout: null,
            products: {}
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
        }
    },
    async mounted() {
        await this.loadBatchData();
        await this.loadOperators();
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