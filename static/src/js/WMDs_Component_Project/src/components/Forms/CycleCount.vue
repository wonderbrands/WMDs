<template>
    <div class="cycle-count-wrapper">
        <div class="cycle-count-modal">
            <h2 class="modal-title">{{ isCreating ? 'Nuevo Conteo Cíclico' : 'Gestionar Conteo' }}</h2>

            <div v-if="isCreating" class="wizard-stepper">
                <div :class="['step-pill', { active: currentStep === 1 }]">1. Selección</div>
                <div :class="['step-pill', { active: currentStep === 2 }]">2. Asignación</div>
            </div>

            <div v-if="isCreating">
                <div v-if="currentStep === 1" class="fade-in">
                    <div class="filter-section card-background">
                        <div class="filter-group">
                            <label class="filter-label">Pasillo (A - Z)</label>
                            <div class="flex-row gap-small">
                                <InputText v-model="filters.aisle_from" maxlength="1" @input="filters.aisle_from = filters.aisle_from.toUpperCase()" class="input-full" />
                                <InputText v-model="filters.aisle_to" maxlength="1" @input="filters.aisle_to = filters.aisle_to.toUpperCase()" class="input-full" />
                            </div>
                        </div>
                        <div class="filter-actions">
                            <Button label="Buscar" icon="pi pi-search" @click="fetchLocations" :loading="store.loading" :disabled="isRangeInvalid" />
                        </div>
                    </div>

                    <div class="tables-container">
                        <div class="table-half">
                            <DataTable v-model:selection="tempSelection" :value="searchResults" paginator :rows="5" class="p-datatable-sm custom-border" dataKey="id">
                                <template #header>
                                    <div class="flex-between">
                                        <span class="font-bold">Resultados ({{ searchResults.length }})</span>
                                        <Button label="Añadir" icon="pi pi-plus" class="p-button-sm p-button-success" @click="addSelected" :disabled="!tempSelection.length" />
                                    </div>
                                </template>
                                <Column selectionMode="multiple" headerStyle="width: 3rem" :selectable="isSelectable"></Column>
                                <Column field="complete_name" header="Ubicación Encontrada"></Column>
                            </DataTable>
                        </div>
                        <div class="table-half">
                            <DataTable v-model:selection="finalSelection" :value="selectedLocations" paginator :rows="5" class="p-datatable-sm custom-border" dataKey="id">
                                <template #header>
                                    <div class="flex-between">
                                        <span class="font-bold text-primary">Seleccionadas ({{ selectedLocations.length }})</span>
                                        <Button label="Quitar" icon="pi pi-trash" class="p-button-sm p-button-danger p-button-outlined" @click="removeSelected" :disabled="!finalSelection.length" />
                                    </div>
                                </template>
                                <Column selectionMode="multiple" headerStyle="width: 3rem"></Column>
                                <Column field="complete_name" header="Ubicación"></Column>
                            </DataTable>
                        </div>
                    </div>
                    <div class="wizard-footer">
                        <Button label="Siguiente" icon="pi pi-arrow-right" iconPos="right" @click="currentStep = 2" :disabled="!selectedLocations.length" />
                    </div>
                </div>

                <div v-if="currentStep === 2" class="fade-in">
                    <div class="card-background mb-medium">
                        <div class="flex-between">
                            <Button label="Volver" icon="pi pi-arrow-left" class="p-button-text" @click="currentStep = 1" />
                            <div class="ref-container">
                                <label class="filter-label">Referencia / Notas del Conteo</label>
                                <InputText v-model="newCount.ref" placeholder="Ej: Auditoría Pasillo A" class="input-ref" />
                            </div>
                            <Button label="Añadir Ola" icon="pi pi-user-plus" class="p-button-outlined" @click="addOperatorField" />
                        </div>
                    </div>

                    <div class="operators-grid">
                        <div v-for="(op, index) in assignedOperators" :key="index" class="operator-card card-background">
                            <div class="flex-between mb-small">
                                <span class="wave-number">Ola #{{ index + 1 }}</span>
                                <Button icon="pi pi-times" class="p-button-rounded p-button-danger p-button-text" @click="removeOperatorField(index)" v-if="assignedOperators.length > 1" />
                            </div>
                            <label class="small-label">Responsable</label>
                            
                            <Dropdown 
                                v-model="op.operator_id" 
                                :options="optionsCache['operadores']" 
                                optionLabel="name" 
                                optionValue="id" 
                                placeholder="Seleccionar..." 
                                class="input-full" 
                                filter
                                :loading="loadingOptions"
                            />
                        </div>
                    </div>

                    <div class="final-footer mt-large">
                        <Button label="GENERAR CONTEO" icon="pi pi-save" severity="success" size="large" @click="saveFullCount" :loading="store.loading" :disabled="isSaveDisabled" />
                    </div>
                </div>
            </div>

            <div v-else class="fade-in">
                </div>
        </div>
    </div>
</template>

<script>
import { useGeneralStore } from "../../store/index";
import InputText from "primevue/inputtext";
import InputNumber from "primevue/inputnumber";
import Button from "primevue/button";
import DataTable from "primevue/datatable";
import Column from "primevue/column";
import Dropdown from "primevue/dropdown";

export default {
    name: "CycleCountModal",
    components: { InputText, InputNumber, Button, DataTable, Column, Dropdown },
    data() {
        return {
            store: useGeneralStore(),
            currentStep: 1,
            filters: { aisle_from: "", aisle_to: "", position_from: 1, position_to: 99, level_from: 1, level_to: 5, front_from: 1, front_to: 2 },
            searchResults: [],
            selectedLocations: [],
            tempSelection: [],
            finalSelection: [],
            assignedOperators: [{ operator_id: null }],
            newCount: { ref: "" },
            waves: [],
            
            // Lógica de cache igual a la del componente genérico
            optionsCache: {
                operadores: []
            },
            loadingOptions: false
        };
    },
    computed: {
        modalData() { return this.store.form_context?.data || {}; },
        isCreating() { return !!this.modalData.cycle_count || this.modalData.form_type === 'new'; },
        isRangeInvalid() {
            const f = this.filters;
            if (!f.aisle_from || !f.aisle_to) return true;
            return (f.aisle_from > f.aisle_to) || (f.position_from > f.position_to) || (f.level_from > f.level_to) || (f.front_from > f.front_to);
        },
        isSaveDisabled() {
            return !this.newCount.ref || this.assignedOperators.some(op => !op.operator_id) || !this.selectedLocations.length;
        }
    },
    async mounted() {
        // Inicializamos la carga de operadores al montar
        await this.loadOperators();
        if (!this.isCreating && this.modalData.id) await this.fetchWavesForCount();
    },
    methods: {
        // Replicamos la lógica de carga del GenericFormView
        async loadOperators() {
            this.loadingOptions = true;
            try {
                const results = await this.store.callOdoo("operadores", "*");
                // Manejamos la respuesta según como llegue de Odoo (Array o .data)
                const data = results?.data || (Array.isArray(results) ? results : []);
                
                // Actualizamos el cache usando el spread para mantener reactividad
                this.optionsCache = {
                    ...this.optionsCache,
                    operadores: data
                };
            } catch (e) {
                console.error("Error cargando operadores en modal:", e);
            } finally {
                this.loadingOptions = false;
            }
        },
        async fetchLocations() {
            let res = await this.store.callOdoo("get_locations_by_range", "", this.filters);
            if (res?.locations) { this.searchResults = res.locations; this.tempSelection = []; }
        },
        isAlreadySelected(data) { return this.selectedLocations.some(s => s.id === data.id); },
        isSelectable(event) { return !this.isAlreadySelected(event.data); },
        rowClass(data) { return this.isAlreadySelected(data) ? 'row-locked' : ''; },
        addSelected() {
            const toAdd = this.tempSelection.filter(item => !this.isAlreadySelected(item));
            this.selectedLocations = [...this.selectedLocations, ...toAdd];
            this.tempSelection = [];
        },
        removeSelected() {
            const idsToRemove = this.finalSelection.map(s => s.id);
            this.selectedLocations = this.selectedLocations.filter(l => !idsToRemove.includes(l.id));
            this.finalSelection = [];
        },
        addOperatorField() { this.assignedOperators.push({ operator_id: null }); },
        removeOperatorField(idx) { this.assignedOperators.splice(idx, 1); },
        async saveFullCount() {
            const payload = {
                name: this.newCount.ref,
                location_ids: this.selectedLocations.map(l => l.id),
                operators: this.assignedOperators.map(op => op.operator_id)
            };
            let res = await this.store.callOdoo("create_full_cycle_count", "", payload);
            if (res.ok) this.store.closeModal();
        },
        async fetchWavesForCount() {
            let res = await this.store.callOdoo("get_waves_for_count", "", { count_id: this.modalData.id });
            if (res?.waves) this.waves = res.waves;
        },
        async finishWave(id) {
            let res = await this.store.callOdoo("finish_cycle_count_wave", "", { wave_id: id });
            if (res.ok) await this.fetchWavesForCount();
        },
        async closeEntireCount() {
            let res = await this.store.callOdoo("close_cycle_count", "", { count_id: this.modalData.id });
            if (res.ok) this.store.closeModal();
        }
    }
};
</script>

<style scoped>
/* (Estilos mantenidos igual al diseño anterior) */
.cycle-count-wrapper { padding: 1.5rem; }
.cycle-count-modal { max-width: 1050px; margin: 0 auto; color: #333; }
.modal-title { font-size: 1.6rem; font-weight: 800; margin-bottom: 1.5rem; }
.wizard-stepper { display: flex; justify-content: center; gap: 1rem; margin-bottom: 2rem; }
.step-pill { padding: 0.6rem 1.5rem; background: #e9ecef; border-radius: 25px; font-weight: 700; color: #999; }
.step-pill.active { background: #007bff; color: #fff; box-shadow: 0 4px 10px rgba(0,123,255,0.3); }
.card-background { background: #f9f9f9; padding: 1.25rem; border-radius: 8px; border: 1px solid #eee; }
.filter-section { display: flex; flex-wrap: wrap; gap: 1rem; margin-bottom: 1.5rem; }
.filter-group { flex: 1 1 calc(25% - 1rem); min-width: 180px; }
.filter-label { display: block; font-weight: 700; font-size: 0.85rem; margin-bottom: 0.4rem; }
.filter-actions { flex: 1 1 100%; display: flex; justify-content: flex-end; }
.tables-container { display: flex; flex-wrap: wrap; gap: 1.5rem; margin-bottom: 1.5rem; }
.table-half { flex: 1 1 calc(50% - 1.5rem); min-width: 350px; }
.custom-border { border: 1px solid #ddd; border-radius: 8px; overflow: hidden; }
:deep(.row-locked) { background-color: #e8f5e9 !important; color: #2e7d32 !important; font-style: italic; }
:deep(.row-locked .p-checkbox) { display: none; }
.input-ref { width: 350px; }
.operator-card { border-left: 5px solid #007bff; margin-top: 10px; }
.flex-between { display: flex; justify-content: space-between; align-items: center; }
.input-full { width: 100%; }
.fade-in { animation: fadeIn 0.3s ease-in; }
@keyframes fadeIn { from { opacity: 0; transform: translateY(5px); } to { opacity: 1; transform: translateY(0); } }
</style>