<template>
    <div class="">
        <Select v-model="ingreso" 
        editable 
        :options="ingresos_pendientes" 
        optionLabel="name" 
        placeholder="Selecciona un ingreso pendiente" 
        class="w-full"
        @input="setOptionsIngreso()" />

        <Select v-model="user" 
        editable 
        :options="users" 
        optionLabel="name" 
        placeholder="Selecciona un usuario para asignar" 
        class="w-full"
        @input="setOptionsUser()" />
    </div>
</template>
<script>
    import Button from 'primevue/button';
    import Select from 'primevue/select';

    import { useGeneralStore } from "../../store/index"
    export default {
        name: "IngresoComponent", 
        data: function() {
            return {
                store: useGeneralStore(),
                ingreso: null,
                user: null,
                users: [],
                ingresos_pendientes: []
            }
        },
        methods: {
            setOptionsIngreso: async function() {
                console.log(this.ingreso)
                this.ingresos_pendientes = await this.store.callOdoo("ingreso",this.ingreso)
            },
            setOptionsUser: async function() {
                console.log(this.user)
                this.users = await this.store.callOdoo("operadores",this.user)
            }
        },
        components: {
            Button,
            Select
        }
    }
</script>