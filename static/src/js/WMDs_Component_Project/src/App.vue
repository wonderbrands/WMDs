<template>
  <LoadingComponent v-if="store.loading" />
  Identificado: {{ store.role.is_identified }}
  Nombre: {{ store.role.user }}
  mail {{ store.role.email }}
  <QRScannerComponent context="user_initial_scanner" 
      instructions="Escanea tu QR para iniciar sesión"
      :can_close="false"
      :onScan="store.role.getUserFromServer" 
      v-if = "!store.role.is_identified"/>
    <div v-else>
      <RolePicker v-if="store.current_screen === 'role_picker'" />
      <ManagerComponent v-else-if="store.current_screen === 'manager_screen'" />
      <OperatorComponent v-else-if="store.current_screen === 'operator_screen'"/>
    </div>
  
</template>

<script>
  import { nextTick } from "vue"
  import LoadingComponent from "./components/LoadingComponent/LoadingComponent.vue"
  import RolePicker from "./components/RolePicker/RolePicker.vue"
  import ManagerComponent from "./components/ManagerComponent/ManagerComponent.vue"
  import OperatorComponent from "./components/OperatorComponent/OperatorComponent.vue"
  import QRScannerComponent from "./components/QRScannerComponent/QRScannerComponent.vue"
  import { useGeneralStore } from "./store/index"
  
  export default {
    name: 'App',
    components: {
      LoadingComponent,
      RolePicker, 
      ManagerComponent,
      OperatorComponent,
      QRScannerComponent
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
  