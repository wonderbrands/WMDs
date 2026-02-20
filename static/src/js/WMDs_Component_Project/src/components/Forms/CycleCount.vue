<template>
    <div class="cycle-count-modal p-3">
        <div v-if="isCreating">
            <h2 class="mb-4 text-xl font-bold">Crear Nuevo Conteo Cíclico</h2>
            
            <div class="grid p-fluid align-items-end mb-4 surface-100 p-3 border-round">
                <div class="col-12 md:col-3">
                    <label class="font-bold block mb-2">Pasillo (Del - Al)</label>
                    <div class="flex gap-2">
                        <InputText v-model="filters.aisle_from" placeholder="A" />
                        <InputText v-model="filters.aisle_to" placeholder="C" />
                    </div>
                </div>
                <div class="col-12 md:col-3">
                    <label class="font-bold block mb-2">Nivel (Del - Al)</label>
                    <div class="flex gap-2">
                        <InputText v-model="filters.level_from" placeholder="1" />
                        <InputText v-model="filters.level_to" placeholder="3" />
                    </div>
                </div>
                <div class="col-12 md:col-3">
                    <label class="font-bold block mb-2">Frente (Del - Al)</label>
                    <div class="flex gap-2">
                        <InputText v-model="filters.front_from" placeholder="01" />
                        <InputText v-model="filters.front_to" placeholder="10" />
                    </div>
                </div>
                <div class="col-12 md:col-3">
                    <Button label="Buscar Ubicaciones" icon="pi pi-search" @click="fetchLocations" :loading="store.loading" />
                </div>
            </div>

            <div class="grid mb-4">
                <div class="col-12 md:col-6">
                    <DataTable :value="searchResults" paginator :rows="5" class="p-datatable-sm border-1 surface-border border-round" emptyMessage="Realiza una búsqueda para ver ubicaciones.">
                        <template #header>
                            <div class="flex justify-content-between align-items-center">
                                <span class="font-bold">Resultados ({{ searchResults.length }})</span>
                                <Button label="Añadir Todos" icon="pi pi-angle-double-right" class="p-button-sm p-button-outlined" @click="addAll" :disabled="searchResults.length === 0" />
                            </div>
                        </template>
                        <Column field="complete_name" header="Ubicación Encontrada"></Column>
                        <Column style="width: 4rem; text-align: center;">
                            <template #body="slotProps">
                                <Button icon="pi pi-angle-right" class="p-button-rounded p-button-text p-button-info" @click="addLocation(slotProps.data)" title="Añadir a la selección" />
                            </template>
                        </Column>
                    </DataTable>
                </div>

                <div class="col-12 md:col-6">
                    <DataTable :value="selectedLocations" paginator :rows="5" class="p-datatable-sm border-1 surface-border border-round" emptyMessage="Aún no has seleccionado ubicaciones.">
                        <template #header>
                            <div class="flex justify-content-between align-items-center">
                                <span class="font-bold text-primary">Seleccionadas ({{ selectedLocations.length }})</span>
                                <Button label="Quitar Todos" icon="pi pi-trash" class="p-button-sm p-button-outlined p-button-danger" @click="removeAll" :disabled="selectedLocations.length === 0" />
                            </div>
                        </template>
                        <Column style="width: 4rem; text-align: center;">
                            <template #body="slotProps">
                                <Button icon="pi pi-times" class="p-button-rounded p-button-text p-button-danger" @click="removeLocation(slotProps.data)" title="Quitar de la selección" />
                            </template>
                        </Column>
                        <Column field="complete_name" header="Ubicación a Contar"></Column>
                    </DataTable>
                </div>
            </div>

            <div class="grid p-fluid align-items-end" v-if="selectedLocations.length > 0">
                <div class="col-12 md:col-5">
                    <label class="font-bold block mb-2">Referencia del Conteo</label>
                    <InputText v-model="newCount.ref" placeholder="Ej. Conteo Anual" />
                </div>
                <div class="col-12 md:col-5">
                    <label class="font-bold block mb-2">Operador Ola 1</label>
                    <Dropdown v-model="newCount.operator_id" :options="operators" optionLabel="name" optionValue="id" placeholder="Asignar a..." />
                </div>
                <div class="col-12 md:col-2">
                    <Button label="Generar" icon="pi pi-check" severity="success" @click="submitNewCount" :loading="store.loading" :disabled="!newCount.ref || !newCount.operator_id" />
                </div>
            </div>
        </div>

        <div v-else>
            <div class="flex justify-content-between align-items-center mb-4">
                <h2 class="text-xl font-bold">Gestionar Conteo: {{ modalData.name || modalData.id }}</h2>
                <Button label="Cerrar Conteo Definitivamente" icon="pi pi-lock" severity="danger" class="p-button-sm" @click="closeEntireCount" :loading="store.loading" />
            </div>

            <DataTable :value="waves" class="p-datatable-sm mb-4" emptyMessage="Cargando olas...">
                <template #header>
                    <div class="font-bold">Olas Activas/Terminadas</div>
                </template>
                <Column field="name" header="Ola"></Column>
                <Column field="operator_name" header="Operador"></Column>
                <Column field="state_label" header="Estado"></Column>
                <Column header="Acción" style="width: 10rem">
                    <template #body="slotProps">
                        <Button v-if="slotProps.data.state !== 'done'" label="Terminar Ola" icon="pi pi-check" severity="success" class="p-button-sm p-button-text" @click="finishWave(slotProps.data.id)" />
                        <span v-else class="text-green-500 font-bold"><i class="pi pi-check-circle"></i> Lista</span>
                    </template>
                </Column>
            </DataTable>

            <div class="surface-100 p-3 border-round">
                <h4 class="mb-3 font-bold">Añadir Nueva Ola a este Conteo</h4>
                <div class="grid p-fluid align-items-end">
                    <div class="col-12 md:col-5">
                        <label class="block mb-2">Nombre de la Ola</label>
                        <InputText v-model="newWave.name" placeholder="Ej. Ola 2 - Re-conteo" />
                    </div>
                    <div class="col-12 md:col-5">
                        <label class="block mb-2">Asignar Operador</label>
                        <Dropdown v-model="newWave.operator_id" :options="operators" optionLabel="name" optionValue="id" placeholder="Seleccionar" />
                    </div>
                    <div class="col-12 md:col-2">
                        <Button label="Añadir Ola" icon="pi pi-plus" @click="addNewWave" :loading="store.loading" :disabled="!newWave.name || !newWave.operator_id" />
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>

<script>
import { useGeneralStore } from "../../store/index";
import InputText from "primevue/inputtext";
import Button from "primevue/button";
import DataTable from "primevue/datatable";
import Column from "primevue/column";
import Dropdown from "primevue/dropdown";

export default {
    name: "CycleCountModal",
    components: { InputText, Button, DataTable, Column, Dropdown },
    props: {
        modalData: {
            type: Object,
            required: true
        }
    },
    data() {
        return {
            store: useGeneralStore(),
            operators: [],
            
            filters: { aisle_from: "", aisle_to: "", level_from: "", level_to: "", front_from: "", front_to: "" },
            searchResults: [], 
            selectedLocations: [], 
            newCount: { ref: "", operator_id: null },

            waves: [],
            newWave: { name: "", operator_id: null }
        };
    },
    computed: {
        isCreating() {
            return !!this.modalData?.cycle_count || this.modalData?.form_type === 'new';
        }
    },
    async mounted() {
        await this.fetchOperators();
        
        if (!this.isCreating) {
            await this.fetchWavesForCount();
        }
    },
    methods: {
        async fetchOperators() {
            try {
                let response = await this.store.odoo_middleware.getFromOdoo("get_operators", "");
                if (response && response.data) this.operators = response.data;
            } catch (error) { console.error("Error cargando operadores", error); }
        },

        async fetchLocations() {
            this.store.loading = true;
            try {
                let response = await this.store.odoo_middleware.getFromOdoo("get_locations_by_range", "", this.filters);
                if (response && response.locations) {
                    this.searchResults = response.locations.filter(
                        resLoc => !this.selectedLocations.some(selLoc => selLoc.id === resLoc.id)
                    );
                }
            } catch (e) { alert("Error buscando ubicaciones"); } 
            finally { this.store.loading = false; }
        },

        addLocation(location) {
            this.searchResults = this.searchResults.filter(loc => loc.id !== location.id);
            this.selectedLocations.push(location);
        },

        addAll() {
            this.selectedLocations = [...this.selectedLocations, ...this.searchResults];
            this.searchResults = [];
        },

        removeLocation(location) {
            this.selectedLocations = this.selectedLocations.filter(loc => loc.id !== location.id);
            this.searchResults.unshift(location); // La regresamos arriba en los resultados
        },

        removeAll() {
            this.searchResults = [...this.selectedLocations, ...this.searchResults];
            this.selectedLocations = [];
        },

        async submitNewCount() {
            this.store.loading = true;
            try {
                const payload = {
                    count_ref: this.newCount.ref,
                    operator_id: this.newCount.operator_id,
                    location_ids: this.selectedLocations.map(loc => loc.id)
                };
                let response = await this.store.odoo_middleware.getFromOdoo("create_initial_cycle_count", "", payload);
                if (response.ok) {
                    this.store.closeModal(); 
                } else { alert(response.error); }
            } catch (e) { console.error(e); } 
            finally { this.store.loading = false; }
        },

        async fetchWavesForCount() {
            this.store.loading = true;
            try {
                let response = await this.store.odoo_middleware.getFromOdoo("get_waves_for_count", "", { count_id: this.modalData.id });
                if (response && response.waves) {
                    this.waves = response.waves;
                }
            } catch (e) { console.error("Error obteniendo olas", e); }
            finally { this.store.loading = false; }
        },
        async addNewWave() {
            this.store.loading = true;
            try {
                const payload = {
                    cycle_count_id: this.modalData.id,
                    wave_name: this.newWave.name,
                    operator_id: this.newWave.operator_id
                };
                let response = await this.store.odoo_middleware.getFromOdoo("add_wave_to_count", "", payload);
                if (response.ok) {
                    this.newWave.name = "";
                    this.newWave.operator_id = null;
                    await this.fetchWavesForCount(); 
                } else { alert(response.error); }
            } catch (e) { console.error(e); }
            finally { this.store.loading = false; }
        },
        async finishWave(waveId) {
            if (!confirm("¿Terminar esta ola?")) return;
            this.store.loading = true;
            try {
                let response = await this.store.odoo_middleware.getFromOdoo("finish_cycle_count_wave", "", { wave_id: waveId });
                if (response.ok) await this.fetchWavesForCount();
                else alert(response.error);
            } catch (e) { console.error(e); }
            finally { this.store.loading = false; }
        },
        async closeEntireCount() {
            if (!confirm("Al cerrar el conteo, ninguna ola podrá ser modificada. ¿Estás seguro?")) return;
            this.store.loading = true;
            try {
                let response = await this.store.odoo_middleware.getFromOdoo("close_cycle_count", "", { count_id: this.modalData.id });
                if (response.ok) {
                    this.store.closeModal();
                } else { alert(response.error); }
            } catch (e) { console.error(e); }
            finally { this.store.loading = false; }
        }
    }
};
</script>