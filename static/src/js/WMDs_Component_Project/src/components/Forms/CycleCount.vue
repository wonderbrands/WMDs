<template>
    <div class="cycle-count-wrapper">
        <div class="cycle-count-modal">
            <h2 class="modal-title">{{ isCreating ? 'Nuevo Conteo Cíclico' : 'Gestionar Conteo' }}</h2>

            <div v-if="isCreating" class="wizard-stepper">
                <div :class="['step-pill', { active: currentStep === 1 }]">1. Selección</div>
                <div :class="['step-pill', { active: currentStep === 2 }]">2. Distribución de Olas</div>
            </div>

            <div v-if="isCreating">
                <div v-if="currentStep === 1" class="fade-in">
                    <div class="filter-section card-background">
                        <div class="filter-group">
                            <label class="filter-label">Pasillo (A - Z)</label>
                            <div class="flex-row gap-small">
                                <InputText v-model="filters.aisle_from" placeholder="A" maxlength="1" @input="filters.aisle_from = filters.aisle_from.toUpperCase()" class="input-full" />
                                <InputText v-model="filters.aisle_to" placeholder="C" maxlength="1" @input="filters.aisle_to = filters.aisle_to.toUpperCase()" class="input-full" />
                            </div>
                        </div>
                        <div class="filter-group">
                            <label class="filter-label">Posición (1 - 99)</label>
                            <div class="flex-row gap-small">
                                <InputNumber v-model="filters.position_from" :min="1" :max="99" placeholder="1" inputClass="input-full" />
                                <InputNumber v-model="filters.position_to" :min="1" :max="99" placeholder="99" inputClass="input-full" />
                            </div>
                        </div>
                        <div class="filter-group">
                            <label class="filter-label">Nivel (1 - 5)</label>
                            <div class="flex-row gap-small">
                                <InputNumber v-model="filters.level_from" :min="1" :max="5" placeholder="1" inputClass="input-full" />
                                <InputNumber v-model="filters.level_to" :min="1" :max="5" placeholder="5" inputClass="input-full" />
                            </div>
                        </div>
                        <div class="filter-group">
                            <label class="filter-label">Frente (1 - 2)</label>
                            <div class="flex-row gap-small">
                                <InputNumber v-model="filters.front_from" :min="1" :max="2" placeholder="1" inputClass="input-full" />
                                <InputNumber v-model="filters.front_to" :min="1" :max="2" placeholder="2" inputClass="input-full" />
                            </div>
                        </div>
                        <div class="filter-actions">
                            <Button label="Buscar Ubicaciones" icon="pi pi-search" @click="fetchLocations" :loading="store.loading" :disabled="isRangeInvalid" />
                        </div>
                    </div>

                    <div class="tables-container">
                        <div class="table-half">
                            <DataTable v-model:selection="tempSelection" :value="searchResults" paginator :rows="5" class="p-datatable-sm custom-border" :rowClass="rowClass" dataKey="id">
                                <template #header>
                                    <div class="flex-between">
                                        <span class="font-bold">Resultados ({{ searchResults.length }})</span>
                                        <Button label="Añadir Seleccionados" icon="pi pi-plus" class="p-button-sm p-button-success" @click="addSelected" :disabled="!tempSelection.length" />
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
                                        <span class="font-bold text-primary">A Contar ({{ selectedLocations.length }})</span>
                                        <Button label="Quitar Seleccionados" icon="pi pi-trash" class="p-button-sm p-button-danger p-button-outlined" @click="removeSelected" :disabled="!finalSelection.length" />
                                    </div>
                                </template>
                                <Column selectionMode="multiple" headerStyle="width: 3rem"></Column>
                                <Column field="complete_name" header="Ubicación"></Column>
                            </DataTable>
                        </div>
                    </div>

                    <div class="wizard-footer">
                        <Button label="Siguiente: Configurar Olas" icon="pi pi-arrow-right" iconPos="right" @click="currentStep = 2" :disabled="!selectedLocations.length" />
                    </div>
                </div>

                <div v-if="currentStep === 2" class="fade-in">
                    <div class="flex-between mb-medium">
                        <Button label="Regresar" icon="pi pi-arrow-left" class="p-button-text" @click="currentStep = 1" />
                        <Button label="Nueva Ola" icon="pi pi-plus-circle" @click="addNewTempWave" class="p-button-outlined" />
                    </div>
                    <div class="waves-container">
                        <div v-for="(wave, index) in tempWaves" :key="index" class="wave-card card-background">
                            <div class="flex-between mb-small">
                                <span class="wave-badge">Ola {{ index + 1 }}</span>
                                <Button icon="pi pi-trash" class="p-button-rounded p-button-text p-button-danger" @click="removeTempWave(index)" v-if="tempWaves.length > 1" />
                            </div>
                            <div class="mb-medium">
                                <label class="small-label">Operador Responsable</label>
                                <Dropdown v-model="wave.operator_id" :options="operators" optionLabel="name" optionValue="id" placeholder="Asignar..." class="input-full" />
                            </div>
                            <div class="wave-items-box">
                                <div class="items-header">Ubicaciones ({{ wave.locations.length }})</div>
                                <div v-if="!wave.locations.length" class="empty-msg">Sin ubicaciones</div>
                                <div v-for="loc in wave.locations" :key="loc.id" class="item-row">
                                    <span>{{ loc.complete_name }}</span>
                                    <i class="pi pi-times cursor-pointer text-red-500" @click="returnToUnassigned(wave, loc)"></i>
                                </div>
                            </div>
                        </div>
                    </div>
                    <div v-if="unassignedLocations.length" class="unassigned-box card-background mt-medium">
                        <h4 class="unassigned-title">Pendientes de Asignar ({{ unassignedLocations.length }})</h4>
                        <div class="flex-row wrap gap-small">
                            <div v-for="loc in unassignedLocations" :key="loc.id" class="loc-chip" @click="autoAssign(loc)">
                                {{ loc.complete_name }} <i class="pi pi-plus ml-1"></i>
                            </div>
                        </div>
                    </div>
                    <div class="final-save-section card-background">
                        <div class="ref-input">
                            <label class="filter-label">Referencia del Conteo</label>
                            <InputText v-model="newCount.ref" placeholder="Ej. Conteo Semanal" class="input-full" />
                        </div>
                        <Button label="GUARDAR CONTEO Y OLAS" icon="pi pi-save" severity="success" size="large" @click="saveFullCount" :loading="store.loading" :disabled="isSaveDisabled" />
                    </div>
                </div>
            </div>

            <div v-else class="fade-in">
                <div class="flex-between mb-medium">
                    <h2 class="modal-title no-margin">ID: {{ modalData?.name || modalData?.id }}</h2>
                    <Button label="Cerrar Ciclo" icon="pi pi-lock" severity="danger" @click="closeEntireCount" :loading="store.loading" />
                </div>
                <DataTable :value="waves" class="p-datatable-sm custom-border mb-medium">
                    <Column field="name" header="Ola"></Column>
                    <Column field="operator_name" header="Operador"></Column>
                    <Column field="state_label" header="Estado"></Column>
                    <Column header="Acciones">
                        <template #body="slotProps">
                            <Button v-if="slotProps.data.state !== 'done'" label="Finalizar" icon="pi pi-check" severity="success" class="p-button-text" @click="finishWave(slotProps.data.id)" />
                            <span v-else class="text-green-500 font-bold"><i class="pi pi-check-circle"></i> Lista</span>
                        </template>
                    </Column>
                </DataTable>
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
            operators: [],
            currentStep: 1,
            filters: { aisle_from: "", aisle_to: "", position_from: 1, position_to: 99, level_from: 1, level_to: 5, front_from: 1, front_to: 2 },
            searchResults: [],
            selectedLocations: [],
            tempSelection: [],
            finalSelection: [],
            tempWaves: [{ operator_id: null, locations: [] }],
            newCount: { ref: "" },
            waves: [],
            newWave: { name: "", operator_id: null }
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
        unassignedLocations() {
            const assignedIds = this.tempWaves.flatMap(w => w.locations.map(l => l.id));
            return this.selectedLocations.filter(l => !assignedIds.includes(l.id));
        },
        isSaveDisabled() {
            return !this.newCount.ref || this.unassignedLocations.length > 0 || this.tempWaves.some(w => !w.operator_id || !w.locations.length);
        }
    },
    async mounted() {
        await this.fetchOperators();
        if (!this.isCreating && this.modalData.id) await this.fetchWavesForCount();
    },
    methods: {
        async fetchOperators() {
            let res = await this.store.callOdoo("get_operators", "");
            if (res?.data) this.operators = res.data;
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
            this.tempWaves.forEach(w => { w.locations = w.locations.filter(l => !idsToRemove.includes(l.id)); });
            this.finalSelection = [];
        },
        addNewTempWave() { this.tempWaves.push({ operator_id: null, locations: [] }); },
        removeTempWave(idx) { this.tempWaves.splice(idx, 1); },
        autoAssign(loc) { this.tempWaves[0].locations.push(loc); },
        returnToUnassigned(wave, loc) { wave.locations = wave.locations.filter(l => l.id !== loc.id); },
        async saveFullCount() {
            const payload = {
                name: this.newCount.ref,
                waves: this.tempWaves.map(w => ({ operator_id: w.operator_id, location_ids: w.locations.map(l => l.id) }))
            };
            let res = await this.store.callOdoo("create_full_cycle_count", "", payload);
            if (res.ok) this.store.closeModal();
        },
        async fetchWavesForCount() {
            let res = await this.store.callOdoo("get_waves_for_count", "", { count_id: this.modalData.id });
            if (res?.waves) this.waves = res.waves;
        },
        async finishWave(id) {
            if (!confirm("¿Finalizar ola?")) return;
            let res = await this.store.callOdoo("finish_cycle_count_wave", "", { wave_id: id });
            if (res.ok) await this.fetchWavesForCount();
        },
        async closeEntireCount() {
            if (!confirm("¿Cerrar ciclo?")) return;
            let res = await this.store.callOdoo("close_cycle_count", "", { count_id: this.modalData.id });
            if (res.ok) this.store.closeModal();
        }
    }
};
</script>

<style scoped>
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
.wizard-footer { display: flex; justify-content: flex-end; margin-top: 1rem; }
.waves-container { display: flex; flex-wrap: wrap; gap: 1.2rem; }
.wave-card { flex: 1 1 calc(33.33% - 1.2rem); min-width: 300px; border-top: 5px solid #007bff; }
.wave-badge { background: #007bff; color: white; padding: 0.2rem 0.8rem; border-radius: 5px; font-size: 0.8rem; font-weight: bold; }
.wave-items-box { background: #fff; border: 1px solid #eee; border-radius: 5px; min-height: 120px; max-height: 250px; overflow-y: auto; }
.items-header { background: #f1f1f1; padding: 0.4rem; font-size: 0.8rem; font-weight: bold; position: sticky; top: 0; }
.item-row { display: flex; justify-content: space-between; padding: 0.4rem; border-bottom: 1px solid #f9f9f9; font-size: 0.8rem; }
.unassigned-box { border-left: 5px solid #fd7e14; }
.unassigned-title { color: #fd7e14; font-weight: 800; margin-bottom: 0.8rem; }
.loc-chip { background: #fff; border: 1px solid #ddd; padding: 0.3rem 0.6rem; border-radius: 4px; font-size: 0.75rem; cursor: pointer; }
.final-save-section { display: flex; flex-wrap: wrap; gap: 1.5rem; align-items: flex-end; margin-top: 2rem; border-bottom: 5px solid #28a745; }
.ref-input { flex: 1 1 60%; }
.flex-row { display: flex; align-items: center; }
.flex-row.wrap { flex-wrap: wrap; }
.flex-between { display: flex; justify-content: space-between; align-items: center; }
.gap-small { gap: 0.5rem; }
.input-full { width: 100%; }
.fade-in { animation: fadeIn 0.3s ease-in; }
@keyframes fadeIn { from { opacity: 0; transform: translateY(5px); } to { opacity: 1; transform: translateY(0); } }
</style>