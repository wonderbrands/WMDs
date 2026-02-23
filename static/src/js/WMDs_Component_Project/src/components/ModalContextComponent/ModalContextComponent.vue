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
                <!--
                <div v-else-if="store.modal_context === 'disponibilizar'">
                <ul>
                    <li v-for="product in [{id: 1, name: 'Cama madera', qty: 2}, {id: 2, name: 'Bolsa', qty: 3}, {id: 3, name: 'Cama metal', qty: 1}]" :key="product.id">
                        {{ product.name }} - {{ product.qty }}
                    </li>
                </ul>
                <Button label="Asignar" @click="store.disponibilizarProducts(store.modal_context_products)" rounded/>
                </div>
                <div v-else-if="store.modal_context === 'traslado'">
                <ul>
                    <li v-for="product in store.modal_context_products" :key="product.id">
                        {{ product.name }} - {{ product.qty }}
                    </li>
                </ul>
                <Button label="asignar" @click="store.trasladarProducts(store.modal_context_products)" rounded/>
                </div>-->
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