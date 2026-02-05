<template>
    <div>
        <div class="mb-6 p-4 border-round-xl surface-card shadow-1">
            <h3 class="mt-0 mb-3 text-700">1. Carga de Datos</h3>
            
            <div v-if="creation.create_by_aggregate.extra_fields" class="grid formgrid mb-4">
                <div v-for="field in creation.create_by_aggregate.extra_fields" :key="field.name" class="col-12 md:col-6">
                    <label class="block text-sm font-medium mb-2">{{ field.label }}</label>
                    
                    <Select 
                        v-if="field.type === 'selectable'"
                        v-model="extraValues[field.name]" 
                        :options="optionsCache[field.source]" 
                        :optionLabel="field.optionLabel || 'name'"
                        :optionValue="field.optionValue || 'id'"
                        :placeholder="'Selecciona ' + field.label" 
                        class="w-full"
                        :class="{'p-invalid': field.required && !extraValues[field.name] && triedToSave}"
                        filter
                    />

                    <InputText 
                        v-else
                        v-model="extraValues[field.name]"
                        class="w-full"
                    />
                </div>
            </div>

            <div class="mb-4">
                <FloatLabel>
                    <Textarea id="aggregate" 
                        v-model="creation.create_by_aggregate.input_aggregate_data" 
                        @keyup.enter="splitInput"
                        rows="1"
                        class="w-full"
                        style="resize: none; overflow-y: auto; height: 45px; padding-top: 10px;" 
                    />
                    <label for="aggregate">
                        {{ creation.create_by_aggregate.input_aggregate_instructions }}
                    </label>
                </FloatLabel>  
                <small class="text-gray-500">Pega la columna y presiona <b>Enter</b>.</small>
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
                <Button v-else label="Guardar" icon="pi pi-exclamation-triangle" severity="warning" @click="forceSaveValid" />
                <Button label="Validar" icon="pi pi-send" @click="sendData" :severity="hasErrors ? 'secondary' : 'primary'" />
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
    import Textarea from 'primevue/textarea';
    import FloatLabel from 'primevue/floatlabel';
    import DataTable from 'primevue/datatable';
    import Column from 'primevue/column';
    import Button from 'primevue/button';
    import Tooltip from 'primevue/tooltip';
    import Select from 'primevue/select';
    import { useGeneralStore } from "../../store/index"

    export default {
        name: "AggregateCreation", 
        components: { InputText, Textarea, FloatLabel, DataTable, Column, Button, Select },
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
                isValidated: false,
                extraValues: {},
                optionsCache: {},
                triedToSave: false      
            }
        },
        computed: {
            hasErrors() {
                return this.aggregates.some(item => item.error !== null);
            }
        },
        async mounted() {
            await this.loadExtraFieldOptions();
        },
        methods: {
            async loadExtraFieldOptions() {
                const fields = this.creation.create_by_aggregate.extra_fields || [];
                
                for (const field of fields) {
                    if (field.type === 'selectable' && field.source) {
                        this.store.loading = true;
                        const results = await this.store.odoo_middleware.getFromOdoo(
                            field.source, 
                            ""
                        );
                        this.optionsCache[field.source] = results || [];
                        this.store.loading = false;
                    }
                }
            },
            splitInput() {
                const text = this.creation.create_by_aggregate.input_aggregate_data;
                console.log("Texto recibido:", text); 

                if (!text || text.trim().length === 0) return;

                const splitRegex = /[\r\n\t]+/; 

                const rawValues = text
                    .split(splitRegex)        
                    .map(i => i.trim())       
                    .filter(i => i !== '');   

                console.log("Elementos detectados:", rawValues);

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
            async sendData() {
                this.store.loading = true;
                this.isValidated = true;
                let errorCount = 0;
                let server_Validaton = null;
                this.aggregates.forEach(item => {
                    if (!item.value || item.value.trim() === '') {
                         item.error = "El valor no puede estar vacío";
                         errorCount++;
                         return;
                    }
                });
                
                for (const item of this.aggregates) {
                    if (item.error) continue;
                    
                    server_Validaton = await this.store.odoo_middleware.getFromOdoo(
                        this.creation.create_by_aggregate.validate_item_endpoint,
                        item.value,
                        null
                    );
                    if (server_Validaton.error){
                        item.error = server_Validaton.error_msg;
                        errorCount++
                    } else {
                        item.error = null;
                    }                     
                }

                if (errorCount === 0) this.moveAllToSuccess();
                this.store.loading = false;
            },
            async forceSaveValid() {
                this.triedToSave = true;

                const fields = this.creation.create_by_aggregate.extra_fields || [];
                const missingRequired = fields.some(f => f.required && !this.extraValues[f.name]);
                
                if (missingRequired) {
                    return;
                }

                this.store.loading = true;
                const validItems = this.aggregates.filter(item => item.error === null);
                
                let server_Validaton = null;
                server_Validaton = await this.store.odoo_middleware.getFromOdoo(
                    this.creation.create_by_aggregate.save_aggregate_endpoint,
                    "", 
                    {
                        batch_create: validItems,
                        ...this.extraValues
                    }
                );

                if (!server_Validaton.error){
                    this.sentAggregates.push(...validItems);
                    this.aggregates = this.aggregates.filter(item => item.error !== null);
                    this.selectedAggregates = []; 
                    this.store.closeModal()
                } else {
                    console.error(server_Validaton.error_msg)
                } 
                this.store.loading = false;
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