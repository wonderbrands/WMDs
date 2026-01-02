<template>
    <BackButton where="role_picker"/>
    <ModalContextComponent v-if="store.modal_open"/>
    <div class="manager_screen">
        <h1>Elige la actividad que deseas realizar</h1>
        <Button label="Asignar ingreso" @click="store.openModal('ingreso')"/>
        <Button label="Disponibilizar inventario (traslado desde ingreso a ubicación)"/>
        <Button label="Asignar traslado"/>
        <Button label="Asignar conteo cíclico"/>
        <Button label="Crear Plan de Pickeo"/>
        <Button label="Ver actividades pendientes"/>
    </div>
</template>
<script>
    import Button from 'primevue/button';
    import BackButton from '../BackButton/BackButton.vue';
    import ModalContextComponent from '../ModalContextComponent/ModalContextComponent.vue';
    import { useGeneralStore } from "../../store/index"
    export default {
        name: "ManagerComponent", 
        data: function() {
            return {
                store: useGeneralStore()
            }
        },
        mounted (){
            if(this.store.current_role != "manager") {
                this.store.current_screen = "role_picker"
            } else{
                this.store.currentScreenLoaded()
            }

        },
        components: {
            Button,
            BackButton,
            ModalContextComponent
        }
    }
</script>