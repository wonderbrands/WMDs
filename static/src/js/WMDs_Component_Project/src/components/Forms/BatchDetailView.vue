<template>
    <div class="batch_detail_view" v-if="batch_data">
        <div class="title_section mb-4">
            <h1 class="text-2xl font-bold">Plan de Pickeo: {{ batch_data.name }}</h1>
        </div>

        <div class="grid formgrid p-fluid mb-4">
            <div class="col-12 md:col-6">
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

        <div class="mb-6">
            <h3 class="text-lg font-semibold mb-3">Órdenes que lo componen</h3>
            <DataTable :value="batch_data.picks" stripedRows class="p-datatable-sm shadow-1 border-round overflow-hidden">
                <Column field="id" header="ID" style="width: 10%"></Column>
                <Column field="name" header="Referencia" style="width: 45%"></Column>
                <Column field="origin" header="Pedido (SO)" style="width: 45%"></Column>
            </DataTable>
        </div>

        <div>
            <h3 class="text-lg font-semibold mb-3">Línea de Tiempo (Logs)</h3>
            <Timeline :value="batch_data.logs" class="customized-timeline">
                <template #opposite="slotProps">
                    <small class="text-gray-500">{{ formatDate(slotProps.item.date) }}</small>
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
            debounceTimeout: null
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
                // Log the reassignment locally or refresh data
                await this.loadBatchData();
            }
        },
        formatDate(dateStr) {
            if (!dateStr) return "";
            const date = new Date(dateStr);
            return date.toLocaleString();
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
}
.customized-timeline {
    margin-top: 1rem;
}
</style>
