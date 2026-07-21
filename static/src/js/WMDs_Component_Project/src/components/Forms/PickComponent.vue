<template>
    <div class="pick_component" v-if="form_data">
        <div class="title_section">
            <h1>{{ store.main_manager_screen.form_title }} {{ form_data.name }}</h1>
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
                        :invalid="!form_data[field]"
                        class="w-full custom-select" 
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
                    </Column>
                </DataTable>
            </div>
        </div>
        <Button severity="success" label="Guardar" @click="saveForm(form_data, 'assign_pick')" class="save-button" />
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
                if (field === "operator"){
                    this.options_non_blocked[field] = await this.store.callOdoo("operadores", data || "*")

                }
                console.log("users loaded:", this.options_non_blocked)
            },
            async saveForm(data, context){
                //reasign data-non blocked fields id to the object 
                let non_blocked_fields = this.map_cols.filter(col => col.non_blocked_field).map(col => col.field)
                console.log(non_blocked_fields)
                non_blocked_fields.forEach(field => {
                    data[field] = this.options_non_blocked[field].find(opt => opt.id === data[field])
                    console.log(data[field])
                })
                console.log(data)
                let saved = await this.store.callOdoo(context, "", data)
                if (saved.saved){
                    await this.store.callOdoo("log_record", "",
                        {
                            pick_id: data.id,
                            operator_mail: this.store.role.email,
                            message: `Traslado ${data.name} asignado a ${data.operator.name}`,
                        }
                    )
                    await this.store.callOdoo("log_record", "",
                        {
                            pick_id: data.id,
                            type: "external",
                            operator_mail: this.store.role.email,
                            message: ``,
                        }
                    )
                    
                    await this.store.callOdoo("change_status", "",
                        {
                            pick_id: data.id,
                            status: "not_started"       
                        }
                    )
                    this.store.closeModal()
                }
                
            }
        },
        async mounted() {
            this.map_cols = this.store.form_context.data.map_cols
            this.form_data = this.store.form_context.data
            delete this.form_data.map_cols
            
            for (const field of this.map_cols.filter(col => col.non_blocked_field).map(col => col.field)){
                await this.setOptions("*", field)
            }
            
            let non_blocked_fields = this.map_cols.filter(col => col.non_blocked_field).map(col => col.field)
            non_blocked_fields.forEach(field => {
                if (this.form_data[field] && typeof this.form_data[field] === 'object' && this.form_data[field].id) {
                    this.form_data[field] = this.form_data[field].id
                }
            })
            
            this.extra_data = await this.store.callOdoo("pick_products", this.form_data.id)
            
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
.field :deep(.p-select) {
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
:deep(.p-floatlabel:has(.p-inputwrapper-filled) label) {
    top: -0.75rem;
    font-size: 12px;
}

@media screen and (max-width: 768px) {
    .field {
        width: 100%;
        height: auto;
        margin-top: 1.5rem;
    }
    
    .save-button {
        width: 80%;
        height: auto;
        padding: 0.75rem;
        position: relative;
        margin: 2rem 0;
        right: auto;
        bottom: auto;
    }
    
    .title_section {
        height: auto;
        min-height: auto;
        margin-bottom: 1rem;
    }
    
    .title_section h1 {
        font-size: 1.3rem;
    }
    
    .form_items {
        height: auto;
        overflow-y: visible;
    }
}
</style>