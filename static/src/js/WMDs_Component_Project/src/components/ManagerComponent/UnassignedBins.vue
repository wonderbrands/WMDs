<template>
    <div class="unassigned-bins-container">
        <div class="header flex justify-content-between align-items-center mb-4">
            <div>
                <h2 class="m-0 text-xl font-bold"><i class="fa fa-exclamation-triangle text-orange-500 mr-2"></i> Lotes y Traslados sin BIN</h2>
                <p class="m-0 text-gray-500 text-sm mt-1">Órdenes finalizadas que no fueron asignadas a un BIN (ej. al salir de la app durante el proceso).</p>
            </div>
            <div class="flex gap-2">
                <Button icon="fa fa-refresh" severity="secondary" rounded text @click="fetchRecords" :loading="loading" title="Actualizar" />
            </div>
        </div>

        <div v-if="loading && records.length === 0" class="flex justify-content-center p-5">
            <i class="fa fa-spinner fa-spin fa-2x text-primary"></i>
        </div>

        <div v-else-if="records.length === 0" class="empty-state p-5 text-center bg-white border-round border-1 border-gray-200">
            <i class="fa fa-check-circle text-green-500 text-4xl mb-3"></i>
            <h3 class="m-0 text-lg font-bold">¡Todo al día!</h3>
            <p class="m-0 text-gray-500 mt-1">No hay lotes ni traslados terminados pendientes de ingresar a BIN.</p>
        </div>

        <div v-else class="card bg-white border-round border-1 border-gray-200 shadow-1 p-3">
            <DataTable :value="records" responsiveLayout="scroll" :paginator="true" :rows="15" stripedRows class="p-datatable-sm">
                <Column field="type" header="Tipo" style="width: 110px;">
                    <template #body="slotProps">
                        <Tag 
                            :value="slotProps.data.type === 'batch' ? 'Lote (Batch)' : 'Traslado'" 
                            :severity="slotProps.data.type === 'batch' ? 'info' : 'warning'" 
                        />
                    </template>
                </Column>

                <Column field="name" header="Identificador" style="width: 160px; font-weight: bold;">
                    <template #body="slotProps">
                        <span>{{ slotProps.data.name }}</span>
                    </template>
                </Column>

                <Column field="origin" header="Documento Origen" style="width: 180px;">
                    <template #body="slotProps">
                        <span class="origin-badge" v-if="slotProps.data.origin && slotProps.data.origin !== 'N/A'">
                            <i class="fa fa-tag text-xs mr-1"></i> {{ slotProps.data.origin }}
                        </span>
                        <span v-else class="text-gray-400 italic">Sin origen</span>
                    </template>
                </Column>

                <Column field="total_items" header="Pzas / Paquetes" style="width: 130px;" class="text-center">
                    <template #body="slotProps">
                        <Badge :value="slotProps.data.total_items" severity="secondary" />
                    </template>
                </Column>

                <Column field="picking_count" header="Traslados" style="width: 100px;" class="text-center">
                    <template #body="slotProps">
                        <span>{{ slotProps.data.picking_count }}</span>
                    </template>
                </Column>

                <Column field="date" header="Fecha Terminado" style="width: 160px;">
                    <template #body="slotProps">
                        <span class="text-sm text-gray-600">{{ slotProps.data.date }}</span>
                    </template>
                </Column>

                <Column header="Acción" style="width: 160px;" class="text-right">
                    <template #body="slotProps">
                        <Button 
                            label="Asignar a BIN" 
                            icon="fa fa-archive" 
                            severity="primary" 
                            size="small" 
                            @click="openAssignDialog(slotProps.data)" 
                        />
                    </template>
                </Column>
            </DataTable>
        </div>

        <!-- DIALOGO ASIGNACIÓN A BIN -->
        <Dialog 
            v-model:visible="showAssignDialog" 
            modal 
            :header="`Asignar a BIN: ${selectedRecord?.name || ''}`" 
            :style="{ width: '450px' }"
        >
            <div class="p-fluid">
                <div class="mb-3">
                    <label class="block font-semibold mb-1">Documento Origen:</label>
                    <div class="p-2 bg-gray-100 border-round font-bold text-primary">
                        {{ selectedRecord?.origin || 'Sin origen' }}
                    </div>
                </div>

                <div class="mb-3">
                    <label class="block font-semibold mb-1">Seleccionar BIN de Destino:</label>
                    <Dropdown 
                        v-model="targetBin" 
                        :options="availableBins" 
                        optionLabel="name" 
                        optionValue="name" 
                        placeholder="Selecciona un BIN disponible" 
                        :filter="true" 
                        class="w-full mb-2"
                    />
                    <small class="text-gray-500">O escribe el nombre exacto del BIN:</small>
                    <InputText v-model="targetBin" placeholder="Ej: BIN-01" class="w-full mt-1" />
                </div>
            </div>

            <template #footer>
                <Button label="Cancelar" icon="fa fa-times" text severity="secondary" @click="showAssignDialog = false" />
                <Button 
                    label="Confirmar Asignación" 
                    icon="fa fa-check" 
                    severity="success" 
                    @click="confirmAssignBin" 
                    :loading="assigning" 
                    :disabled="!targetBin" 
                />
            </template>
        </Dialog>
    </div>
</template>

<script>
import DataTable from 'primevue/datatable';
import Column from 'primevue/column';
import Tag from 'primevue/tag';
import Badge from 'primevue/badge';
import Button from 'primevue/button';
import Dialog from 'primevue/dialog';
import Dropdown from 'primevue/dropdown';
import InputText from 'primevue/inputtext';
import { useGeneralStore } from "../../store/index";

export default {
    name: 'UnassignedBins',
    components: {
        DataTable,
        Column,
        Tag,
        Badge,
        Button,
        Dialog,
        Dropdown,
        InputText
    },
    data() {
        return {
            store: useGeneralStore(),
            loading: false,
            records: [],
            showAssignDialog: false,
            selectedRecord: null,
            targetBin: '',
            availableBins: [],
            assigning: false
        };
    },
    mounted() {
        this.fetchRecords();
        this.fetchAvailableBins();
    },
    methods: {
        async fetchRecords() {
            this.loading = true;
            try {
                const res = await this.store.callOdoo("get_unassigned_ful_records", "", {});
                if (res && res.ok) {
                    this.records = res.records || [];
                } else {
                    this.records = [];
                    if (res && res.error) {
                        this.$toast.add({ severity: 'error', summary: 'Error', detail: res.error, life: 4000 });
                    }
                }
            } catch (e) {
                console.error("Error fetching unassigned ful records:", e);
                this.$toast.add({ severity: 'error', summary: 'Error', detail: 'No se pudieron consultar los registros sin BIN.', life: 4000 });
            } finally {
                this.loading = false;
            }
        },

        async fetchAvailableBins() {
            try {
                const bins = await this.store.callOdoo("get_available_bins", "", {});
                if (Array.isArray(bins)) {
                    this.availableBins = bins;
                }
            } catch (e) {
                console.error("Error fetching available bins:", e);
            }
        },

        openAssignDialog(record) {
            this.selectedRecord = record;
            this.targetBin = '';
            this.showAssignDialog = true;
        },

        async confirmAssignBin() {
            if (!this.targetBin || !this.selectedRecord) return;

            this.assigning = true;
            try {
                const params = {
                    bin: this.targetBin.trim(),
                    operator: this.store.role?.email || 'manager'
                };

                if (this.selectedRecord.type === 'batch') {
                    params.batch_id = this.selectedRecord.id;
                } else {
                    params.pick_id = this.selectedRecord.id;
                }

                const res = await this.store.callOdoo("move_to_bin", "", params);

                if (res && res.error) {
                    this.$toast.add({ 
                        severity: 'error', 
                        summary: 'Error al mover a BIN', 
                        detail: res.error, 
                        life: 6000 
                    });
                } else if (res && (res.ok || res.status === 'queued')) {
                    this.$toast.add({ 
                        severity: 'success', 
                        summary: 'Asignado a BIN', 
                        detail: `${this.selectedRecord.name} movido exitosamente al BIN ${this.targetBin}.`, 
                        life: 4000 
                    });
                    this.showAssignDialog = false;
                    await this.fetchRecords();
                } else {
                    this.$toast.add({ 
                        severity: 'warn', 
                        summary: 'Respuesta inesperada', 
                        detail: res?.message || 'Verifique el estado del BIN.', 
                        life: 4000 
                    });
                }
            } catch (e) {
                console.error("Error in confirmAssignBin:", e);
                this.$toast.add({ 
                    severity: 'error', 
                    summary: 'Error', 
                    detail: e.message || 'Error de comunicación al asignar BIN.', 
                    life: 5000 
                });
            } finally {
                this.assigning = false;
            }
        }
    }
};
</script>

<style scoped>
.unassigned-bins-container {
    padding: 1.5rem;
    max-width: 1200px;
    margin: 0 auto;
}

.origin-badge {
    background: #eef2ff;
    color: #4338ca;
    padding: 3px 8px;
    border-radius: 4px;
    font-weight: 600;
    font-size: 0.85rem;
    border: 1px solid #c7d2fe;
    display: inline-block;
}
</style>
