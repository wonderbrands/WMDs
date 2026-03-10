<template>
    <div class="cycle-count-modal p-3">
        <div v-if="isCreating">
            <h2 class="mb-4 text-xl font-bold">Crear Nuevo Conteo Cíclico</h2>
            
            <div class="grid mb-4 surface-100 p-3 border-round">
                <div class="col-12 md:col-3">
                    <label class="font-bold block mb-2">Pasillo (A - Z)</label>
                    <div class="flex gap-2">
                        <InputText v-model="filters.aisle_from" placeholder="A" maxlength="1" 
                                   @input="filters.aisle_from = filters.aisle_from.toUpperCase()" class="w-full" />
                        <InputText v-model="filters.aisle_to" placeholder="C" maxlength="1" 
                                   @input="filters.aisle_to = filters.aisle_to.toUpperCase()" class="w-full" />
                    </div>
                </div>

                <div class="col-12 md:col-3">
                    <label class="font-bold block mb-2">Posición (1 - 99)</label>
                    <div class="flex gap-2">
                        <InputNumber v-model="filters.position_from" :min="1" :max="99" placeholder="1" inputClass="w-full" />
                        <InputNumber v-model="filters.position_to" :min="1" :max="99" placeholder="99" inputClass="w-full" />
                    </div>
                </div>

                <div class="col-12 md:col-3">
                    <label class="font-bold block mb-2">Nivel (1 - 5)</label>
                    <div class="flex gap-2">
                        <InputNumber v-model="filters.level_from" :min="1" :max="5" placeholder="1" inputClass="w-full" />
                        <InputNumber v-model="filters.level_to" :min="1" :max="5" placeholder="5" inputClass="w-full" />
                    </div>
                </div>

                <div class="col-12 md:col-3">
                    <label class="font-bold block mb-2">Frente (1 - 2)</label>
                    <div class="flex gap-2">
                        <InputNumber v-model="filters.front_from" :min="1" :max="2" placeholder="1" inputClass="w-full" />
                        <InputNumber v-model="filters.front_to" :min="1" :max="2" placeholder="2" inputClass="w-full" />
                    </div>
                </div>

                <div class="col-12 mt-3 flex justify-content-end">
                    <Button label="Buscar Ubicaciones" icon="pi pi-search" @click="fetchLocations" 
                            :loading="store.loading" :disabled="isRangeInvalid" />
                </div>
            </div>

            <div class="grid mb-4">
                <div class="col-12 md:col-6">
                    <DataTable :value="searchResults" paginator :rows="5" class="p-datatable-sm border-1 surface-border border-round" emptyMessage="Realiza una búsqueda válida para ver ubicaciones.">
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

            <div v-if="selectedLocations.length > 0" class="surface-100 p-3 border-round grid">
                <div class="col-12 md:col-6">
                    <label class="font-bold block mb-2">Referencia del Conteo</label>
                    <InputText v-model="newCount.ref" placeholder="Ej. Conteo Anual" class="w-full" />
                </div>
                <div class="col-12 md:col-6">
                    <label class="font-bold block mb-2">Operador Ola 1</label>
                    <Dropdown v-model="newCount.operator_id" :options="operators" optionLabel="name" optionValue="id" placeholder="Asignar a..." class="w-full" />
                </div>
                <div class="col-12 mt-3 flex justify-content-end">
                    <Button label="Generar Conteo" icon="pi pi-check" severity="success" @click="submitNewCount" :loading="store.loading" :disabled="!newCount.ref || !newCount.operator_id" />
                </div>
            </div>
        </div>

        <div v-else>
            <div class="flex justify-content-between align-items-center mb-4">
                <h2 class="text-xl font-bold">Gestionar Conteo: {{ modalData?.name || modalData?.id || 'Desconocido' }}</h2>
                <Button label="Cerrar Conteo Definitivamente" icon="pi pi-lock" severity="danger" class="p-button-sm" @click="closeEntireCount" :loading="store.loading" />
            </div>

            <DataTable :value="waves" class="p-datatable-sm mb-4" emptyMessage="Cargando olas o sin olas activas...">
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

            <div class="surface-100 p-3 border-round mt-4">
                <h4 class="mb-3 font-bold">Añadir Nueva Ola a este Conteo</h4>
                <div class="grid">
                    <div class="col-12 md:col-5">
                        <label class="block mb-2 text-sm">Nombre de la Ola</label>
                        <InputText v-model="newWave.name" placeholder="Ej. Ola 2 - Re-conteo" class="w-full" />
                    </div>
                    <div class="col-12 md:col-5">
                        <label class="block mb-2 text-sm">Asignar Operador</label>
                        <Dropdown v-model="newWave.operator_id" :options="operators" optionLabel="name" optionValue="id" placeholder="Seleccionar" class="w-full" />
                    </div>
                    <div class="col-12 md:col-2 flex align-items-end">
                        <Button label="Añadir" icon="pi pi-plus" @click="addNewWave" :loading="store.loading" :disabled="!newWave.name || !newWave.operator_id" class="w-full" />
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
            
            // Estado para Creación
            filters: { 
                aisle_from: "", aisle_to: "", 
                position_from: 1, position_to: 99,
                level_from: 1, level_to: 5, 
                front_from: 1, front_to: 2 
            },
            searchResults: [], 
            selectedLocations: [], 
            newCount: { ref: "", operator_id: null },

            // Estado para Edición
            waves: [],
            newWave: { name: "", operator_id: null }
        };
    },
    
    computed: {
        modalData() {
            return this.store.form_context?.data || {};
        },
        isCreating() {
            return !!this.modalData.cycle_count || this.modalData.form_type === 'new';
        },
        // Bloquea el botón si algún rango es inválido o los pasillos están vacíos
        isRangeInvalid() {
            const f = this.filters;
            if (!f.aisle_from || !f.aisle_to) return true;
            
            return (f.aisle_from > f.aisle_to) || 
                   (f.position_from > f.position_to) ||
                   (f.level_from > f.level_to) || 
                   (f.front_from > f.front_to);
        }
    },

    async mounted() {
        await this.fetchOperators();
        if (!this.isCreating && this.modalData.id) {
            await this.fetchWavesForCount();
        }
    },

    methods: {
        async fetchOperators() {
            try {
                let response = await this.store.callOdoo("get_operators", "");
                if (response && response.data) this.operators = response.data;
            } catch (error) { 
                this.$toast.add({ severity: 'error', summary: 'Error', detail: 'No se pudieron cargar los operadores.', life: 3000 });
                console.error("Error cargando operadores", error); 
            }
        },

        async fetchLocations() {
            const f = this.filters;

            // 1. Validar Pasillos
            if (!f.aisle_from || !f.aisle_to) {
                this.$toast.add({ severity: 'warn', summary: 'Campos incompletos', detail: 'Debe ingresar el rango de pasillos.', life: 3000 });
                return;
            }
            if (f.aisle_from > f.aisle_to) {
                this.$toast.add({ severity: 'error', summary: 'Rango Inválido', detail: `El pasillo ${f.aisle_from} no puede ser posterior a ${f.aisle_to}.`, life: 4000 });
                return;
            }

            if (f.position_from > f.position_to) {
                this.$toast.add({ severity: 'error', summary: 'Rango Inválido', detail: 'La posición inicial debe ser menor o igual a la final.', life: 3000 });
                return;
            }
            if (f.level_from > f.level_to) {
                this.$toast.add({ severity: 'error', summary: 'Rango Inválido', detail: 'El nivel inicial debe ser menor o igual al final.', life: 3000 });
                return;
            }
            if (f.front_from > f.front_to) {
                this.$toast.add({ severity: 'error', summary: 'Rango Inválido', detail: 'El frente inicial debe ser menor o igual al final.', life: 3000 });
                return;
            }

            try {
                let response = await this.store.callOdoo("get_locations_by_range", "", this.filters);
                if (response && response.locations) {
                    this.searchResults = response.locations.filter(
                        resLoc => !this.selectedLocations.some(selLoc => selLoc.id === resLoc.id)
                    );
                }
            } catch (e) {
                this.$toast.add({ severity: 'error', summary: 'Error', detail: 'Error buscando ubicaciones.', life: 3000 });
                console.error("Error buscando ubicaciones:", e);
            } 
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
            this.searchResults.unshift(location); 
        },

        removeAll() {
            this.searchResults = [...this.selectedLocations, ...this.searchResults];
            this.selectedLocations = [];
        },

        async submitNewCount() {
            try {
                const payload = {
                    count_ref: this.newCount.ref,
                    operator_id: this.newCount.operator_id,
                    location_ids: this.selectedLocations.map(loc => loc.id)
                };
                let response = await this.store.callOdoo("create_initial_cycle_count", "", payload);
                if (response.ok) {
                    this.store.closeModal(); 
                } else {
                    this.$toast.add({ severity: 'error', summary: 'Error', detail: response.error, life: 3000 });
                }
            } catch (e) {
                this.$toast.add({ severity: 'error', summary: 'Error', detail: 'No se pudo crear el conteo cíclico.', life: 3000 });
                console.error(e);
            } 
        },

        /* --- MÉTODOS DE EDICIÓN --- */
        async fetchWavesForCount() {
            if (!this.modalData.id) return;
            try {
                let response = await this.store.callOdoo("get_waves_for_count", "", { count_id: this.modalData.id });
                if (response && response.waves) {
                    this.waves = response.waves;
                }
            } catch (e) {
                this.$toast.add({ severity: 'error', summary: 'Error', detail: 'No se pudieron obtener las olas.', life: 3000 });
                console.error("Error obteniendo olas", e);
            }
        },

        async addNewWave() {
            try {
                const payload = {
                    cycle_count_id: this.modalData.id,
                    wave_name: this.newWave.name,
                    operator_id: this.newWave.operator_id
                };
                let response = await this.store.callOdoo("add_wave_to_count", "", payload);
                if (response.ok) {
                    this.newWave.name = "";
                    this.newWave.operator_id = null;
                    await this.fetchWavesForCount(); 
                } else {
                    this.$toast.add({ severity: 'error', summary: 'Error', detail: response.error, life: 3000 });
                }
            } catch (e) {
                this.$toast.add({ severity: 'error', summary: 'Error', detail: 'No se pudo agregar la nueva ola.', life: 3000 });
                console.error(e);
            }
        },

        async finishWave(waveId) {
            if (!confirm("¿Terminar esta ola?")) return;
            try {
                let response = await this.store.callOdoo("finish_cycle_count_wave", "", { wave_id: waveId });
                if (response.ok) await this.fetchWavesForCount();
                else {
                    this.$toast.add({ severity: 'error', summary: 'Error', detail: response.error, life: 3000 });
                }
            } catch (e) {
                this.$toast.add({ severity: 'error', summary: 'Error', detail: 'No se pudo finalizar la ola.', life: 3000 });
                console.error(e);
            }
        },

        async closeEntireCount() {
            if (!confirm("Al cerrar el conteo, ninguna ola podrá ser modificada. ¿Estás seguro?")) return;
            try {
                let response = await this.store.callOdoo("close_cycle_count", "", { count_id: this.modalData.id });
                if (response.ok) {
                    this.store.closeModal();
                } else {
                    this.$toast.add({ severity: 'error', summary: 'Error', detail: response.error, life: 3000 });
                }
            } catch (e) {
                this.$toast.add({ severity: 'error', summary: 'Error', detail: 'No se pudo cerrar el conteo.', life: 3000 });
                console.error(e);
            }
        }
    }
};
</script>

<style scoped>
.cycle-count-modal {
    max-width: 1000px;
    margin: 0 auto;
}
</style>