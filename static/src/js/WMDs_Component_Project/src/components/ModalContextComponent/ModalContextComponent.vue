<template>
    <div class="modal_context">
        <section class="modal_box">
            <div class="close_modal_button">
                <Button 
                    icon="fa fa-refresh" 
                    @click="store.triggerRefresh()" 
                    rounded 
                    severity="secondary" 
                    outlined
                    class="close-btn-styled mr-2"
                    title="Refrescar vista"
                />
                <Button 
                    icon="fa fa-times" 
                    @click="store.closeModal()" 
                    rounded 
                    severity="danger" 
                    outlined
                    class="close-btn-styled"
                />
            </div>
            <div style="width: 100%; height: 100%;"
            v-if="store.form_context.data.create_by_aggregate">
                <AggregateCreation 
                    :key="store.refreshKey"
                    :creation="store.main_manager_screen"
                    :id="store.form_context.data.form_type"/>
            </div>
            <div style="width: 100%; height: 100%;"
            v-else-if="store.form_context.data.cycle_count || store.modal_context === 'cycle_count_management'">
                <CycleCount :key="store.refreshKey"/>
            </div>
            <div style="width: 100%; height: 100%;"
            v-else-if="store.modal_context === 'batch_pick'">
                <BatchDetailView :key="store.refreshKey"/>
            </div>
            <div  style="width: 100%; height: 100%;"
            v-else>
                <IngresoComponent v-if="store.modal_context === 'ingreso'" :key="store.refreshKey"/>
                <GenericFormView v-else-if="['pick','pack','operator_definition'].includes(store.modal_context)" :key="store.refreshKey"/>
            </div>
           
        </section>
    </div>
</template>
<script>
    import Button from 'primevue/button';
    import IngresoComponent from "../Forms/IngresoComponent.vue";
    import GenericFormView from '../Forms/GenericFormView.vue';
    import AggregateCreation from '../Forms/AggregateCreation.vue';
    import BatchDetailView from '../Forms/BatchDetailView.vue';
    import CycleCount from '../Forms/CycleCount.vue';
    import { useGeneralStore } from "../../store/index";
    export default {
        name: "ModalContextComponent", 
        data: function() {
            return {
                store: useGeneralStore()
            }
        },
        mounted() {
            window.addEventListener('keydown', this.handleKeydown);
        },
        beforeUnmount() {
            window.removeEventListener('keydown', this.handleKeydown);
        },
        methods: {
            handleKeydown(event) {
                if (event.key === 'Escape') {
                    this.store.closeModal();
                }
            }
        },
        components: {
            Button,
            IngresoComponent, 
            GenericFormView,
            AggregateCreation,
            BatchDetailView,
            CycleCount
        }
    }
</script>

<style scoped>
.modal_context {
    position: fixed;
    top: 0;
    left: 0;
    width: 100vw;
    height: 100vh;
    background-color: rgba(0, 0, 0, 0.6);
    display: flex;
    justify-content: center;
    align-items: center;
    z-index: 400; /* Below LoadingComponent (500) */
}

.modal_box {
    background-color: white;
    width: 95%;
    max-width: 1400px;
    height: 90%;
    max-height: 95vh;
    border-radius: 12px;
    position: relative;
    padding: 1.5rem;
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3);
    overflow-y: auto;
    display: flex;
    flex-direction: column;
}

.close_modal_button {
    position: absolute;
    top: 1rem;
    right: 1.5rem;
    z-index: 100;
}

.close-btn-styled {
    width: 2.5rem !important;
    height: 2.5rem !important;
    background: white !important;
    box-shadow: 0 2px 8px rgba(0,0,0,0.2);
}

.close-btn-styled:hover {
    background: #f8d7da !important;
}
</style>