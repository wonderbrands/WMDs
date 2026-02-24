<template>
    <div class="modal_context">
        <section class="modal_box">
            <div class="close_modal_button">
                <Button label="X" @click="store.closeModal()" rounded/>
            </div>
            <div style="width: 100%; height: 100%;"
            v-if="store.form_context.data.create_by_aggregate">
                <AggregateCreation 
                    :creation="store.main_manager_screen"
                    :id="store.form_context.data.form_type"/>
            </div>
            <div style="width: 100%; height: 100%;"
            v-else-if="store.form_context.data.cycle_count">
                <CycleCount/>
            </div>
            <div  style="width: 100%; height: 100%;"
            v-else>
                <IngresoComponent v-if="store.modal_context === 'ingreso'"/>
                <GenericFormView v-else-if="['pick','pack'].includes(store.modal_context)"/>
            </div>
           
        </section>
    </div>
</template>
<script>
    import Button from 'primevue/button';
    import IngresoComponent from "../Forms/IngresoComponent.vue";
    import GenericFormView from '../Forms/GenericFormView.vue';
    import AggregateCreation from '../Forms/AggregateCreation.vue';
    import CycleCount from '../Forms/CycleCount.vue';
    import { useGeneralStore } from "../../store/index";
    export default {
        name: "ModalContextComponent", 
        data: function() {
            return {
                store: useGeneralStore()
            }
        },
        components: {
            Button,
            IngresoComponent, 
            GenericFormView,
            AggregateCreation,
            CycleCount
        }
    }
</script>