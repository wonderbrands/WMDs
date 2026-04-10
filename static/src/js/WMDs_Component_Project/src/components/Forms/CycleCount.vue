<template>
    <div class="cycle-count-wrapper">
        <div class="cycle-count-modal">
            <div v-if="isCreating">
                <h2 class="modal-title">Nuevo Conteo Cíclico</h2>
                <div class="wizard-stepper">
                    <div :class="['step-pill', { active: currentStep === 1 }]">1. Selección</div>
                    <div :class="['step-pill', { active: currentStep === 2 }]">2. Asignación</div>
                </div>

                <div v-if="currentStep === 1" class="fade-in">
                    <div class="filter-section card-background">
                        <div class="filter-group">
                            <label class="filter-label">Pasillo (A - ZZ)</label>
                            <div class="flex-row gap-small">
                                <InputText v-model="filters.aisle_from" maxlength="2" @input="filters.aisle_from = filters.aisle_from.toUpperCase()" class="input-full" />
                                <InputText v-model="filters.aisle_to" maxlength="2" @input="filters.aisle_to = filters.aisle_to.toUpperCase()" class="input-full" />
                            </div>
                        </div>
                        <div class="filter-group">
                            <label class="filter-label">Posición (1 - 99)</label>
                            <div class="flex-row gap-small">
                                <InputNumber v-model="filters.position_from" :min="1" :max="99" inputClass="input-full" />
                                <InputNumber v-model="filters.position_to" :min="1" :max="99" inputClass="input-full" />
                            </div>
                        </div>
                        <div class="filter-group">
                            <label class="filter-label">Nivel (1 - 5)</label>
                            <div class="flex-row gap-small">
                                <InputNumber v-model="filters.level_from" :min="1" :max="5" inputClass="input-full" />
                                <InputNumber v-model="filters.level_to" :min="1" :max="5" inputClass="input-full" />
                            </div>
                        </div>
                        <div class="filter-group">
                            <label class="filter-label">Frente (1 - 2)</label>
                            <div class="flex-row gap-small">
                                <InputNumber v-model="filters.front_from" :min="1" :max="2" inputClass="input-full" />
                                <InputNumber v-model="filters.front_to" :min="1" :max="2" inputClass="input-full" />
                            </div>
                        </div>
                        <div class="filter-actions">
                            <Button label="Buscar" icon="fa fa-search" @click="fetchLocations" :loading="store.loading" :disabled="isRangeInvalid" />
                        </div>
                    </div>

                    <div class="tables-container">
                        <div class="table-half">
                            <div class="search-bar-container mb-small">
                                <span class="p-input-icon-left input-full">
                                    <i class="fa fa-search"></i>
                                    <InputText v-model="rawSearchQueryResults" placeholder="Filtrar resultados..." class="input-full p-inputtext-sm" />
                                </span>
                            </div>
                            <DataTable v-model:selection="tempSelection" :value="filteredSearchResults" paginator :rows="5" class="p-datatable-sm custom-border" :rowClass="rowClass" dataKey="id">
                                <template #header>
                                    <div class="flex-between">
                                        <span class="font-bold">Resultados ({{ filteredSearchResults.length }})</span>
                                        <Button label="Añadir" icon="fa fa-plus" class="p-button-sm p-button-success" @click="addSelected" :disabled="!tempSelection.length" />
                                    </div>
                                </template>
                                <Column selectionMode="multiple" headerStyle="width: 3rem" :selectable="isSelectable"></Column>
                                <Column field="complete_name" header="Ubicación Encontrada">
                                    <template #body="slotProps">
                                        <div class="flex align-items-center gap-2">
                                            <span>{{ slotProps.data.complete_name }}</span>
                                            <i v-if="slotProps.data.has_reservation" 
                                               class="fa fa-info-circle text-blue-500" 
                                               :title="'Reservado por: ' + slotProps.data.reservation_info">
                                            </i>
                                        </div>
                                    </template>
                                </Column>
                            </DataTable>
                        </div>
                        <div class="table-half">
                            <div class="search-bar-container mb-small">
                                <span class="p-input-icon-left input-full">
                                    <i class="fa fa-search"></i>
                                    <InputText v-model="rawSearchQuerySelected" placeholder="Filtrar seleccionadas..." class="input-full p-inputtext-sm" />
                                </span>
                            </div>
                            <DataTable v-model:selection="finalSelection" :value="filteredSelectedLocations" paginator :rows="5" class="p-datatable-sm custom-border" dataKey="id">
                                <template #header>
                                    <div class="flex-between">
                                        <span class="font-bold text-primary">Seleccionadas ({{ filteredSelectedLocations.length }})</span>
                                        <Button label="Quitar" icon="fa fa-trash" class="p-button-sm p-button-danger p-button-outlined" @click="removeSelected" :disabled="!finalSelection.length" />
                                    </div>
                                </template>
                                <Column selectionMode="multiple" headerStyle="width: 3rem"></Column>
                                <Column field="complete_name" header="Ubicación"></Column>
                            </DataTable>
                        </div>
                    </div>
                    <div class="wizard-footer">
                        <Button label="Siguiente" icon="fa fa-arrow-right" iconPos="right" @click="currentStep = 2" :disabled="!selectedLocations.length" />
                    </div>
                </div>

                <div v-if="currentStep === 2" class="fade-in">
                    <div class="card-background mb-medium">
                        <div class="flex-between">
                            <Button label="Volver" icon="fa fa-arrow-left" class="p-button-text" @click="currentStep = 1" />
                            <div class="ref-container">
                                <label class="filter-label">Referencia / Notas</label>
                                <InputText v-model="newCount.ref" placeholder="Ej: Auditoría Pasillo A" class="input-ref" />
                            </div>
                            <Button v-if="assignedOperators.length === 0" label="Añadir Ola" icon="fa fa-user-plus" class="p-button-outlined" @click="addOperatorField" />
                        </div>
                    </div>

                    <div class="operators-grid">
                        <div v-for="(op, index) in assignedOperators" :key="op.id" class="operator-card card-background">
                            <div class="flex-between mb-small">
                                <span class="wave-number">Ola Única</span>
                                <Button icon="fa fa-times"  severity="danger" @click="removeOperatorField(index)" label="X" />
                            </div>
                            <label class="small-label">Responsable</label>
                            <Dropdown v-model="op.operator_id" :options="optionsCache['operadores']" optionLabel="name" optionValue="id" placeholder="Seleccionar..." class="input-full" filter />
                        </div>
                    </div>

                    <div class="final-footer mt-large">
                        <Button label="GENERAR CONTEO" icon="fa fa-save" severity="success" size="large" @click="saveFullCount" :loading="store.loading" :disabled="isSaveDisabled" />
                    </div>
                </div>
            </div>

            <div v-else class="fade-in">
                <div v-if="!detailView">
                    <div class="flex-between mb-medium">
                        <div>
                            <h2 class="modal-title no-margin">{{ modalData?.name }}</h2>
                            <p v-if="cycleCountNotes" class="no-margin text-secondary"><strong>Referencia:</strong> {{ cycleCountNotes }}</p>
                            <span class="sub-title">Creado por: {{ created_by }}</span>
                        </div>
                        <div v-if="cycleCountState !== 'finalized' && cycleCountState !== 'cancelled'">
                            <Button label="Ver Logs" icon="fa fa-list" severity="secondary" class="mr-2" @click="showLogsReport" />
                            <Button label="Comparar Conteos" icon="fa fa-bar-chart" severity="help" class="mr-2" @click="showComparisonReport" />
                            <Button v-if="!hasActiveWave" label="Añadir Ola" icon="fa fa-plus" class="p-button-outlined mr-2" @click="showOperatorDialog('add')" />
                            <!-- "Finalizar Ciclo" button removed as per request -->
                            <Button label="Cancelar Ciclo" icon="fa fa-ban" severity="danger" class="p-button-outlined" @click="cancelEntireCount" :loading="store.loading" />
                        </div>
                        <div v-else class="flex-row">
                             <Button label="Ver Logs" icon="fa fa-list" severity="secondary" class="mr-2" @click="showLogsReport" />
                             <span :class="['state-badge', cycleCountState]">
                                {{ cycleCountState === 'finalized' ? 'FINALIZADO' : 'CANCELADO' }}
                             </span>
                        </div>
                    </div>

                    <div class="mb-medium">
                        <h4 class="small-label">Ubicaciones Planificadas ({{ selectedLocations.length }})</h4>
                        <DataTable :value="selectedLocations" paginator :rows="3" class="p-datatable-sm custom-border">
                            <Column field="complete_name" header="Ubicación"></Column>
                        </DataTable>
                    </div>

                    <DataTable :value="waves" class="p-datatable-sm custom-border mb-medium" @row-click="showWaveDetails" selectionMode="single">
                         <template #header>
                            <h4 class="small-label no-margin">Olas de Conteo ({{ waves.length }}) - <small>Click para ver detalle</small></h4>
                        </template>
                        <Column field="name" header="Ola"></Column>
                        <Column field="operator_name" header="Operador"></Column>
                        <Column field="state_label" header="Estado"></Column>
                        <Column header="Acciones" style="width: 25rem">
                            <template #body="slotProps">
                                <div v-if="cycleCountState !== 'finalized' && cycleCountState !== 'cancelled' && slotProps.data.state !== 'done' && slotProps.data.state !== 'cancelled'">
                                    <Button label="Reasignar" icon="fa fa-user" class="p-button-text text-orange-500" @click.stop="showOperatorDialog('reassign', slotProps.data)" />
                                    <Button label="Finalizar" icon="fa fa-check" severity="success" class="p-button-text" @click.stop="finishWave(slotProps.data.id)" />
                                    <Button label="Cancelar" icon="fa fa-times" severity="danger" class="p-button-text" @click.stop="cancelWave(slotProps.data.id)" />
                                </div>
                                <div v-else-if="slotProps.data.state === 'done'" class="flex-row gap-small">
                                    <span class="text-green-500 font-bold"><i class="fa fa-check-circle"></i> Lista</span>
                                    <Button label="Reabrir" icon="fa fa-refresh" class="p-button-text p-button-sm" @click.stop="reopenWavePrompt(slotProps.data)" v-if="cycleCountState !== 'finalized' && cycleCountState !== 'cancelled'" />
                                </div>
                                <span v-else-if="slotProps.data.state === 'cancelled'" class="text-red-500 font-bold"><i class="fa fa-ban"></i> Cancelada</span>
                                <span v-else-if="cycleCountState === 'finalized' || cycleCountState === 'cancelled'" class="text-secondary italic">Sin acciones</span>
                            </template>
                        </Column>
                    </DataTable>
                </div>

                <div v-else-if="detailView === 'wave'">
                     <div class="flex-between mb-medium">
                        <div>
                            <Button icon="fa fa-arrow-left" label="Volver a Olas" @click="detailView = null" class="p-button-text" />
                            <h3 class="modal-title no-margin mt-2">Detalle de Ola: {{ selectedWave.name }}</h3>
                        </div>
                    </div>
                    <DataTable :value="waveLines" class="p-datatable-sm custom-border">
                         <template #header>
                            <h4 class="small-label no-margin">Productos Contados ({{ waveLines.length }})</h4>
                        </template>
                        <Column v-for="col of waveLinesCols" :key="col.field" :field="col.field" :header="col.name"></Column>
                        <template #empty>No se encontraron productos contados para esta ola.</template>
                    </DataTable>
                </div>
                <div v-else-if="detailView === 'logs'">
                    <div class="flex-between mb-medium">
                        <div>
                            <Button icon="fa fa-arrow-left" label="Volver" @click="detailView = null" class="p-button-text" />
                            <h3 class="modal-title no-margin mt-2">Log de Actividad: {{ modalData?.name }}</h3>
                        </div>
                        <span class="p-input-icon-left">
                            <i class="fa fa-search"></i>
                            <InputText v-model="logSearchQuery" placeholder="Filtrar logs..." class="p-inputtext-sm" />
                        </span>
                    </div>

                    <DataTable :value="filteredLogs" class="p-datatable-sm custom-border" paginator :rows="15">
                        <Column field="date" header="Fecha/Hora" sortable style="width: 200px"></Column>
                        <Column field="user" header="Usuario" sortable style="width: 150px"></Column>
                        <Column field="log" header="Mensaje"></Column>
                        <template #empty>No hay registros de actividad para este ciclo.</template>
                    </DataTable>
                </div>
                <div v-else-if="detailView === 'comparison'">
                    <div class="flex-between mb-medium">
                        <div>
                            <Button icon="fa fa-arrow-left" label="Volver" @click="detailView = null" class="p-button-text" />
                            <h3 class="modal-title no-margin mt-2">Consolidación de Conteos: {{ modalData?.name }}</h3>
                        </div>
                        <div class="flex-row gap-small">
                            <span class="p-input-icon-left mr-2">
                                <i class="fa fa-search"></i>
                                <InputText v-model="comparisonSearchQuery" placeholder="Buscar SKU/Producto..." class="p-inputtext-sm" />
                            </span>
                            <span class="p-input-icon-left mr-2">
                                <i class="fa fa-map-marker"></i>
                                <InputText v-model="comparisonLocationQuery" placeholder="Filtrar Ubicación..." class="p-inputtext-sm" />
                            </span>
                        </div>
                    </div>

                    <div class="card-background mb-small flex-between bg-white shadow-sm border-blue">
                        <div class="flex-row gap-small">
                            <Button label="Todo" :class="comparisonFilter === 'all' ? 'p-button-primary' : 'p-button-outlined'" @click="comparisonFilter = 'all'" />
                            <Button label="Discrepancias" :class="comparisonFilter === 'diff' ? 'p-button-danger' : 'p-button-outlined p-button-danger'" @click="comparisonFilter = 'diff'" />
                            <Button label="Coincidencias" :class="comparisonFilter === 'match' ? 'p-button-success' : 'p-button-outlined p-button-success'" @click="comparisonFilter = 'match'" />
                            <Divider layout="vertical" />
                            <Button label="Seleccionar Discrepancias" icon="fa fa-check-circle" class="p-button-text p-button-sm" @click="selectAllDiscrepancies" />
                            <Button label="Seleccionar Coincidencias" icon="fa fa-circle-o" class="p-button-text p-button-sm" @click="selectAllMatches" />
                        </div>
                        <div :title="anyWaveOpen ? 'No están todas las olas cerradas.' : ''">
                            <!-- Button label changed to "AJUSTAR Y FINALIZAR CONTEO" -->
                            <Button label="AJUSTAR Y FINALIZAR CONTEO" icon="fa fa-bolt" severity="success" :disabled="!canBulkAdjust || anyWaveOpen" @click="prepareBulkAdjustment" :loading="store.loading" />
                        </div>
                    </div>

                    <DataTable :value="filteredComparison" v-model:selection="comparisonSelection" dataKey="__uid" class="p-datatable-sm custom-border mt-3" responsiveLayout="scroll" paginator :rows="10">
                        <Column selectionMode="multiple" headerStyle="width: 3rem"></Column>
                        <Column header="Ubicación" field="location_name" sortable style="min-width: 150px">
                             <template #body="slotProps">
                                <div class="flex align-items-center gap-2">
                                    <span :class="['font-bold', slotProps.data.is_blocked ? 'text-secondary line-through' : 'text-primary']">{{ slotProps.data.location_name }}</span>
                                    <i v-if="slotProps.data.is_blocked" class="fa fa-lock text-secondary" title="Ubicación Excluida"></i>
                                    <i v-if="slotProps.data.has_reservation" 
                                       class="fa fa-info-circle text-blue-500" 
                                       :title="'Reservado por: ' + slotProps.data.reservation_info">
                                    </i>
                                </div>
                             </template>
                        </Column>
                        <Column field="product_sku" header="SKU" sortable></Column>
                        <Column field="barcode" header="Código Barras" sortable></Column>
                        <Column field="product_name" header="Producto" sortable style="min-width: 200px">
                             <template #body="slotProps">
                                <div class="product-cell">
                                    <span class="block">{{ slotProps.data.product_name }}</span>
                                    <small class="text-secondary">{{ slotProps.data.product_sku }}</small>
                                </div>
                             </template>
                        </Column>
                        
                        <Column v-for="(wave, idx) in comparisonWaves" :key="wave.id">
                            <template #header>
                                <div class="header-wave" :title="`${wave.name} - ${wave.operator}`">
                                    <span :class="['wave-state-indicator', wave.state]"></span>
                                    <span class="block">W{{ idx + 1 }}</span>
                                    <small class="block">{{ wave.operator.split(' ')[0] }}</small>
                                </div>
                            </template>
                            <template #body="slotProps">
                                <div class="wave-count-cell" v-if="slotProps.data.wave_counts[wave.id] !== '-'">
                                    <Button 
                                        :label="String(slotProps.data.wave_counts[wave.id])" 
                                        :class="['p-button-sm', proposedQuantities[slotProps.data.__uid] === slotProps.data.wave_counts[wave.id] ? 'p-button-info' : 'p-button-outlined p-button-secondary']"
                                        @click="selectTruth(slotProps.data, slotProps.data.wave_counts[wave.id], wave.id)" 
                                    />
                                </div>
                                <span v-else class="text-secondary">-</span>
                            </template>
                        </Column>
                        
                        <Column field="theoretical_qty" header="Odoo" sortable>
                            <template #body="slotProps">
                                <Button 
                                    :label="String(slotProps.data.theoretical_qty)" 
                                    :class="['p-button-sm', proposedQuantities[slotProps.data.__uid] === slotProps.data.theoretical_qty ? 'p-button-info' : 'p-button-outlined p-button-secondary']"
                                    @click="selectTruth(slotProps.data, slotProps.data.theoretical_qty)" 
                                />
                            </template>
                        </Column>

                        <!-- Header changed to "Ajustar cantidad a:" -->
                        <Column header="Ajustar cantidad a:" headerStyle="width: 8rem">
                            <template #body="slotProps">
                                <InputNumber v-model="proposedQuantities[slotProps.data.__uid]" :min="0" inputClass="input-center font-bold p-inputtext-sm" />
                            </template>
                        </Column>

                        <Column header="Estado">
                            <template #body="slotProps">
                                <span v-if="slotProps.data.theoretical_qty === proposedQuantities[slotProps.data.__uid]" class="text-green-500 font-bold">
                                    <i class="fa fa-check"></i> OK
                                </span>
                                <span v-else class="text-red-500 font-bold">
                                    <i class="fa fa-exclamation-triangle"></i> DIF
                                </span>
                            </template>
                        </Column>

                        <!-- Header changed to "Excluir de futuras olas" -->
                        <Column header="Excluir de futuras olas" headerStyle="width: 8rem">
                            <template #body="slotProps">
                                <Button 
                                    :icon="slotProps.data.is_blocked ? 'fa fa-lock' : 'fa fa-unlock'" 
                                    :class="['p-button-rounded p-button-text', slotProps.data.is_blocked ? 'p-button-danger' : 'p-button-secondary']"
                                    @click="toggleLocationBlock(slotProps.data)"
                                    title="Excluir de futuras olas"
                                />
                            </template>
                        </Column>
                    </DataTable>
                </div>
            </div>
        </div>

        <!-- Bulk Adjustment Dialog -->
        <!-- Header changed to reflect adjustment and finalization -->
        <Dialog v-model:visible="bulkAdjDialog.visible" header="Ajustar y Finalizar Conteo" modal class="p-fluid" style="width: 500px">
             <div class="mb-3">
                <div v-if="anyWaveOpen" class="warning-box mb-3">
                    <i class="fa fa-exclamation-triangle"></i>
                    <span>Hay olas que aún no han sido finalizadas. Se recomienda esperar a que todos los operadores terminen.</span>
                </div>
                <p>Estás por ajustar <strong>{{ comparisonSelection.length }}</strong> registros de inventario y finalizar el conteo.</p>
                <p class="text-danger font-bold">¡Esta acción es irreversible!</p>
            </div>
            <div class="field">
                <label class="font-bold">Motivo del Ajuste Masivo</label>
                <InputText v-model="bulkAdjDialog.reason" placeholder="Ej: Consolidación Auditoría Anual..." />
            </div>
            <template #footer>
                <div :title="anyWaveOpen ? 'No están todas las olas cerradas.' : ''" style="display:inline-block">
                    <Button label="Cancelar" icon="fa fa-times" @click="bulkAdjDialog.visible = false" class="p-button-text mr-2" />
                    <Button label="CONFIRMAR Y FINALIZAR" icon="fa fa-check" severity="success" @click="confirmBulkAdjustment" :loading="store.loading" :disabled="anyWaveOpen" />
                </div>
            </template>
        </Dialog>

        <!-- Adjustment Dialog -->
        <Dialog v-model:visible="adjDialog.visible" header="Ajustar Stock Manualmente" modal class="p-fluid" style="width: 500px">
            <div v-if="adjDialog.line">
                <div v-if="anyWaveOpen" class="warning-box mb-3">
                    <i class="fa fa-exclamation-triangle"></i>
                    <span>Hay olas abiertas. Los resultados podrían no ser definitivos.</span>
                </div>
                <div class="mb-3">
                    <p class="no-margin"><strong>Producto:</strong> {{ adjDialog.line.product_sku }} - {{ adjDialog.line.product_name }}</p>
                    <p class="no-margin"><strong>Ubicación:</strong> {{ adjDialog.line.location_name }}</p>
                </div>
                <div class="field mb-3">
                    <label class="font-bold">Nueva Cantidad</label>
                    <InputNumber v-model="adjDialog.qty" :min="0" showButtons autofocus />
                </div>
                <div class="field">
                    <label class="font-bold">Motivo del Ajuste</label>
                    <InputText v-model="adjDialog.reason" placeholder="Ej: Conteo ciclo CC... olas N y M..." />
                </div>
                <small class="text-secondary block mt-2">
                    * El motivo se registrará en el historial del movimiento.
                </small>
            </div>
            <template #footer>
                <div :title="anyWaveOpen ? 'No están todas las olas cerradas.' : ''" style="display:inline-block">
                    <Button label="Cancelar" icon="fa fa-times" @click="adjDialog.visible = false" class="p-button-text mr-2" />
                    <Button label="CONFIRMAR AJUSTE" icon="fa fa-check" severity="success" @click="confirmAdjustment" :loading="store.loading" :disabled="!adjDialog.reason || anyWaveOpen" />
                </div>
            </template>
        </Dialog>

        <Dialog v-model:visible="reopenDialog.visible" header="Reabrir Ola de Conteo" modal class="p-fluid" style="width: 450px">
            <div class="field">
                <label class="font-bold">Motivo de Reapertura</label>
                <InputText v-model="reopenDialog.reason" placeholder="Ej: Error en conteo de SKU..." autofocus />
            </div>
            <template #footer>
                <Button label="Cancelar" icon="fa fa-times" @click="reopenDialog.visible = false" class="p-button-text" />
                <Button label="REABRIR OLA" icon="fa fa-check" severity="warning" @click="confirmReopen" :loading="store.loading" :disabled="!reopenDialog.reason" />
            </template>
        </Dialog>

        <Dialog v-model:visible="operatorDialog.visible" :header="operatorDialog.title" modal class="p-fluid" style="width: 450px">
            <Listbox v-model="operatorDialog.selected" :options="optionsCache['operadores']" optionLabel="name" optionValue="id" :multiple="operatorDialog.multiSelect" filter listStyle="max-height:250px" />
            <template #footer>
                <Button label="Cancelar" icon="fa fa-times" @click="operatorDialog.visible = false" class="p-button-text" />
                <Button label="Guardar" icon="fa fa-check" @click="handleOperatorSave" :loading="store.loading" />
            </template>
        </Dialog>
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
import Dialog from 'primevue/dialog';
import Listbox from 'primevue/listbox';
import Divider from 'primevue/divider';

export default {
    name: "CycleCountModal",
    components: { InputText, InputNumber, Button, DataTable, Column, Dropdown, Dialog, Listbox, Divider },
    data() {
        return {
            store: useGeneralStore(),
            currentStep: 1,
            filters: { aisle_from: "A", aisle_to: "Z", position_from: 1, position_to: 99, level_from: 1, level_to: 5, front_from: 1, front_to: 2 },
            searchResults: [],
            selectedLocations: [],
            tempSelection: [],
            finalSelection: [],
            rawSearchQueryResults: "",
            debouncedSearchQueryResults: "",
            rawSearchQuerySelected: "",
            debouncedSearchQuerySelected: "",
            assignedOperators: [{ id: Date.now(), operator_id: null }],
            newCount: { ref: "" },
            waves: [],
            created_by: '',
            cycleCountState: 'created',
            cycleCountNotes: '',
            optionsCache: { operadores: [] },
            
            detailView: null, 
            selectedWave: null,
            waveLines: [],
            waveLinesCols: [],

            comparisonData: [],
            comparisonWaves: [],
            comparisonFilter: 'all', // all, diff, match
            comparisonSearchQuery: '',
            comparisonLocationQuery: '',
            comparisonSelection: [],
            proposedQuantities: {}, // { 'locId_prodId': qty }

            logData: [],
            logSearchQuery: '',
            
            adjDialog: {
                visible: false,
                line: null,
                qty: 0,
                reason: ''
            },
            bulkAdjDialog: {
                visible: false,
                reason: ''
            },
            reopenDialog: {
                visible: false,
                wave: null,
                reason: ''
            },

            // Operator dialog state
            operatorDialog: {
                visible: false,
                title: '',
                mode: 'add', 
                multiSelect: true,
                selected: null
            }
        };
    },
    computed: {
        modalData() { return this.store.form_context?.data || {}; },
        isCreating() { return !!this.modalData.cycle_count || this.modalData.form_type === 'new'; },
        isRangeInvalid() {
            const f = this.filters;
            if (!f.aisle_from || !f.aisle_to) return true;
            
            // Warehouse logic: shorter length is smaller (A < Z < AA < ZZ)
            // If lengths same, standard string compare
            const isAisleInvalid = (a, b) => {
                if (a.length > b.length) return true;
                if (a.length < b.length) return false;
                return a > b;
            };

            return isAisleInvalid(f.aisle_from, f.aisle_to) || (f.position_from > f.position_to) || (f.level_from > f.level_to) || (f.front_from > f.front_to);
        },
        isSaveDisabled() {
            return !this.newCount.ref || this.assignedOperators.length === 0 || this.assignedOperators.some(op => !op.operator_id) || !this.selectedLocations.length;
        },
        filteredComparison() {
            let base = this.comparisonData;
            if (this.comparisonFilter === 'diff') base = base.filter(d => d.has_discrepancy);
            if (this.comparisonFilter === 'match') base = base.filter(d => !d.has_discrepancy);
            
            if (this.comparisonSearchQuery) {
                const q = this.comparisonSearchQuery.toLowerCase();
                base = base.filter(d => d.product_sku.toLowerCase().includes(q) || d.product_name.toLowerCase().includes(q));
            }
            if (this.comparisonLocationQuery) {
                const q = this.comparisonLocationQuery.toLowerCase();
                base = base.filter(d => d.location_name.toLowerCase().includes(q));
            }
            return base;
        },
        canBulkAdjust() {
            return this.comparisonSelection.length > 0;
        },
        hasActiveWave() {
            return this.waves.some(w => w.state !== 'done' && w.state !== 'cancelled');
        },
        anyWaveOpen() {
            return this.comparisonWaves.some(w => w.state !== 'done' && w.state !== 'cancelled');
        },
        filteredSearchResults() {
            if (!this.debouncedSearchQueryResults) return this.searchResults;
            const q = this.debouncedSearchQueryResults.toLowerCase();
            return this.searchResults.filter(l => l.complete_name.toLowerCase().includes(q));
        },
        filteredSelectedLocations() {
            if (!this.debouncedSearchQuerySelected) return this.selectedLocations;
            const q = this.debouncedSearchQuerySelected.toLowerCase();
            return this.selectedLocations.filter(l => l.complete_name.toLowerCase().includes(q));
        },
        filteredLogs() {
            if (!this.logSearchQuery) return this.logData;
            const q = this.logSearchQuery.toLowerCase();
            return this.logData.filter(l => l.log.toLowerCase().includes(q) || l.user.toLowerCase().includes(q));
        }
    },
    async mounted() {
        await this.loadOperators();
        if (!this.isCreating && this.modalData.id) {
            this.created_by = this.modalData.create_uid;
            await this.loadExistingCountDetails();
        }
    },
    watch: {
        rawSearchQueryResults(newVal) {
            if (this.searchTimeoutResults) clearTimeout(this.searchTimeoutResults);
            this.searchTimeoutResults = setTimeout(() => {
                this.debouncedSearchQueryResults = newVal;
            }, 300);
        },
        rawSearchQuerySelected(newVal) {
            if (this.searchTimeoutSelected) clearTimeout(this.searchTimeoutSelected);
            this.searchTimeoutSelected = setTimeout(() => {
                this.debouncedSearchQuerySelected = newVal;
            }, 300);
        }
    },
    methods: {
        async loadOperators() {
            let res = await this.store.callOdoo("operadores", "*");
            const data = res?.data || (Array.isArray(res) ? res : []);
            this.optionsCache = { ...this.optionsCache, operadores: data };
        },
        async fetchLocations() {
            let res = await this.store.callOdoo("get_locations_by_range", "", this.filters);
            if (res?.locations) { this.searchResults = res.locations; this.tempSelection = []; }
        },
        async loadExistingCountDetails() {
            this.detailView = null; // Reset view when reloading
            let res = await this.store.callOdoo("get_cycle_count_details", "", { count_id: this.modalData.id });
            if (res.ok) {
                this.selectedLocations = res.details.locations;
                this.waves = res.details.waves;
                this.cycleCountState = res.details.state;
                this.cycleCountNotes = res.details.notes;
            }
        },
        isAlreadySelected(data) { return this.selectedLocations.some(s => s.id === data.id); },
        isSelectable(data) { 
            // data might be the record directly or an event object depending on PrimeVue version
            const item = data.data || data;
            return !this.isAlreadySelected(item) && !item.has_reservation; 
        },
        rowClass(data) { 
            if (this.isAlreadySelected(data)) return 'row-locked';
            if (data.has_reservation) return 'row-reserved';
            return '';
        },
        addSelected() {
            const toAdd = this.tempSelection.filter(item => !this.isAlreadySelected(item) && !item.has_reservation);
            this.selectedLocations = [...this.selectedLocations, ...toAdd];
            this.tempSelection = [];
        },
        removeSelected() {
            const idsToRemove = this.finalSelection.map(s => s.id);
            this.selectedLocations = this.selectedLocations.filter(l => !idsToRemove.includes(l.id));
            this.finalSelection = [];
        },
        addOperatorField() { this.assignedOperators.push({ id: Date.now() + Math.random(), operator_id: null }); },
        removeOperatorField(idx) { 
            this.assignedOperators = this.assignedOperators.filter((_, i) => i !== idx); 
        },
        async saveFullCount() {
            const payload = {
                name: this.newCount.ref,
                location_ids: this.selectedLocations.map(l => l.id),
                operators: this.assignedOperators.map(op => op.operator_id)
            };
            let res = await this.store.callOdoo("create_full_cycle_count", "", payload);
            if (res.ok) {
                this.$toast.add({ 
                    severity: 'success', 
                    summary: 'Conteo Cíclico Creado', 
                    detail: `Conteo cíclico ${res.name} creado con éxito`, 
                    life: 5000 
                });
                this.store.closeModal(true);
            } else {
                this.$toast.add({ severity: 'error', summary: 'Error al Generar', detail: (res.error || 'Error desconocido'), life: 5000 });
            }
        },
        async finishWave(id) {
            if (!confirm("¿Marcar esta ola como finalizada?")) return;
            let res = await this.store.callOdoo("finish_cycle_count_wave", "", { wave_id: id });
            if (res.ok) await this.loadExistingCountDetails();
        },
        async cancelWave(id) {
            if (!confirm("¿Cancelar esta ola? Esta acción no se puede deshacer.")) return;
            let res = await this.store.callOdoo("cancel_cycle_count_wave", "", { wave_id: id });
            if (res.ok) await this.loadExistingCountDetails();
        },
        async closeEntireCount() {
            // Internal method to close cycle, now also called by confirmBulkAdjustment
            let res = await this.store.callOdoo("close_cycle_count", "", { count_id: this.modalData.id });
            if (res.ok) await this.loadExistingCountDetails();
            return res;
        },
        async cancelEntireCount() {
            if (!confirm("¿Cancelar ciclo completo? Todas las olas en curso también serán canceladas.")) return;
            let res = await this.store.callOdoo("cancel_cycle_count", "", { count_id: this.modalData.id });
            if (res.ok) await this.loadExistingCountDetails();
        },
        async showWaveDetails(event) {
            this.selectedWave = event.data;
            const res = await this.store.callOdoo("get_cycle_wave_lines", "", { wave_id: this.selectedWave.id });
            if (res.ok) {
                this.waveLines = res.data;
                this.waveLinesCols = res.map_cols;
                this.detailView = 'wave';
            }
        },
        async showLogsReport() {
            const res = await this.store.callOdoo("get_cycle_count_logs", "", { count_id: this.modalData.id });
            if (res.ok) {
                this.logData = res.data;
                this.detailView = 'logs';
                this.logSearchQuery = '';
            }
        },
        async showComparisonReport() {
            const res = await this.store.callOdoo("get_cycle_count_comparison", "", { count_id: this.modalData.id });
            if (res.ok) {
                this.comparisonData = res.data.map(row => ({
                    ...row,
                    __uid: `${row.location_id}_${row.product_id}`
                }));
                this.comparisonWaves = res.waves;
                this.detailView = 'comparison';
                this.comparisonSelection = [];
                // Initialize proposed quantities with odoo stock as default
                this.proposedQuantities = {};
                this.comparisonData.forEach(row => {
                    this.proposedQuantities[row.__uid] = row.theoretical_qty;
                });
            }
        },
        rowKey(row) {
            return row.__uid;
        },
        getProposedQty(row) {
            return this.proposedQuantities[this.rowKey(row)];
        },
        selectTruth(row, qty, waveId = null) {
            const key = this.rowKey(row);
            this.proposedQuantities[key] = qty;
        },
        selectAllDiscrepancies() {
            this.comparisonSelection = this.comparisonData.filter(d => d.has_discrepancy);
        },
        selectAllMatches() {
            this.comparisonSelection = this.comparisonData.filter(d => !d.has_discrepancy);
        },
        prepareBulkAdjustment() {
            const waveNames = this.comparisonWaves.map(w => w.name).join(', ');
            this.bulkAdjDialog.reason = `Ajuste Masivo Ciclo ${this.modalData.name}. Olas: ${waveNames}.`;
            this.bulkAdjDialog.visible = true;
        },
        async confirmBulkAdjustment() {
            if (!this.bulkAdjDialog.reason) return;
            if (this.anyWaveOpen) {
                this.$toast.add({ severity: 'error', summary: 'Acción Bloqueada', detail: 'No se pueden hacer ajustes si hay olas sin finalizar o cancelar.', life: 5000 });
                return;
            }
            this.store.loading = true;
            try {
                let count = 0;
                for (const row of this.comparisonSelection) {
                    // Skip adjustment for dummy "Empty Location" rows
                    if (!row.product_id || row.product_id === 0) {
                        count++;
                        continue;
                    }

                    const key = this.rowKey(row);
                    const new_qty = this.proposedQuantities[key];
                    
                    let res = await this.store.callOdoo("adjust_cycle_count_stock", "", {
                        line: row,
                        new_qty: new_qty,
                        reason: this.bulkAdjDialog.reason,
                        count_name: this.modalData.name
                    });
                    if (res.ok) count++;
                }
                
                // After bulk adjustment, finalize the entire count automatically
                await this.closeEntireCount();

                const isManager = this.store.role && (this.store.role.role === 'WMDs Manager' || (this.store.role.permissions && this.store.role.permissions.includes('WMDs Manager')));
                if (!isManager) {
                    this.$toast.add({ severity: 'success', summary: 'Ajuste y Cierre Finalizado', detail: `${count} ajustes realizados y ciclo cerrado.`, life: 3000 });
                }
                this.bulkAdjDialog.visible = false;
                await this.loadExistingCountDetails(); // Go back to overview
            } catch (e) {
                this.$toast.add({ severity: 'error', summary: 'Error Masivo', detail: 'Hubo un error en el procesamiento masivo.', life: 3000 });
            } finally {
                this.store.loading = false;
            }
        },
        prepareAdjustment(line) {
            this.adjDialog.line = line;
            const firstCount = Object.values(line.wave_counts).find(c => c !== '-');
            this.adjDialog.qty = firstCount !== undefined ? firstCount : line.theoretical_qty;
            
            const waveNames = this.comparisonWaves.map(w => w.name).join(', ');
            this.adjDialog.reason = `Ajuste Ciclo ${this.modalData.name}. Olas: ${waveNames}.`;
            this.adjDialog.visible = true;
        },
        async confirmAdjustment() {
            if (!this.adjDialog.reason) return;
            if (this.anyWaveOpen) {
                this.$toast.add({ severity: 'error', summary: 'Acción Bloqueada', detail: 'No se pueden hacer ajustes si hay olas sin finalizar o cancelar.', life: 5000 });
                return;
            }

            if (!this.adjDialog.line.product_id || this.adjDialog.line.product_id === 0) {
                this.adjDialog.visible = false;
                return;
            }

            const res = await this.store.callOdoo("adjust_cycle_count_stock", "", {
                line: this.adjDialog.line,
                new_qty: this.adjDialog.qty,
                reason: this.adjDialog.reason,
                count_name: this.modalData.name
            });

            if (res.ok) {
                const isManager = this.store.role && (this.store.role.role === 'WMDs Manager' || (this.store.role.permissions && this.store.role.permissions.includes('WMDs Manager')));
                if (!isManager) {
                    this.$toast.add({ severity: 'success', summary: 'Éxito', detail: 'Stock ajustado correctamente.', life: 3000 });
                }
                this.adjDialog.visible = false;
                await this.showComparisonReport(); 
            } else {
                this.$toast.add({ severity: 'error', summary: 'Error', detail: (res.error || 'Error desconocido'), life: 3000 });
            }
        },
        showOperatorDialog(mode, wave = null) {
            this.operatorDialog.mode = mode;
            this.selectedWave = wave;
            if (mode === 'add') {
                this.operatorDialog.title = 'Añadir Nueva Ola';
                this.operatorDialog.multiSelect = true;
                this.operatorDialog.selected = [];
            } else { // reassign
                this.operatorDialog.title = `Reasignar Operador para ${wave.name}`;
                this.operatorDialog.multiSelect = false;
                this.operatorDialog.selected = null;
            }
            this.operatorDialog.visible = true;
        },
        reopenWavePrompt(wave) {
            this.reopenDialog.wave = wave;
            this.reopenDialog.reason = '';
            this.reopenDialog.visible = true;
        },
        async confirmReopen() {
            if (!this.reopenDialog.reason) return;
            let res = await this.store.callOdoo("reopen_cycle_count_wave", "", {
                wave_id: this.reopenDialog.wave.id,
                reason: this.reopenDialog.reason
            });
            if (res.ok) {
                this.reopenDialog.visible = false;
                await this.loadExistingCountDetails();
                if (this.detailView === 'comparison') {
                    await this.showComparisonReport();
                }
            }
        },
        async toggleLocationBlock(row) {
            let res = await this.store.callOdoo("toggle_location_block", "", {
                count_id: this.modalData.id,
                location_id: row.location_id
            });
            if (res.ok) {
                this.comparisonData.forEach(d => {
                    if (d.location_id === row.location_id) {
                        d.is_blocked = res.is_blocked;
                    }
                });
                const isManager = this.store.role && (this.store.role.role === 'WMDs Manager' || (this.store.role.permissions && this.store.role.permissions.includes('WMDs Manager')));
                if (!isManager) {
                    this.$toast.add({ severity: 'success', summary: 'Ubicación Actualizada', detail: `La ubicación ahora está ${res.is_blocked ? 'excluida' : 'disponible'}.`, life: 2000 });
                }
            } else {
                this.$toast.add({ severity: 'error', summary: 'Error al Cambiar Estado', detail: (res.error || 'No se pudo cambiar el estado de bloqueo.'), life: 5000 });
            }
        },
        async handleOperatorSave() {
            if (this.operatorDialog.mode === 'add') {
                 if (!this.operatorDialog.selected || this.operatorDialog.selected.length === 0) return;
                const payload = {
                    location_ids: this.selectedLocations.map(l => l.id),
                    operators: this.operatorDialog.selected,
                    cycle_count_id: this.modalData.id
                };
                 let res = await this.store.callOdoo("create_waves_for_cycle", "", payload);
                 if (res.ok) await this.loadExistingCountDetails();

            } else { // reassign
                if (!this.operatorDialog.selected) return;
                const payload = {
                    wave_id: this.selectedWave.id,
                    operator_id: this.operatorDialog.selected
                };
                let res = await this.store.callOdoo("reassign_cycle_count_wave_operator", "", payload);
                if (res.ok) await this.loadExistingCountDetails();
            }
            this.operatorDialog.visible = false;
        }
    }
};
</script>

<style scoped>
.cycle-count-wrapper { padding: 1rem 1.5rem; }
.cycle-count-modal { max-width: 1050px; margin: 0 auto; color: #333; }
.modal-title { font-size: 1.6rem; font-weight: 800; margin-bottom: 0.25rem; }
.sub-title { font-size: 0.9rem; color: #6c757d; display: block; margin-bottom: 1.5rem; }
.wizard-stepper { display: flex; justify-content: center; gap: 1rem; margin-bottom: 2rem; }
.step-pill { padding: 0.6rem 1.5rem; background: #e9ecef; border-radius: 25px; font-weight: 700; color: #999; }
.step-pill.active { background: #007bff; color: #fff; box-shadow: 0 4px 10px rgba(0,123,255,0.3); }
.card-background { background: #f9f9f9; padding: 1.25rem; border-radius: 8px; border: 1px solid #eee; }
.filter-section { display: flex; flex-wrap: wrap; gap: 1rem; margin-bottom: 1.5rem; align-items: flex-end; }
.filter-group { flex: 1 1 calc(25% - 1rem); min-width: 180px; }
.filter-label { display: block; font-weight: 700; font-size: 0.85rem; margin-bottom: 0.4rem; }
.filter-actions { flex-grow: 0; }
.tables-container { display: flex; flex-wrap: wrap; gap: 1.5rem; margin-bottom: 1.5rem; }
.table-half { flex: 1 1 calc(50% - 1.5rem); min-width: 350px; }
.custom-border { border: 1px solid #ddd; border-radius: 8px; overflow: hidden; }
:deep(.p-datatable-row-selectable) { cursor: pointer; }
:deep(.row-locked) { background-color: #e8f5e9 !important; color: #2e7d32 !important; font-style: italic; }
:deep(.row-locked .p-checkbox) { display: none; }
:deep(.row-reserved) { background-color: #f1f1f1 !important; color: #999 !important; font-style: italic; }
:deep(.row-reserved .p-checkbox) { display: none; }
.wizard-footer { display: flex; justify-content: flex-end; margin-top: 1rem; }
.input-ref { width: 350px; }
.operators-grid { display: flex; flex-wrap: wrap; gap: 1rem; margin-top: 1rem; }
.operator-card { flex: 1 1 calc(33.33% - 1rem); min-width: 280px; border-left: 5px solid #007bff; }
.wave-number { font-weight: 800; color: #007bff; }
.small-label { font-size: 0.8rem; font-weight: bold; color: #666; margin-bottom: 0.3rem; display: block; }
.final-footer { display: flex; justify-content: center; padding: 2rem 0; }
.flex-row { display: flex; align-items: center; }
.flex-between { display: flex; justify-content: space-between; align-items: center; }
.gap-small { gap: 0.5rem; }
.input-full { width: 100%; }
.fade-in { animation: fadeIn 0.3s ease-in; }
.text-orange-500 { color: #f59e0b; }
.mr-2 { margin-right: 0.5rem; }
.mt-2 { margin-top: 0.5rem; }
.text-secondary { color: #6c757d; }
.no-margin { margin: 0; }
.italic { font-style: italic; }
.state-badge { padding: 0.4rem 0.8rem; border-radius: 4px; font-weight: 800; font-size: 0.9rem; letter-spacing: 0.5px; }
.state-badge.finalized { background: #e8f5e9; color: #2e7d32; border: 1px solid #c8e6c9; }
.search-bar-container { position: relative; }
:deep(.p-input-icon-left > i) { left: 0.75rem; color: #999; }
:deep(.p-input-icon-left > .p-inputtext) { padding-left: 2.5rem; }
.mb-small { margin-bottom: 0.5rem; }
.ml-auto { margin-left: auto; }
.border-blue { border: 1px solid #3498db; }
.bg-white { background: #fff !important; }
.shadow-sm { box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
.product-cell { line-height: 1.2; }
.header-wave { line-height: 1; text-align: center; }
.header-wave small { font-size: 0.7rem; color: #666; font-weight: normal; }
.wave-count-cell { text-align: center; }
:deep(.input-center input) { text-align: center !important; }
.text-danger { color: #dc3545; }
.font-bold { font-weight: bold; }

/* Custom Scrollbar Visibility */
:deep(.p-datatable-wrapper), :deep(.p-datatable-scrollable-body) {
    scrollbar-width: auto;
    scrollbar-color: #3498db #f1f1f1;
}

:deep(::-webkit-scrollbar) {
    width: 10px;
    height: 10px;
}

:deep(::-webkit-scrollbar-track) {
    background: #f1f1f1; border-radius: 5px; } :deep(::-webkit-scrollbar-thumb) { background: #3498db; border-radius: 5px; border: 2px solid #f1f1f1; } :deep(::-webkit-scrollbar-thumb:hover) { background: #2980b9; } /* Wave State Indicators */ .wave-state-indicator { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 5px; } .wave-state-indicator.draft { background-color: #95a5a6; } .wave-state-indicator.ongoing { background-color: #f1c40f; } .wave-state-indicator.done { background-color: #2ecc71; } .wave-state-indicator.cancelled { background-color: #e74c3c; } .warning-box { background: #fff3cd; border: 1px solid #ffeeba; color: #856404; padding: 10px; border-radius: 4px; display: flex; align-items: center; gap: 10px; font-size: 0.9rem; } </style>