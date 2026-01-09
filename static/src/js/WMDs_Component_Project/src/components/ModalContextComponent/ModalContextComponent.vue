<template>
    <div class="modal_context">
        <section class="modal_box">
            <div class="close_modal_button">
                <Button label="X" @click="store.closeModal()" rounded/>
            </div>
            <IngresoComponent v-if="store.modal_context === 'ingreso'"/>
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
            </div>
            <PickComponent v-else-if="store.modal_context === 'pick'"/>
        </section>
    </div>
</template>
<script>
    import Button from 'primevue/button';
    import IngresoComponent from "../Forms/IngresoComponent.vue";
    import PickComponent from '../Forms/PickComponent.vue';
;
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
            IngresoComponent, 
            PickComponent
        }
    }
</script>