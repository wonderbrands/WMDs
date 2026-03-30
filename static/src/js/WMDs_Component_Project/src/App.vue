<template>
  <Toast />
  <LoadingComponent v-if="store.loading" />

  <component 
    v-if="store.mandatory_uncompleted.component"
    :is="store.mandatory_uncompleted.component"
    v-bind="store.mandatory_uncompleted.component_props"
  />

  <QRScannerComponent 
    v-else-if="!role.is_identified"
    instructions="Escanea tu QR para iniciar sesión"
    :can_close="false"
    :onScan="handleUserScan" 
  />

  <component 
    v-else
    :is="currentScreenComponent" 
  />
</template>

<script>
import { nextTick } from "vue"
import Toast from 'primevue/toast';
import LoadingComponent from "./components/LoadingComponent/LoadingComponent.vue"
import RolePicker from "./components/RolePicker/RolePicker.vue"
import ManagerComponent from "./components/ManagerComponent/ManagerComponent.vue"
import OperatorComponent from "./components/OperatorComponent/OperatorComponent.vue"
import QRScannerComponent from "./components/QRScannerComponent/QRScannerComponent.vue"
import BarcodeScannerComponent from "./components/QRScannerComponent/BarcodeScannerComponent.vue"
import LogoutComponent from "./components/RolePicker/LogoutComponent.vue"
import BinComponent  from "./components/OperatorComponent/BinComponent.vue"
import DockComponent  from "./components/OperatorComponent/DockComponent.vue"
import DispatchComponent  from "./components/OperatorComponent/DispatchComponent.vue"
import DispatchComponentFul  from "./components/OperatorComponent/DispatchComponentFul.vue"

import { useGeneralStore } from "./store/index"

export default {
  name: 'App',
  components: {
    Toast,
    LoadingComponent,
    RolePicker,
    ManagerComponent,
    OperatorComponent,
    QRScannerComponent,
    BarcodeScannerComponent,
    LogoutComponent,
    BinComponent,
    DockComponent,
    DispatchComponent,
    DispatchComponentFul
  },
  data() {
    return {
      store: useGeneralStore()
    }
  },
  methods: {
    async handleUserScan(data) {
        try {
            this.store.loading = true;
            await this.store.role.getUserFromServer(data)
        } catch (e) {
            this.$toast.add({ severity: 'error', summary: 'Error de Autenticación', detail: e.message, life: 3000 });
        } finally {
            this.store.loading = false;
        }
    },
    restorePersistedUser(){
      const persisted = window.sessionStorage.getItem("wmds_logged_user");
      if (persisted) {
        try {
          const json_persisted = JSON.parse(persisted);
          Object.assign(this.role, json_persisted);
        } catch (e) {
          this.$toast.add({ severity: 'error', summary: 'Error de Sesión', detail: 'No se pudo restaurar la sesión anterior.', life: 3000 });
          console.error("Error al restaurar sesión:", e);
        }
      }
    },
    async skipLogIfManager(){
      let response = await this.store.callOdoo("skip_log_if_manager", "", "");
      let is_manager = response.is_manager
      let json_user = response.json_user

      if (is_manager){
        await this.handleUserScan(json_user);
      }
    }
  },

  computed: {
    role() {
      return this.store.role
    },
    currentScreenComponent() {
      const screens = {
        role_picker: 'RolePicker',
        manager_screen: 'ManagerComponent',
        operator_screen: 'OperatorComponent'
      }
      return screens[this.store.current_screen]
    }
  },
  beforeMount() {
    this.restorePersistedUser();
  },
  async mounted() {
    this.store.mandatory_uncompleted.loadFromStorage(this.role);
    if (this.store.mandatory_uncompleted.screen) {
        this.store.setCurrentScreen(this.store.mandatory_uncompleted.screen);
        return;
    }

    if (!this.store.role.is_identified) {
        this.store.loading = true;
        try {
            await this.skipLogIfManager();
        } finally {
            this.store.loading = false;
        }
    }
    
    if (this.store.role.is_identified && !this.store.current_screen) {
      this.store.setCurrentScreen('role_picker');
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

<style>
* {
    scrollbar-width: thin;
    scrollbar-color: rgba(0,0,0,.3) transparent;
}

#app {
  height: 100vh;
  width: 100vw;
  margin: 0px;
  padding: 0px;
  overflow: hidden;
}

:root {
    --p-button-primary-color: #000 !important;
    margin: 0px;
    padding: 0px;
}

body{
    margin: 0px;
    padding: 0px;
}

/* Mobile Toast Overrides */
@media screen and (max-width: 768px) {
    .p-toast {
        width: 90vw !important;
        left: 5vw !important;
        right: 5vw !important;
    }
}
</style>