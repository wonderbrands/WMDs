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
                        :class="{'p-invalid': field.required && !extraValues[field.name] && triedToSave}"
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
                    <label for="aggregate">{{ creation.create_by_aggregate.input_aggregate_instructions }}</label>
                </FloatLabel>  
                <small class="text-gray-500">Pega la columna y presiona <b>Enter</b>.</small>
            </div>

            <div class="flex justify-between align-items-center mb-2" v-if="aggregates.length > 0">
                <span class="text-sm text-gray-600">{{ aggregates.length }} elementos en lista</span>
                <Button 
                    v-if="selectedAggregates.length > 0"
                    :label="'Borrar (' + selectedAggregates.length + ')'" 
                    icon="pi pi-trash" 
                    severity="danger" 
                    outlined size="small"
                    @click="deleteSelected"
                />
            </div>

            <DataTable 
                :value="aggregates" 
                v-model:selection="selectedAggregates" 
                selectionMode="multiple" 
                :metaKeySelection="false"
                dataKey="value"
                v-if="aggregates.length > 0"
                class="mb-4"
                :rowClass="rowClass"
            >
                <Column selectionMode="multiple" headerStyle="width: 3rem"></Column>
                <Column header="Dato (Editable)">
                    <template #body="slotProps">
                        <InputText 
                            v-model="slotProps.data.value" 
                            class="w-full p-inputtext-sm"
                            :class="{'p-invalid': slotProps.data.error}"
                            @input="onInputChange(slotProps.data)"
                        />
                    </template>
                </Column>
                <Column header="Estado / Errores">
                    <template #body="slotProps">
                        <span v-if="slotProps.data.error" class="text-red-600 font-bold text-sm flex align-items-center gap-2">
                            <i class="pi pi-exclamation-circle"></i> {{ slotProps.data.error }}
                        </span>
                        <span v-else-if="slotProps.data.validated" class="text-green-600 font-bold text-sm flex align-items-center gap-2">
                            <i class="pi pi-check-circle"></i> Listo para guardar
                        </span>
                        <span v-else class="text-gray-400 text-sm">Pendiente de validar...</span>
                    </template>
                </Column>
                <Column header="Acciones" headerStyle="width: 5rem; text-align: center">
                    <template #body="slotProps">
                        <Button icon="pi pi-trash" severity="danger" text rounded @click="removeAggregate(slotProps.data)" />
                    </template>
                </Column>
            </DataTable>

            <div class="flex justify-end gap-2" v-if="aggregates.length > 0">
                <template v-if="hasValidatedItems">
                    <Button 
                        v-if="hasErrors" 
                        label="Guardar válidos (ignorar errores)" 
                        icon="pi pi-save" 
                        severity="warning" 
                        @click="saveValidRecords" 
                        v-tooltip="'Guardar solo los verdes'" 
                    />
                    <Button 
                        v-else 
                        label="Confirmar y Guardar Todo" 
                        icon="pi pi-check-square" 
                        severity="success" 
                        @click="saveValidRecords" 
                    />
                </template>
                
                <Button 
                    label="Validar Datos" 
                    icon="pi pi-send" 
                    @click="validateData" 
                    :severity="isValidated ? 'secondary' : 'primary'" 
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
            },
            hasValidatedItems() {
                return this.aggregates.some(item => item.validated && !item.error);
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
                        const results = await this.store.odoo_middleware.getFromOdoo(field.source, "");
                        this.optionsCache[field.source] = results || [];
                        this.store.loading = false;
                    }
                }
            },
            splitInput() {
                const text = this.creation.create_by_aggregate.input_aggregate_data;
                if (!text || text.trim().length === 0) return;
                const rawValues = text.split(/[\r\n\t]+/).map(i => i.trim()).filter(i => i !== ''); 

                rawValues.forEach(val => {
                    if (!this.aggregates.some(agg => agg.value === val) && !this.sentAggregates.some(agg => agg.value === val)) {
                        this.aggregates.push({ value: val, error: null, validated: false });
                    }
                });
                this.creation.create_by_aggregate.input_aggregate_data = '';
                this.isValidated = false; 
            },
            async validateData() {
                this.store.loading = true;
                this.isValidated = true;
                
                for (const item of this.aggregates) {
                    if (!item.value || item.value.trim() === '') {
                         item.error = "El valor no puede estar vacío";
                         item.validated = false;
                         continue;
                    }

                    const serverValidation = await this.store.odoo_middleware.getFromOdoo(
                        this.creation.create_by_aggregate.validate_item_endpoint,
                        item.value,
                        null
                    );
                    
                    if (serverValidation.error){
                        item.error = serverValidation.error_msg;
                        item.validated = false;
                    } else {
                        item.error = null;
                        item.validated = true; // Marcamos como listo
                    }                     
                }
                this.store.loading = false;
            },
            // MÉTODO DE GUARDADO: Ejecución manual
            async saveValidRecords() {
                this.triedToSave = true;

                // Validación de campos extra
                const fields = this.creation.create_by_aggregate.extra_fields || [];
                if (fields.some(f => f.required && !this.extraValues[f.name])) return;

                const validItems = this.aggregates.filter(item => item.validated && !item.error);
                if (validItems.length === 0) return;

                this.store.loading = true;
                const response = await this.store.odoo_middleware.getFromOdoo(
                    this.creation.create_by_aggregate.save_aggregate_endpoint,
                    "", 
                    {
                        batch_create: validItems,
                        ...this.extraValues
                    }
                );

                if (!response.error){
                    this.sentAggregates.push(...validItems);
                    // Removemos de la lista de trabajo solo los que se enviaron
                    this.aggregates = this.aggregates.filter(item => !validItems.includes(item));
                    this.selectedAggregates = []; 
                    
                    if (this.aggregates.length === 0) {
                        this.store.closeModal();
                    }
                }
                this.store.loading = false;
                this.isValidated = false;
            },
            onInputChange(item) {
                item.error = null;
                item.validated = false;
                this.isValidated = false;
            },
            removeAggregate(itemToRemove) {
                this.aggregates = this.aggregates.filter(item => item.value !== itemToRemove.value);
            },
            deleteSelected() {
                this.aggregates = this.aggregates.filter(item => !this.selectedAggregates.includes(item));
                this.selectedAggregates = []; 
            },
            rowClass(data) {
                if (data.error) return 'bg-red-50';
                if (data.validated) return 'bg-green-50';
                return '';
            }
        }
    }
</script>