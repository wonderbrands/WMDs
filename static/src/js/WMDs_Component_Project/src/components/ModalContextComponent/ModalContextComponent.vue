<template>
    <div class="modal_context">
        <section class="modal_box">
            <div class="close_modal_button">
                <Button label="X" @click="store.closeModal()" rounded/>
            </div>
            <IngresoComponent v-if="store.modal_context === 'ingreso'"/>
        </section>
    </div>
</template>
<script>
    import Button from 'primevue/button';
    import IngresoComponent from "../Forms/IngresoComponent.vue";
    import { useGeneralStore } from "../../store/index"
    export default {
        name: "ModalContextComponent", 
        data: function() {
            return {
                store: useGeneralStore()
            }
        },
        components: {
            Button,
            IngresoComponent
        }
    }
</script>