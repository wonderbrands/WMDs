<template>
    <div>
        <div class="mb-6 p-4 border-round-xl surface-card shadow-1">
            
            <div class="mb-4">
                <FloatLabel>
                    <InputText id="aggregate" 
                    v-model="creation.create_by_aggregate.input_aggregate_data" 
                    :placeholder="creation.create_by_aggregate.input_aggregate_instructions" 
                    @keyup.enter="splitInput"
                    class="w-full"
                    />
                    <label for="aggregate">
                        {{ creation.create_by_aggregate.input_aggregate_instructions }}
                    </label>
                </FloatLabel>  
                <small class="text-gray-500">Tip: Escribe una "x" para simular error.</small>
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
                        <span v-else class="text-gray-400 text-sm">
                            ...
                        </span>
                    </template>
                </Column>

                <Column header="Acciones" headerStyle="width: 5rem; text-align: center" bodyStyle="text-align: center">
                    <template #body="slotProps">
                        <Button 
                            icon="pi pi-trash" 
                            severity="danger" 
                            text 
                            rounded 
                            aria-label="Eliminar" 
                            @click="removeAggregate(slotProps.data)" 
                        />
                    </template>
                </Column>
            </DataTable>

            <div class="flex justify-end gap-2" v-if="aggregates.length > 0">
                <Button 
                    v-if="hasErrors"
                    label="Guardar ignorando errores" 
                    icon="pi pi-exclamation-triangle" 
                    severity="warning"
                    @click="forceSaveValid" 
                    v-tooltip="'Guardar solo los verdes y dejar los rojos aquí'"
                />
                <Button 
                    label="Validar y Enviar" 
                    icon="pi pi-send" 
                    @click="sendData" 
                    :severity="hasErrors ? 'secondary' : 'primary'"
                />
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
                        <span class="inline-flex align-items-center border-round px-2 py-1 bg-green-100 text-green-700 text-sm font-bold">
                            Enviado
                        </span>
                    </template>
                </Column>
            </DataTable>
        </div>

    </div>
</template>

<script>
    import InputText from 'primevue/inputtext';
    import FloatLabel from 'primevue/floatlabel';
    import DataTable from 'primevue/datatable';
    import Column from 'primevue/column';
    import Button from 'primevue/button';
    import Tooltip from 'primevue/tooltip';
    import { useGeneralStore } from "../../store/index"

    export default {
        name: "AggregateCreation", 
        components: { InputText, FloatLabel, DataTable, Column, Button },
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
                console.log("Texto crudo recibido:", text);

                if (!text || text.trim().length === 0) {
                    console.log("Texto vacío. Saliendo de splitInput.");
                    return;
                }

                const CANDIDATE_SEPARATORS = [
                    { char: '\n', label: 'Salto' }, { char: '\t', label: 'Tab' },
                    { char: ',',  label: 'Coma' }, { char: ';',  label: 'Punto y coma' },
                    { char: '|',  label: 'Pipe' }
                ];
                let maxCount = 0;
                let winner = '\n';
                
                console.log("Analizando separadores...");
                CANDIDATE_SEPARATORS.forEach(sep => {
                    const count = text.split(sep.char).length - 1;
                    if (count > maxCount) { maxCount = count; winner = sep.char; }
                });
                console.log("Separador ganador:", winner, "con ocurrencias:", maxCount);

                let separatorRegex = winner;
                if (text.includes('\n') && text.includes('\t')) {
                    console.log("Detectada mezcla de Tab y Enter (Excel mode)");
                    separatorRegex = /[\n\t]+/; 
                }

                const rawValues = text.split(separatorRegex).map(i => i.trim()).filter(i => i !== ''); 
                console.log("Valores parseados:", rawValues);

                let addedCount = 0;
                rawValues.forEach(val => {
                    const existsInPending = this.aggregates.some(agg => agg.value === val);
                    const existsInSent = this.sentAggregates.some(agg => agg.value === val);
                    
                    if (!existsInPending && !existsInSent) {
                        this.aggregates.push({ value: val, error: null });
                        addedCount++;
                    } else {
                        console.log("Valor duplicado omitido:", val);
                    }
                });
                console.log("Total nuevos elementos agregados:", addedCount);

                this.creation.create_by_aggregate.input_aggregate_data = '';
                this.isValidated = false; 
                console.log("Limpieza completada. Estado isValidated reset a false.");
            },

            removeAggregate(itemToRemove) {
                console.log("Intentando eliminar item:", itemToRemove.value);
                this.aggregates = this.aggregates.filter(item => item.value !== itemToRemove.value);
                this.selectedAggregates = this.selectedAggregates.filter(item => item.value !== itemToRemove.value);
                console.log("Item eliminado. Restantes:", this.aggregates.length);
            },

            deleteSelected() {
                console.log("--- INICIO deleteSelected ---");
                console.log("Cantidad a borrar:", this.selectedAggregates.length);
                this.aggregates = this.aggregates.filter(item => !this.selectedAggregates.includes(item));
                this.selectedAggregates = []; 
                console.log("Borrado masivo completado. Restantes:", this.aggregates.length);
            },

            clearError(item) {
                console.log("Editando item:", item.value);
                if (item.error) {
                    console.log("Limpiando error previo:", item.error);
                    item.error = null;
                }
            },

            rowClass(data) {
                return data.error ? 'bg-red-50' : '';
            },

            sendData() {
                console.log("--- INICIO sendData (Validación) ---");
                this.isValidated = true;
                let errorCount = 0;
                
                console.log("Validando", this.aggregates.length, "elementos...");
                this.aggregates.forEach(item => {
                    if (!item.value || item.value.trim() === '') {
                         console.log("Error encontrado: Valor vacío");
                         item.error = "El valor no puede estar vacío";
                         errorCount++;
                         return;
                    }

                    if (item.value.toLowerCase().includes('x')) {
                        console.log("Error simulado encontrado en:", item.value);
                        item.error = "Error: Formato inválido (simulado)";
                        errorCount++;
                    } else {
                        item.error = null;
                    }
                });

                console.log("Total errores encontrados:", errorCount);

                if (errorCount === 0) {
                    console.log("Validación exitosa (0 errores). Moviendo todo a success.");
                    this.moveAllToSuccess();
                } else {
                    console.log("Validación fallida. Se requiere acción del usuario.");
                }
            },

            forceSaveValid() {
                console.log("--- INICIO forceSaveValid ---");
                const validItems = this.aggregates.filter(item => item.error === null);
                console.log("Elementos válidos identificados:", validItems.length);
                
                this.sentAggregates.push(...validItems);
                
                this.aggregates = this.aggregates.filter(item => item.error !== null);
                console.log("Elementos inválidos que se quedan:", this.aggregates.length);
                
                this.selectedAggregates = []; 
                console.log("Guardado forzoso completado.");
            },

            moveAllToSuccess() {
                console.log("Moviendo todos los items a la tabla de enviados...");
                this.sentAggregates.push(...this.aggregates);
                this.aggregates = [];
                this.selectedAggregates = [];
                this.isValidated = false;
                console.log("Movimiento completado. Tabla aggregates vacía.");
            }
        }
    }
</script>