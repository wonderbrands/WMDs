<template>
    <div class="pick_component" v-if="form_data">
        <div class="title_section">
            <h1>{{ store.main_manager_screen.form_title }} {{ form_data.name }}</h1>
        </div>
        
        <div class="form_items">
            <div v-for="col in merged_cols" :key="col.field" class="field">
                
                <FloatLabel v-if="!col.non_blocked_field">
                    <InputText disabled :id="col.field" 
                        :value="col.field.includes('date') ? store.formatDate(form_data[col.field]) : form_data[col.field]" 
                        class="w-full" />
                    <label :for="col.field">{{ col.label }}</label>
                </FloatLabel>
                
                <FloatLabel v-else-if="col.type === 'text'">
                    <InputText :id="col.field" :name="col.field" type="text" autocomplete="off" v-model="form_data[col.field]" class="w-full" />
                    <label :for="col.field">{{ col.label }}</label>
                </FloatLabel>

                <FloatLabel v-else-if="col.type === 'multiselect'">
                    <MultiSelect v-model="form_data[col.field]" 
                        :id="col.field"
                        :options="optionsCache[col.source]" 
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
                
                <FloatLabel v-else>
                    <Select v-model="form_data[col.field]" 
                        :id="col.field"
                        :options="optionsCache[col.source]" 
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

                nonBlockedCols.forEach(col => {
                    if (col.type !== 'multiselect' && col.type !== 'text' && this.optionsCache[col.source]) {
                        data[col.field] = this.optionsCache[col.source].find(opt => opt.id === data[col.field]);
                    }
                });

                let saved = await this.store.callOdoo(formConfig.save_context, "", data);
                
                if (saved.saved && formConfig.on_save_actions) {
                    for (const action of formConfig.on_save_actions) {
                        let params = { ...action.params };
                        for (const key in params) {
                            if (typeof params[key] === 'string') {
                                params[key] = params[key].replace(/{id}/g, data.id);
                                params[key] = params[key].replace(/{name}/g, data.name);
                                params[key] = params[key].replace(/{user_email}/g, this.store.role.email);
                                if (data.responsible && data.responsible.name) {
                                    params[key] = params[key].replace(/{responsible.name}/g, data.responsible.name);
                                }
                            }
                        }
                        await this.store.callOdoo(action.context, "", params);
                    }
                    this.store.closeModal();
                }
            }
        },
        async mounted() {
            const formConfig = this.store.main_manager_screen.form_config;
            const frontendCols = this.store.main_manager_screen.map_columns || [];
            
            this.form_data = { ...this.store.form_context.data };
            delete this.form_data.map_cols;
            
            this.merged_cols = frontendCols.map(col => {
                return {
                    field: col.name,
                    label: col.label,
                    non_blocked_field: col.non_blocked_field || false,
                    source: col.source || null,
                    type: col.type || null
                };
            });

            for (const col of this.merged_cols) {
                if (col.source && !this.optionsCache[col.source]) {
                    this.optionsCache[col.source] = [];
                }
            }

            const nonBlockedCols = this.merged_cols.filter(col => col.non_blocked_field);
            
            for (const col of nonBlockedCols) {
                await this.loadOptions("*", col.source);
            }
            
            nonBlockedCols.forEach(col => {
                if (col.type === 'multiselect' && Array.isArray(this.form_data[col.field])) {
                    if (this.form_data[col.field].length > 0 && typeof this.form_data[col.field][0] === 'object') {
                        const existing = this.optionsCache[col.source] || [];
                        const merged = [...existing, ...this.form_data[col.field]];
                        const unique = [];
                        const map = new Map();
                        for (const item of merged) {
                            if (item && item.id && !map.has(item.id)) {
                                map.set(item.id, true);
                                unique.push(item);
                            }
                        }
                        this.optionsCache[col.source] = unique;
                        this.form_data[col.field] = this.form_data[col.field].map(item => item.id || item);
                    }
                } else if (this.form_data[col.field] && typeof this.form_data[col.field] === 'object' && !Array.isArray(this.form_data[col.field]) && this.form_data[col.field].id) {
                    const existing = this.optionsCache[col.source] || [];
                    if (!existing.find(i => i.id === this.form_data[col.field].id)) {
                        this.optionsCache[col.source] = [...existing, { ...this.form_data[col.field] }];
                    }
                    this.form_data[col.field] = this.form_data[col.field].id;
                }
            });
            
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

/* Fix for FloatLabel with Select overlapping */
.field :deep(.p-floatlabel label) {
    z-index: 1;
    pointer-events: none;
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

/* Ensure Select label floats correctly in PrimeVue 4 */
:deep(.p-floatlabel:has(.p-select-overlay-visible) label),
:deep(.p-floatlabel:has(.p-multiselect-overlay-visible) label),
:deep(.p-floatlabel:has(.p-inputwrapper-filled) label) {
    top: -0.75rem;
    font-size: 12px;
}
</style>