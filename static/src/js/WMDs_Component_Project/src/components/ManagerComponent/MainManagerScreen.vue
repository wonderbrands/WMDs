<template>
  <article class="main_manager_screen">
    <ListView v-if="['ingreso', 'ingresos', 'disponibilizar', 'traslado', 'pick', 'pack', 'devolucion', 'resurtido', 'batch_pick', 'cycle_count', 'operator_list'].includes(store.main_manager_screen.value)"/>
    <ManualDispatch v-else-if="store.main_manager_screen.value === 'manual_dispatch'" />
    <div v-else class="home-screen">
        <h1>Bienvenido al WMDs Manager</h1>
        <p>Selecciona una opción del menú lateral para comenzar.</p>
    </div>
  </article>
</template>

<script >
    import { useGeneralStore } from "../../store/index"
    import ListView from './ListView.vue'
    import ManualDispatch from './ManualDispatch.vue'
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
          ListView,
          ManualDispatch
      }
    }
</script>

<style scoped>
.main_manager_screen {
    width: 100%;
    height: 100%;
    padding: 25px;
    display: flex;
    flex-direction: column;
    align-items: center;
}

.home-screen {
    text-align: center;
    margin-top: 5rem;
}
</style>