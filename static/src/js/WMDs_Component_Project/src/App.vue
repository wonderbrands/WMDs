<template>
  <LoadingComponent v-if="store.loading" />

  <RolePicker v-if="store.current_screen === 'role_picker'" />
  <ManagerComponent v-else-if="store.current_screen === 'manager_screen'" />
  <OperatorComponent v-else-if="store.current_screen === 'operator_screen'"/>
</template>

<script>
  import { nextTick } from "vue"
  import LoadingComponent from "./components/LoadingComponent/LoadingComponent.vue"
  import RolePicker from "./components/RolePicker/RolePicker.vue"
  import ManagerComponent from "./components/ManagerComponent/ManagerComponent.vue"
  import OperatorComponent from "./components/OperatorComponent/OperatorComponent.vue"
  import { useGeneralStore } from "./store/index"
  
  export default {
    name: 'App',
    components: {
      LoadingComponent,
      RolePicker, 
      ManagerComponent,
      OperatorComponent
    },
    data() {
      return {
        store: useGeneralStore()
      }
    },
  
    watch: {
      "store.current_screen"(newVal) {
        if (newVal === "operator_screen") {
          nextTick(() => {
            this.store.loading = false
          })
        }
      }
    }
  }
  </script>
  