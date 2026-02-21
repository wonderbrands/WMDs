<template>
    <div class="pick_component" v-if="form_data">
        <div class="title_section">
            <h1>{{ store.main_manager_screen.form_title }} {{ form_data.name }}</h1>
            <h2>{{}}</h2>
        </div>
        <div class="form_items">
            <div v-for="field in Object.keys(form_data)" :key="field" class="field">
                <FloatLabel v-if="!map_cols.filter(col => col.non_blocked_field ).map(col => col.field).includes(field)">
                    <InputText disabled :id="field" v-model="form_data[field]" :placeholder="map_cols[field]" />
                    <label :for="field">{{ map_cols.filter(col => col.field === field)[0].name }}</label>
                </FloatLabel>
                <FloatLabel v-else>
                    <Select v-model="form_data[field]" 
                        :id="field"
                        :options="options_non_blocked[field]" 
                        filter
                        :showClear="true"
                        placeholder="Selecciona un usuario para asignar" 
                        :invalid="!form_data[field]"
                        class="w-full" 
                        optionLabel="name"
                        optionValue="id">
                        
                        <template #filter="{ filterModel }">
                            <InputText 
                                v-model="filterModel.value" 
                                @input="setOptions(filterModel.value, field)"
                                placeholder="Buscar..."
                                class="w-full"
                            />
                        </template>
                    </Select>
                    <label :for="field">{{ map_cols.filter(col => col.field === field)[0].name }}</label>
                </FloatLabel>
            </div>
            <div v-if="extra_data">
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
                    </Column>
                </DataTable>
            </div>
        </div>
        <Button severity="success" label="Guardar" @click="saveForm()" />
    </div>
</template>
<script>
    import InputText from 'primevue/inputtext';
    import FloatLabel from 'primevue/floatlabel';
    import Button from 'primevue/button';
    import Select from 'primevue/select';
    import DataTable from 'primevue/datatable';
    import Column from 'primevue/column';

    import { useGeneralStore } from "../../store/index"
    export default {
        name: "GenericFormView", 
        data: function() {
            return {
                store: useGeneralStore(),
                form_data: null,
                map_cols: null,
                options_non_blocked: {},
                extra_data: null,
                filters: {
                    global: { value: null, matchMode: "contains" }
                },
            }
        },
        methods: {
            setOptions: async function(data, field) {
                const field_config = this.map_cols.find(c => c.field === field);
                if (field_config && field_config.source) {
                    this.options_non_blocked[field] = await this.store.callOdoo(field_config.source, data || "")
                }
            },
            async saveForm(){
                const formConfig = this.store.main_manager_screen.form_config;
                let data = this.form_data;

                // Re-assign data for non-blocked fields
                let non_blocked_fields = this.map_cols.filter(col => col.non_blocked_field).map(col => col.field)
                non_blocked_fields.forEach(field => {
                    data[field] = this.options_non_blocked[field].find(opt => opt.id === data[field])
                })

                let saved = await this.store.callOdoo(formConfig.save_context, "", data)
                
                if (saved.saved){
                    for (const action of formConfig.on_save_actions) {
                        let params = { ...action.params };
                        // Replace placeholders
                        for (const key in params) {
                            if (typeof params[key] === 'string') {
                                params[key] = params[key].replace(/{id}/g, data.id);
                                params[key] = params[key].replace(/{name}/g, data.name);
                                params[key] = params[key].replace(/{user_email}/g, this.store.role.email);
                                if (data.responsible) {
                                    params[key] = params[key].replace(/{responsible.name}/g, data.responsible.name);
                                }
                            }
                        }
                        await this.store.callOdoo(action.context, "", params);
                    }
                    this.store.closeModal()
                }
            }
        },
        async mounted() {
            const formConfig = this.store.main_manager_screen.form_config;

            this.map_cols = this.store.form_context.data.map_cols
            this.form_data = this.store.form_context.data
            delete this.form_data.map_cols
            
            for (const field of this.map_cols.filter(col => col.non_blocked_field).map(col => col.field)){
                await this.setOptions("", field)
            }
            
            let non_blocked_fields = this.map_cols.filter(col => col.non_blocked_field).map(col => col.field)
            non_blocked_fields.forEach(field => {
                if (this.form_data[field] && typeof this.form_data[field] === 'object' && this.form_data[field].id) {
                    this.form_data[field] = this.form_data[field].id
                }
            })
            
            if (formConfig.related_data_endpoint) {
                this.extra_data = await this.store.callOdoo(formConfig.related_data_endpoint, "", { id: this.form_data.id })
            }
        },
        components: {
            Button,
            Select,
            InputText,
            FloatLabel,
            DataTable,
            Column
        }
    }
</script>