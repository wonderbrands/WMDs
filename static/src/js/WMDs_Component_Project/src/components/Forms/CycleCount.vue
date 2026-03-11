<template>
    <div class="cycle-count-modal">
        <div v-if="isCreating">
            <h2 class="modal-title">Crear Nuevo Conteo Cíclico</h2>
            
            <div class="filter-section card-background">
                <div class="filter-group">
                    <label class="filter-label">Pasillo (A - Z)</label>
                    <div class="flex-row gap-small">
                        <InputText v-model="filters.aisle_from" placeholder="A" maxlength="1" 
                                   @input="filters.aisle_from = filters.aisle_from.toUpperCase()" class="input-full" />
                        <InputText v-model="filters.aisle_to" placeholder="C" maxlength="1" 
                                   @input="filters.aisle_to = filters.aisle_to.toUpperCase()" class="input-full" />
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
                    <Button label="Buscar Ubicaciones" icon="pi pi-search" @click="fetchLocations" 
                            :loading="store.loading" :disabled="isRangeInvalid" />
                </div>
            </div>

            <div class="tables-container">
                <div class="table-half">
                    <DataTable :value="searchResults" paginator :rows="5" class="p-datatable-sm custom-border" emptyMessage="Sin resultados.">
                        <template #header>
                            <div class="flex-between">
                                <span class="font-bold">Resultados ({{ searchResults.length }})</span>
                                <Button label="Añadir Todos" icon="pi pi-angle-double-right" class="p-button-sm p-button-outlined" @click="addAll" :disabled="searchResults.length === 0" />
                            </div>
                        </template>
                        <Column field="complete_name" header="Ubicación Encontrada"></Column>
                        <Column class="action-column">
                            <template #body="slotProps">
                                <Button icon="pi pi-angle-right" class="p-button-rounded p-button-text p-button-info" @click="addLocation(slotProps.data)" />
                            </template>
                        </Column>
                    </DataTable>
                </div>

                <div class="table-half">
                    <DataTable :value="selectedLocations" paginator :rows="5" class="p-datatable-sm custom-border" emptyMessage="Sin selecciones.">
                        <template #header>
                            <div class="flex-between">
                                <span class="font-bold text-primary">Seleccionadas ({{ selectedLocations.length }})</span>
                                <Button label="Quitar Todos" icon="pi pi-trash" class="p-button-sm p-button-outlined p-button-danger" @click="removeAll" :disabled="selectedLocations.length === 0" />
                            </div>
                        </template>
                        <Column class="action-column">
                            <template #body="slotProps">
                                <Button icon="pi pi-times" class="p-button-rounded p-button-text p-button-danger" @click="removeLocation(slotProps.data)" />
                            </template>
                        </Column>
                        <Column field="complete_name" header="Ubicación a Contar"></Column>
                    </DataTable>
                </div>
            </div>

            <div v-if="selectedLocations.length > 0" class="final-action card-background">
                <div class="action-item">
                    <label class="filter-label">Referencia del Conteo</label>
                    <InputText v-model="newCount.ref" placeholder="Ej. Conteo Anual" class="input-full" />
                </div>
                <div class="action-item">
                    <label class="filter-label">Operador Ola 1</label>
                    <Dropdown v-model="newCount.operator_id" :options="operators" optionLabel="name" optionValue="id" placeholder="Asignar a..." class="input-full" />
                </div>
                <div class="action-button-container">
                    <Button label="Generar Conteo" icon="pi pi-check" severity="success" @click="submitNewCount" :loading="store.loading" :disabled="!newCount.ref || !newCount.operator_id" />
                </div>
            </div>
        </div>

        <div v-else>
            <div class="flex-between mb-medium">
                <h2 class="modal-title no-margin">Gestionar Conteo: {{ modalData?.name || 'Desconocido' }}</h2>
                <Button label="Cerrar Conteo" icon="pi pi-lock" severity="danger" class="p-button-sm" @click="closeEntireCount" :loading="store.loading" />
            </div>

            <DataTable :value="waves" class="p-datatable-sm custom-border mb-medium" emptyMessage="Sin olas activas.">
                <template #header><div class="font-bold">Olas Activas/Terminadas</div></template>
                <Column field="name" header="Ola"></Column>
                <Column field="operator_name" header="Operador"></Column>
                <Column field="state_label" header="Estado"></Column>
                <Column header="Acción" style="width: 10rem">
                    <template #body="slotProps">
                        <Button v-if="slotProps.data.state !== 'done'" label="Terminar" icon="pi pi-check" severity="success" class="p-button-sm p-button-text" @click="finishWave(slotProps.data.id)" />
                        <span v-else class="text-green-500 font-bold"><i class="pi pi-check-circle"></i> Lista</span>
                    </template>
                </Column>
            </DataTable>

            <div class="new-wave-form card-background">
                <h4 class="font-bold mb-small">Añadir Nueva Ola</h4>
                <div class="flex-row wrap">
                    <div class="wave-input-box">
                        <label class="small-label">Nombre</label>
                        <InputText v-model="newWave.name" placeholder="Ej. Ola 2" class="input-full" />
                    </div>
                    <div class="wave-input-box">
                        <label class="small-label">Operador</label>
                        <Dropdown v-model="newWave.operator_id" :options="operators" optionLabel="name" optionValue="id" placeholder="Seleccionar" class="input-full" />
                    </div>
                    <div class="wave-button-box">
                        <Button label="Añadir" icon="pi pi-plus" @click="addNewWave" :loading="store.loading" :disabled="!newWave.name || !newWave.operator_id" class="input-full" />
                    </div>
                </div>
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
            filters: { 
                aisle_from: "", aisle_to: "", 
                position_from: 1, position_to: 99,
                level_from: 1, level_to: 5, 
                front_from: 1, front_to: 2 
            },
            searchResults: [], 
            selectedLocations: [], 
            newCount: { ref: "", operator_id: null },
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
            return (f.aisle_from > f.aisle_to) || (f.position_from > f.position_to) ||
                   (f.level_from > f.level_to) || (f.front_from > f.front_to);
        }
    },
    async mounted() {
        await this.fetchOperators();
        if (!this.isCreating && this.modalData.id) await this.fetchWavesForCount();
    },
    methods: {
        async fetchOperators() {
            try {
                let response = await this.store.callOdoo("get_operators", "");
                if (response && response.data) this.operators = response.data;
            } catch (e) { console.error(e); }
        },
        async fetchLocations() {
            try {
                let response = await this.store.callOdoo("get_locations_by_range", "", this.filters);
                if (response?.locations) {
                    this.searchResults = response.locations.filter(l => !this.selectedLocations.some(s => s.id === l.id));
                }
            } catch (e) { this.$toast.add({ severity: 'error', summary: 'Error', detail: 'Error buscando ubicaciones.' }); }
        },
        addLocation(loc) { this.searchResults = this.searchResults.filter(l => l.id !== loc.id); this.selectedLocations.push(loc); },
        addAll() { this.selectedLocations = [...this.selectedLocations, ...this.searchResults]; this.searchResults = []; },
        removeLocation(loc) { this.selectedLocations = this.selectedLocations.filter(l => l.id !== loc.id); this.searchResults.unshift(loc); },
        removeAll() { this.searchResults = [...this.selectedLocations, ...this.searchResults]; this.selectedLocations = []; },
        async submitNewCount() {
            try {
                const payload = { count_ref: this.newCount.ref, operator_id: this.newCount.operator_id, location_ids: this.selectedLocations.map(l => l.id) };
                let response = await this.store.callOdoo("create_initial_cycle_count", "", payload);
                if (response.ok) this.store.closeModal();
            } catch (e) { console.error(e); }
        },
        async fetchWavesForCount() {
            try {
                let response = await this.store.callOdoo("get_waves_for_count", "", { count_id: this.modalData.id });
                if (response?.waves) this.waves = response.waves;
            } catch (e) { console.error(e); }
        },
        async addNewWave() {
            try {
                const payload = { cycle_count_id: this.modalData.id, wave_name: this.newWave.name, operator_id: this.newWave.operator_id };
                let response = await this.store.callOdoo("add_wave_to_count", "", payload);
                if (response.ok) { this.newWave.name = ""; this.newWave.operator_id = null; await this.fetchWavesForCount(); }
            } catch (e) { console.error(e); }
        },
        async finishWave(id) {
            if (!confirm("¿Terminar ola?")) return;
            try {
                let res = await this.store.callOdoo("finish_cycle_count_wave", "", { wave_id: id });
                if (res.ok) await this.fetchWavesForCount();
            } catch (e) { console.error(e); }
        },
        async closeEntireCount() {
            if (!confirm("¿Cerrar conteo?")) return;
            try {
                let res = await this.store.callOdoo("close_cycle_count", "", { count_id: this.modalData.id });
                if (res.ok) this.store.closeModal();
            } catch (e) { console.error(e); }
        }
    }
};
</script>

<style scoped>
/* CONTENEDOR PRINCIPAL */
.cycle-count-modal {
    max-width: 1000px;
    margin: 0 auto;
    font-family: var(--font-family);
}

/* UTILIDADES FLEX */
.flex-row { display: flex; align-items: center; }
.flex-row.wrap { flex-wrap: wrap; }
.flex-between { display: flex; justify-content: space-between; align-items: center; }
.gap-small { gap: 0.5rem; }
.input-full { width: 100%; }
.mb-medium { margin-bottom: 1.5rem; }
.mb-small { margin-bottom: 0.75rem; }
.no-margin { margin: 0; }

/* TÍTULOS */
.modal-title {
    font-size: 1.5rem;
    font-weight: 700;
    margin-bottom: 1.5rem;
}

/* TARJETAS / SECCIONES */
.card-background {
    background-color: #f8f9fa; /* surface-100 */
    padding: 1rem;
    border-radius: 6px;
}

/* SECCIÓN FILTROS: 4 columnas (25% aprox) */
.filter-section {
    display: flex;
    flex-wrap: wrap;
    gap: 1rem;
    margin-bottom: 1.5rem;
}

.filter-group {
    flex: 1 1 calc(25% - 1rem); /* 25% menos el gap */
    min-width: 180px;
}

.filter-label {
    display: block;
    font-weight: 700;
    margin-bottom: 0.5rem;
    font-size: 0.9rem;
}

.filter-actions {
    flex: 1 1 100%;
    display: flex;
    justify-content: flex-end;
    margin-top: 0.5rem;
}

/* CONTENEDOR DE TABLAS: 2 columnas (50% aprox) */
.tables-container {
    display: flex;
    flex-wrap: wrap;
    gap: 1.5rem;
    margin-bottom: 1.5rem;
}

.table-half {
    flex: 1 1 calc(50% - 1.5rem);
    min-width: 350px;
}

.custom-border {
    border: 1px solid #dee2e6;
    border-radius: 6px;
    overflow: hidden;
}

.action-column {
    width: 4rem;
    text-align: center;
}

/* SECCIÓN FINAL */
.final-action {
    display: flex;
    flex-wrap: wrap;
    gap: 1rem;
    align-items: flex-end;
}

.action-item {
    flex: 1 1 calc(40% - 1rem);
    min-width: 250px;
}

.action-button-container {
    flex: 1 1 calc(20% - 1rem);
    display: flex;
    justify-content: flex-end;
}

/* FORMULARIO NUEVA OLA */
.new-wave-form .wave-input-box {
    flex: 1 1 calc(40% - 1rem);
    padding: 0.5rem;
    min-width: 200px;
}

.new-wave-form .wave-button-box {
    flex: 1 1 calc(20% - 1rem);
    padding: 0.5rem;
    min-width: 120px;
}

.small-label {
    font-size: 0.8rem;
    margin-bottom: 0.25rem;
    display: block;
}

/* RESPONSIVO MÓVIL */
@media (max-width: 768px) {
    .filter-group, .table-half, .action-item, .action-button-container, .wave-input-box, .wave-button-box {
        flex: 1 1 100% !important;
    }
}
</style>