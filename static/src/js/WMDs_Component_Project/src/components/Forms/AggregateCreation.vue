<template>
    <div>
        <div class="mb-6 p-4 border-round-xl surface-card shadow-1">
            <h3 class="mt-0 mb-3 text-700">1. Carga de Datos</h3>
            
            <div class="mb-4">
                <FloatLabel>
                    <Textarea id="aggregate" 
                        v-model="creation.create_by_aggregate.input_aggregate_data" 
                        @keyup.enter="splitInput"
                        rows="1"
                        autoResize
                        class="w-full"
                        style="min-height: 45px; padding-top: 1rem;" 
                    />
                    <label for="aggregate">
                        {{ creation.create_by_aggregate.input_aggregate_instructions }}
                    </label>
                </FloatLabel>  
                <small class="text-gray-500">Tip: Pega tu columna de Excel aquí y presiona Enter.</small>
            </div>

            <div class="flex justify-between align-items-center mb-2" v-if="aggregates.length > 0">
                <span class="text-sm text-gray-600">
                    {{ aggregates.length }} elementos en lista
                </span>
                <Button 
                    v-if="selectedAggregates.length > 0"
                    :label="'Borrar (' + selectedAggregates.length + ')'" 
                    icon="pi pi-trash" 
                    severity="danger" 
                    outlined
                    size="small"
                    @click="deleteSelected"
                />
            </div>

            <DataTable 
                :value="aggregates" 
                v-model:selection="selectedAggregates" 
                selectionMode="multiple" 
                :metaKeySelection="false"
                dataKey="value"
                tableStyle="min-width: 50rem"
                v-if="aggregates.length > 0"
                class="mb-4"
                :rowClass="rowClass"
                editMode="cell" 
            >
                <Column selectionMode="multiple" headerStyle="width: 3rem"></Column>
                <Column header="Dato (Editable)">
                    <template #body="slotProps">
                        <InputText 
                            v-model="slotProps.data.value" 
                            class="w-full p-inputtext-sm"
                            :class="{'p-invalid': slotProps.data.error}"
                            @input="clearError(slotProps.data)"
                            placeholder="Valor vacío..."
                        />
                    </template>
                </Column>
                <Column header="Estado / Errores">
                    <template #body="slotProps">
                        <span v-if="slotProps.data.error" class="text-red-600 font-bold text-sm flex align-items-center gap-2">
                            <i class="pi pi-exclamation-circle"></i> {{ slotProps.data.error }}
                        </span>
                        <span v-else-if="isValidated" class="text-green-600 font-bold text-sm flex align-items-center gap-2">
                            <i class="pi pi-check-circle"></i> Listo
                        </span>
                        <span v-else class="text-gray-400 text-sm">...</span>
                    </template>
                </Column>
                <Column header="Acciones" headerStyle="width: 5rem; text-align: center" bodyStyle="text-align: center">
                    <template #body="slotProps">
                        <Button icon="pi pi-trash" severity="danger" text rounded @click="removeAggregate(slotProps.data)" />
                    </template>
                </Column>
            </DataTable>

            <div class="flex justify-end gap-2" v-if="aggregates.length > 0">
                <Button v-if="hasErrors" label="Guardar ignorando errores" icon="pi pi-exclamation-triangle" severity="warning" @click="forceSaveValid" v-tooltip="'Guardar solo los verdes'" />
                <Button label="Validar y Enviar" icon="pi pi-send" @click="sendData" :severity="hasErrors ? 'secondary' : 'primary'" />
            </div>
        </div>

        <div v-if="sentAggregates.length > 0" class="p-4 border-round-xl surface-ground border-1 surface-border">
            <h3 class="mt-0 mb-3 text-green-700 flex align-items-center gap-2">
                <i class="pi pi-verified"></i> 2. Procesados Correctamente
            </h3>
            <DataTable :value="sentAggregates" dataKey="value" stripedRows>
                <Column field="value" header="Dato Guardado"></Column>
                <Column header="Estado">
                    <template #body>
                        <span class="inline-flex align-items-center border-round px-2 py-1 bg-green-100 text-green-700 text-sm font-bold">Enviado</span>
                    </template>
                </Column>
            </DataTable>
        </div>
    </div>
</template>

<script>
    import InputText from 'primevue/inputtext';
    import Textarea from 'primevue/textarea'; // IMPORTANTE: Importar Textarea
    import FloatLabel from 'primevue/floatlabel';
    import DataTable from 'primevue/datatable';
    import Column from 'primevue/column';
    import Button from 'primevue/button';
    import Tooltip from 'primevue/tooltip';
    import { useGeneralStore } from "../../store/index"

    export default {
        name: "AggregateCreation", 
        // Registramos el componente Textarea
        components: { InputText, Textarea, FloatLabel, DataTable, Column, Button },
        directives: { 'tooltip': Tooltip },
        props: {
          creation: { type: Object, required: true },
          id: { required: true }
        },
        data: function() {
            return {
                store: useGeneralStore(),
                aggregates: [],         
                sentAggregates: [],     
                selectedAggregates: [], 
                isValidated: false      
            }
        },
        computed: {
            hasErrors() {
                const errorFound = this.aggregates.some(item => item.error !== null);
                console.log("Calculando hasErrors:", errorFound);
                return errorFound;
            }
        },
        methods: {
            splitInput() {
                console.log("--- INICIO splitInput ---");
                const text = this.creation.create_by_aggregate.input_aggregate_data;
                console.log("Texto crudo recibido:", text); // AHORA SÍ VERÁS LOS SALTOS DE LÍNEA AQUÍ

                if (!text || text.trim().length === 0) return;

                // NOTA: He eliminado 'Espacio' de la lista porque tus datos "Panel 1" tienen espacios.
                // Si dejamos espacio, te va a partir "Panel" y "1" en dos filas distintas.
                const CANDIDATE_SEPARATORS = [
                    { char: '\n', label: 'Salto' }, 
                    { char: '\t', label: 'Tab' },
                    { char: ',',  label: 'Coma' }, 
                    { char: ';',  label: 'Punto y coma' },
                    { char: '|',  label: 'Pipe' }
                ];

                let maxCount = 0;
                let winner = '\n'; // Default a Salto de línea, ideal para Excel
                
                CANDIDATE_SEPARATORS.forEach(sep => {
                    const count = text.split(sep.char).length - 1;
                    if (count > maxCount) { maxCount = count; winner = sep.char; }
                });
                console.log("Separador ganador:", winner);

                let separatorRegex = winner;
                // Detectar mezcla de Tab y Enter (común al pegar rangos grandes de Excel)
                if (text.includes('\n') && text.includes('\t')) {
                    separatorRegex = /[\n\t]+/; 
                }

                const rawValues = text.split(separatorRegex).map(i => i.trim()).filter(i => i !== ''); 
                
                let addedCount = 0;
                rawValues.forEach(val => {
                    const existsInPending = this.aggregates.some(agg => agg.value === val);
                    const existsInSent = this.sentAggregates.some(agg => agg.value === val);
                    
                    if (!existsInPending && !existsInSent) {
                        this.aggregates.push({ value: val, error: null });
                        addedCount++;
                    }
                });

                this.creation.create_by_aggregate.input_aggregate_data = '';
                this.isValidated = false; 
            },

            // ... (Resto de métodos: removeAggregate, deleteSelected, clearError, sendData, forceSaveValid, moveAllToSuccess se mantienen igual) ...
            
            removeAggregate(itemToRemove) {
                this.aggregates = this.aggregates.filter(item => item.value !== itemToRemove.value);
                this.selectedAggregates = this.selectedAggregates.filter(item => item.value !== itemToRemove.value);
            },
            deleteSelected() {
                this.aggregates = this.aggregates.filter(item => !this.selectedAggregates.includes(item));
                this.selectedAggregates = []; 
            },
            clearError(item) {
                if (item.error) item.error = null;
            },
            rowClass(data) {
                return data.error ? 'bg-red-50' : '';
            },
            sendData() {
                this.isValidated = true;
                let errorCount = 0;
                this.aggregates.forEach(item => {
                    if (!item.value || item.value.trim() === '') {
                         item.error = "El valor no puede estar vacío";
                         errorCount++;
                         return;
                    }
                    if (item.value.toLowerCase().includes('x')) {
                        item.error = "Error: Formato inválido (simulado)";
                        errorCount++;
                    } else {
                        item.error = null;
                    }
                });
                if (errorCount === 0) this.moveAllToSuccess();
            },
            forceSaveValid() {
                const validItems = this.aggregates.filter(item => item.error === null);
                this.sentAggregates.push(...validItems);
                this.aggregates = this.aggregates.filter(item => item.error !== null);
                this.selectedAggregates = []; 
            },
            moveAllToSuccess() {
                this.sentAggregates.push(...this.aggregates);
                this.aggregates = [];
                this.selectedAggregates = [];
                this.isValidated = false;
            }
        }
    }
</script>