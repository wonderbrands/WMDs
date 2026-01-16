<template>
    <div class="pick_component" v-if="form_data">
        <div class="title_section">
            <h1>{{ store.main_manager_screen.form_title }} {{ form_data.name }}</h1>
        </div>

        <div class="form_items">
            <div
                v-for="field in Object.keys(form_data)"
                :key="field"
                class="field"
            >
                <!-- READ ONLY FIELDS -->
                <FloatLabel
                    v-if="!map_cols.filter(col => col.non_blocked_field).map(col => col.field).includes(field)"
                >
                    <InputText
                        disabled
                        :id="field"
                        v-model="form_data[field]"
                    />
                    <label :for="field">
                        {{ map_cols.find(col => col.field === field)?.name }}
                    </label>
                </FloatLabel>

                <!-- SELECTABLE FIELDS -->
                <FloatLabel v-else>
                    <Select
                        v-model="form_data[field]"
                        :id="field"
                        :options="users"
                        optionLabel="name"
                        optionValue="null"
                        filter
                        showClear
                        placeholder="Selecciona un usuario para asignar"
                        :invalid="!form_data[field]"
                        class="w-full"
                        @change="onSelectChange(field)"
                    >
                        <template #filter="{ filterModel }">
                            <InputText
                                v-model="filterModel.value"
                                @input="setOptionsUser(filterModel.value)"
                                placeholder="Buscar..."
                                class="w-full"
                            />
                        </template>
                    </Select>

                    <label :for="field">
                        {{ map_cols.find(col => col.field === field)?.name }}
                    </label>
                </FloatLabel>
            </div>

            <!-- EXTRA DATA -->
            <div v-if="extra_data">
                <h5>{{ extra_data.title }}</h5>

                <DataTable
                    v-if="extra_data.data"
                    stripedRows
                    :value="extra_data.data"
                >
                    <Column
                        v-for="col of extra_data.map_cols"
                        :key="col.field"
                        :field="col.field"
                        :header="col.name"
                    />
                </DataTable>
            </div>
        </div>

        <Button
            severity="success"
            label="Guardar"
            @click="saveForm(form_data, 'assign_pick')"
        />
    </div>
</template>

<script>
import InputText from 'primevue/inputtext'
import FloatLabel from 'primevue/floatlabel'
import Button from 'primevue/button'
import Select from 'primevue/select'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'

import { useGeneralStore } from "../../store/index"

export default {
    name: "PickComponent",

    data() {
        return {
            store: useGeneralStore(),
            form_data: null,
            map_cols: null,
            users: [],
            extra_data: null
        }
    },

    methods: {
        async setOptionsUser(search) {
            console.log("🔍 Searching users with:", search)

            this.users = await this.store.odoo_middleware.getFromOdoo(
                "operadores",
                search || "*"
            )

            console.log("✅ Users loaded from server:", this.users)

            console.log(
                "🎯 Current selected value:",
                this.form_data?.operator
            )
        },

        onSelectChange(field) {
            console.log("🟢 Select changed")
            console.log("Field:", field)
            console.log("Selected object:", this.form_data[field])
        },

        async saveForm(data, context) {
            console.log("💾 Save button clicked")
            console.log("Form data before validation:", data)

            const requiredFields = this.map_cols
                .filter(col => col.non_blocked_field)
                .map(col => col.field)

            if (requiredFields.some(field => !data[field])) {
                console.warn("❌ Missing required fields")
                return
            }

            console.log("📤 Sending to backend:", data)

            const response = await this.store.odoo_middleware.getFromOdoo(
                context,
                "",
                data
            )

            console.log("📥 Backend response:", response)

            if (response?.saved) {
                console.log("✅ Save successful, closing modal")
                this.store.closeModal()
            }
        }
    },

    async mounted() {
        console.log("🚀 Component mounted")

        this.map_cols = this.store.form_context.data.map_cols
        this.form_data = this.store.form_context.data

        delete this.form_data.map_cols

        console.log("📋 Initial form data:", this.form_data)
        console.log("🗺️ Map columns:", this.map_cols)

        // Load users FIRST
        await this.setOptionsUser("*")

        console.log("👤 Users after initial load:", this.users)
        console.log("🎯 Default selected operator:", this.form_data.operator)

        // Load extra data
        this.extra_data = await this.store.odoo_middleware.getFromOdoo(
            "pick_products",
            this.form_data.id
        )

        console.log("📦 Extra data loaded:", this.extra_data)
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
