<template>
  <article class="main_manager_screen">
    <ListView v-if="['ingreso', 'disponibilizar', 'traslado', 'pick', 'devolucion', 'resurtido', 'batch_pick'].includes(store.main_manager_screen.value)"/>
  </article>
</template>

<script >
    import { useGeneralStore } from "../../store/index"
    import ListView from './ListView.vue'
    export default {
    name: 'MainManagerScreen',

    data() {
        return {
            store: useGeneralStore(),
        };
    },

    mounted() {
    },

    methods: {
        
    },
    components: {
        ListView
    }
    }
</script>