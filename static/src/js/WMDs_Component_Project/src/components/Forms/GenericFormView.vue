<template>
    <div class="pick_component" v-if="form_data">
        <div class="title_section">
            <h1>{{ store.main_manager_screen.form_title }} {{ form_data.name }}</h1>
        </div>
        
        <div class="form_items">
            <div v-for="col in merged_cols" :key="col.field" class="field">
                
                <!-- MultiSelect -->
                <FloatLabel v-if="col.type === 'multiselect'" :class="{ 'float-label-filled': hasValue(col.field) }">
                    <MultiSelect v-model="form_data[col.field]" 
                        :id="col.field"
                        :disabled="!col.non_blocked_field"
                        :options="optionsCache[col.source] || []" 
                        filter
                        dataKey="id"
                        class="w-full" 
                        display="chip"
                        optionLabel="name"
                        optionValue="id">
                        
                        <template #filter="{ filterModel }">
                            <InputText 
                                v-model="filterModel.value" 
                                @input="onSearchInput(filterModel.value, col.source)"
                                placeholder="Buscar..."
                                class="w-full"
                            />
                        </template>
                    </MultiSelect>
                    <label :for="col.field">{{ col.label }}</label>
                </FloatLabel>

                <!-- Select (Relational) -->
                <FloatLabel v-else-if="col.source" :class="{ 'float-label-filled': hasValue(col.field) }">
                    <Select v-model="form_data[col.field]" 
                        :id="col.field"
                        :disabled="!col.non_blocked_field"
                        :options="optionsCache[col.source] || []" 
                        filter
                        :showClear="true"
                        dataKey="id"
                        class="w-full" 
                        optionLabel="name"
                        optionValue="id">
                        
                        <template #filter="{ filterModel }">
                            <InputText 
                                v-model="filterModel.value" 
                                @input="onSearchInput(filterModel.value, col.source)"
                                placeholder="Buscar..."
                                class="w-full"
                            />
                        </template>
                    </Select>
                    <label :for="col.field">{{ col.label }}</label>
                </FloatLabel>
                
                <!-- InputText (Standard / Text) -->
                <FloatLabel v-else :class="{ 'float-label-filled': hasValue(col.field) }">
                    <InputText :id="col.field" 
                        :name="col.field" 
                        type="text" 
                        autocomplete="off" 
                        v-model="form_data[col.field]" 
                        :disabled="!col.non_blocked_field"
                        class="w-full" />
                    <label :for="col.field">{{ col.label }}</label>
                </FloatLabel>
                
            </div>

            <div v-if="form_data.qr_image" style="margin-top: 1rem; margin-bottom: 1.5rem; text-align: center; display: flex; justify-content: center;">
                <img :src="'data:image/png;base64,' + form_data.qr_image" alt="QR Code" style="width: 150px; height: 150px; border: 1px solid #ddd; border-radius: 8px; padding: 5px; background: white;" />
            </div>
            
            <div v-if="extra_data" class="extra-data-container">
                <h5>{{ extra_data.title }}</h5>
                <DataTable v-if="extra_data.data"
                    stripedRows 
                    :value="extra_data.data"
                    v-model:filters="filters"
                    filterDisplay="row">
                    <Column v-for="col of extra_data.map_cols" 
                        :key="col.field" 
                        :field="col.field" 
                        :header="col.name">
                        <template #body="slotProps">
                            <span v-if="col.field.includes('date')">
                                {{ store.formatDate(slotProps.data[col.field]) }}
                            </span>
                            <span v-else-if="typeof slotProps.data[col.field] === 'object' && slotProps.data[col.field] !== null">
                                {{ formatObjectValue(slotProps.data[col.field]) }}
                            </span>
                            <span v-else>
                                {{ slotProps.data[col.field] }}
                            </span>
                        </template>
                    </Column>
                </DataTable>
            </div>
        </div>
        
        <Button severity="success" label="Guardar" @click="saveForm()" class="save-button" />
    </div>
</template>

<script>
    import InputText from 'primevue/inputtext';
    import FloatLabel from 'primevue/floatlabel';
    import Button from 'primevue/button';
    import Select from 'primevue/select';
    import MultiSelect from 'primevue/multiselect';
    import DataTable from 'primevue/datatable';
    import Column from 'primevue/column';

    import { useGeneralStore } from "../../store/index"

    export default {
        name: "GenericFormView", 
        data: function() {
            return {
                store: useGeneralStore(),
                form_data: null,
                merged_cols: [],
                optionsCache: {},
                extra_data: null,
                filters: {
                    global: { value: null, matchMode: "contains" }
                },
                debounceTimeout: null
            }
        },
        methods: {
            /**
             * Formatea un objeto para mostrar su valor de manera legible
             * @param {*} value - El valor a formatear
             * @returns {string} - Valor formateado como string
             */
            formatObjectValue(value) {
                if (value === null || value === undefined) return '';
                
                if (typeof value === 'object') {
                    // Si es un array de objetos
                    if (Array.isArray(value)) {
                        return value.map(item => this.formatObjectValue(item)).join(', ');
                    }
                    
                    // Si es un objeto único
                    // Priorizar diferentes propiedades comunes
                    return value.name || 
                           value.display_name || 
                           value.email || 
                           value.login ||
                           value.reference ||
                           value.code ||
                           (value.id ? `ID: ${value.id}` : JSON.stringify(value));
                }
                
                return String(value);
            },

            /**
             * Verifica si un campo tiene valor para la animación del FloatLabel
             * @param {string} field - Nombre del campo
             * @returns {boolean} - True si el campo tiene valor
             */
            hasValue(field) {
                const val = this.form_data[field];
                if (val === null || val === undefined || val === '') return false;
                if (Array.isArray(val)) return val.length > 0;
                if (typeof val === 'object') return Object.keys(val).length > 0;
                return true;
            },

            /**
             * Obtiene el valor a mostrar para campos deshabilitados
             * @param {Object} col - Configuración de la columna
             * @returns {string} - Valor formateado para mostrar
             */
            getDisplayValue(col) {
                const val = this.form_data[col.field];
                
                // Manejo de fechas
                if (col.field && col.field.includes('date')) {
                    return this.store.formatDate(val);
                }
                
                // Manejo de objetos
                return this.formatObjectValue(val);
            },

            async loadOptions(term, source) {
                if (!source) return;
                const results = await this.store.callOdoo(source, term || "*");
                const data = results?.data || results?.results || (Array.isArray(results) ? results : []);
                
                const existing = this.optionsCache[source] || [];
                const merged = [...existing, ...data];
                
                const unique = [];
                const map = new Map();
                for (const item of merged) {
                    if (item && item.id && !map.has(item.id)) {
                        map.set(item.id, true);
                        unique.push(item);
                    }
                }
                this.optionsCache[source] = unique;
            },

            onSearchInput(term, source) {
                clearTimeout(this.debounceTimeout);
                this.debounceTimeout = setTimeout(() => {
                    this.loadOptions(term, source);
                }, 500);
            },

            async saveForm() {
                const formConfig = this.store.main_manager_screen.form_config;
                let data = { ...this.form_data };

                const nonBlockedCols = this.merged_cols.filter(col => col.non_blocked_field);

                // Procesar cada columna no bloqueada para convertir IDs a objetos
                for (const col of nonBlockedCols) {
                    if (col.type !== 'multiselect' && col.type !== 'text' && this.optionsCache[col.source]) {
                        const selectedOption = this.optionsCache[col.source].find(opt => opt.id === data[col.field]);
                        if (selectedOption) {
                            data[col.field] = selectedOption;
                        }
                    }
                }

                let saved = await this.store.callOdoo(formConfig.save_context, "", data);
                
                if (saved.saved && formConfig.on_save_actions) {
                    for (const action of formConfig.on_save_actions) {
                        let params = { ...action.params };
                        for (const key in params) {
                            if (typeof params[key] === 'string') {
                                // Reemplazar placeholders con valores reales
                                params[key] = params[key].replace(/{id}/g, data.id);
                                params[key] = params[key].replace(/{name}/g, data.name);
                                params[key] = params[key].replace(/{user_email}/g, this.store.role.email);
                                
                                // Manejar objetos anidados como responsible.name u operator.name
                                if (data.responsible && data.responsible.name) {
                                    params[key] = params[key].replace(/{responsible.name}/g, data.responsible.name);
                                }
                                if (data.operator && data.operator.name) {
                                    params[key] = params[key].replace(/{operator.name}/g, data.operator.name);
                                }
                                if (data.responsible && data.responsible.id) {
                                    params[key] = params[key].replace(/{responsible.id}/g, data.responsible.id);
                                }
                                if (data.operator && data.operator.id) {
                                    params[key] = params[key].replace(/{operator.id}/g, data.operator.id);
                                }
                            }
                        }
                        await this.store.callOdoo(action.context, "", params);
                    }
                    this.store.closeModal();
                }
            },

            async ensureOptionsLoaded(col) {
                if (col.source && col.non_blocked_field && this.optionsCache[col.source] && this.optionsCache[col.source].length === 0) {
                    await this.loadOptions("*", col.source);
                }
            },

            async normalizeFormData() {
                // Procesar cada columna para normalizar los datos
                for (const col of this.merged_cols) {
                    const val = this.form_data[col.field];
                    
                    if (val && typeof val === 'object') {
                        // MultiSelect con array de objetos
                        if (Array.isArray(val) && col.type === 'multiselect') {
                            if (val.length > 0 && typeof val[0] === 'object' && col.source) {
                                await this.ensureOptionsLoaded(col);
                                const existing = this.optionsCache[col.source] || [];
                                val.forEach(item => {
                                    if (item.id && !existing.find(i => i.id === item.id)) {
                                        existing.push(item);
                                    }
                                });
                                this.form_data[col.field] = val.map(item => item.id);
                            }
                        } 
                        // Select con objeto único
                        else if (val.id && !Array.isArray(val) && col.source) {
                            await this.ensureOptionsLoaded(col);
                            const existing = this.optionsCache[col.source] || [];
                            if (!existing.find(i => i.id === val.id)) {
                                existing.push(val);
                            }
                            this.form_data[col.field] = val.id;
                        }
                    }
                    
                    // Para campos deshabilitados con valores que no son objetos, forzar actualización
                    if (!col.non_blocked_field && val !== null && val !== undefined && val !== '') {
                        this.$nextTick(() => {
                            this.hasValue(col.field);
                        });
                    }
                }
            }
        },

        async mounted() {
            const formConfig = this.store.main_manager_screen.form_config;
            const frontendCols = this.store.main_manager_screen.map_columns || [];
            
            this.form_data = { ...this.store.form_context.data };
            delete this.form_data.map_cols;
            
            // 1. Initial columns from config
            this.merged_cols = frontendCols.map(col => ({
                field: col.name,
                label: col.label,
                non_blocked_field: col.non_blocked_field || false,
                source: col.source || null,
                type: col.type || (col.source ? 'select' : 'text')
            }));

            // 2. Add remaining fields from form_data as blocked
            const mappedFields = new Set(this.merged_cols.map(c => c.field));
            Object.keys(this.form_data).forEach(key => {
                if (!mappedFields.has(key) && !['id', 'qr_image'].includes(key) && !key.startsWith('_')) {
                    this.merged_cols.push({
                        field: key,
                        label: key.charAt(0).toUpperCase() + key.slice(1).replace(/_/g, ' '),
                        non_blocked_field: false,
                        source: null,
                        type: 'text'
                    });
                }
            });

            // 3. Initialize optionsCache
            for (const col of this.merged_cols) {
                if (col.source && !this.optionsCache[col.source]) {
                    this.optionsCache[col.source] = [];
                }
            }

            // 4. Load options for non-blocked columns
            const nonBlockedCols = this.merged_cols.filter(col => col.non_blocked_field);
            for (const col of nonBlockedCols) {
                if (col.source) {
                    await this.loadOptions("*", col.source);
                }
            }
            
            // 5. Normalize data for ALL columns (handle objects/relations)
            await this.normalizeFormData();
            
            // 6. Load extra data if configured
            if (formConfig && formConfig.related_data_endpoint) {
                this.extra_data = await this.store.callOdoo(formConfig.related_data_endpoint, "", { id: this.form_data.id });
            }
        },

        components: {
            Button,
            Select,
            MultiSelect,
            InputText,
            FloatLabel,
            DataTable,
            Column
        }
    }
</script>

<style scoped>
.pick_component {
    width: 100%;
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-direction: column;
    padding: 1em;
    padding-bottom: 3em;
    position: relative;
    overflow: hidden;
}

.title_section {
    width: 100%;
    height: 10vh;
    min-height: 80px;
    text-align: center;
}

.form_items {
    width: 100%;
    height: 100%;
    display: flex;
    flex-direction: row;
    flex-wrap: wrap;
    align-items: center;
    justify-content: center;
    align-content: flex-start;
    overflow-y: scroll;
}

.field {
    width: 50%;
    height: 10vh;
    min-width: 40px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    margin-top: 2rem;
}

.field :deep(.p-floatlabel) {
    width: 90%;
    position: relative;
    display: block;
}

.field :deep(.p-inputtext), 
.field :deep(.p-select),
.field :deep(.p-multiselect) {
    width: 100%;
}

/* Fix para FloatLabel con campos deshabilitados */
.field :deep(.p-floatlabel label) {
    transition: all 0.2s ease;
    background: transparent;
    padding: 0 0.25rem;
    pointer-events: none;
    z-index: 1;
}

.field :deep(.p-floatlabel.float-label-filled label),
.field :deep(.p-floatlabel:has(.p-inputwrapper-filled) label),
.field :deep(.p-floatlabel:has(.p-inputtext:not(:placeholder-shown)) label),
.field :deep(.p-floatlabel:has(input:not([value=""])) label),
.field :deep(.p-floatlabel:has(input[value]:not([value=""])) label),
.field :deep(.p-floatlabel:has(.p-inputtext:disabled[value]:not([value=""])) label) {
    top: -0.75rem;
    font-size: 12px;
    background: white;
    padding: 0 0.25rem;
}

/* Para campos deshabilitados con valor */
.field :deep(.p-floatlabel:has(input:disabled) label) {
    background: #f5f5f5;
}

.save-button {
    width: 20vw;
    height: 7vh;
    position: fixed;
    right: 2vw;
    bottom: 2vh;
    z-index: 5;
}

.extra-data-container {
    width: 100%;
    margin-top: 2rem;
}

/* Asegurar que los campos deshabilitados tengan un estilo consistente */
.field :deep(.p-inputtext:disabled) {
    background-color: #f5f5f5;
    opacity: 0.8;
}

/* Responsive para pantallas pequeñas */
@media (max-width: 768px) {
    .field {
        width: 100%;
    }
    
    .save-button {
        width: 40vw;
    }
}
</style>