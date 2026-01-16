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
        <Button severity="success" label="Guardar" @click="saveForm(form_data, 'assign_pick')" />
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
        name: "PickComponent", 
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
                console.log("input:", data)
                if (field === "user"){
                    this.options_non_blocked[field] = await this.store.odoo_middleware.getFromOdoo("operadores", data || "*")

                }
                console.log("users loaded:", this.options_non_blocked)
            },
            async saveForm(data, context){
                //reasign data-non blocked fields id to the object 
                let non_blocked_fields = this.map_cols.filter(col => col.non_blocked_field).map(col => col.field)
                console.log(non_blocked_fields)
                non_blocked_fields.forEach(field => {
                    if (this.options_non_blocked[field].find(opt => opt.name === data[field])){
                        data[field] = this.options_non_blocked[field].find(opt => opt.name === data[field]).id
                        console.log(data[field])
                    }
                })
                console.log(data)
                let saved = await this.store.odoo_middleware.getFromOdoo(context, "", data)
                if (saved.saved){
                    this.store.closeModal()
                }
                /*
                let required_fields = this.map_cols.filter(col => col.non_blocked_field).map(col => col.field)
                if (required_fields.some(field => !data[field])){
                    return 0;
                }
                console.log("========================")
                console.log(data)
                let saved = await this.store.odoo_middleware.getFromOdoo(context, "", data)
                Object.keys(data).forEach(key => {
                    if (data[key].name){
                        this.form_data[key] = data[key].name
                    }
                })
                console.log(saved)
                if (saved.saved){
                    this.store.closeModal()
                }*/
            }
        },
        async mounted() {
            this.map_cols = this.store.form_context.data.map_cols
            this.form_data = this.store.form_context.data
            delete this.form_data.map_cols
            
            // Load users FIRST
            for (const field of this.map_cols.filter(col => col.non_blocked_field).map(col => col.field)){
                await this.setOptions("*", field)
            }
            
            // THEN convert operator object to ID
            let non_blocked_fields = this.map_cols.filter(col => col.non_blocked_field).map(col => col.field)
            non_blocked_fields.forEach(field => {
                if (this.form_data[field] && typeof this.form_data[field] === 'object' && this.form_data[field].id) {
                    this.form_data[field] = this.form_data[field].id
                }
            })
            
            this.extra_data = await this.store.odoo_middleware.getFromOdoo("pick_products", this.form_data.id)
            
            console.log("--------mounted-------")
            console.log("form_data:", this.form_data)
            console.log("users:", this.options_non_blocked)
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