<template>
  <LoadingComponent v-if="store.loading" />  
  <QRScannerComponent 
      context="user_initial_scanner" 
      instructions="Escanea tu QR para iniciar sesión"
      :can_close="false"
      :onScan="(data) => store.role.getUserFromServer(data)" 
      v-if="!role.is_identified"/>
    <div style="width: 100%; height: 100%;" v-else>
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
    computed: {
      role() {
          return this.store.role
        }  
    },
    beforeMount(){
      if (this.store.role.checkIfPersisted()){
        const persisted =  window.sessionStorage.getItem("wmds_logged_user");
        this.role.user = persisted.name
        this.role.permissions = persisted.permissions
        this.role.role = persisted.role
        this.role.is_identified = persisted.is_identified
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
  