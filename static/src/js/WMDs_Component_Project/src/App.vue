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
import LogoutComponent from "./components/RolePicker/LogoutComponent.vue"
import BinComponent  from "./components/OperatorComponent/BinComponent.vue"
import DockComponent  from "./components/OperatorComponent/DockComponent.vue"
import DispatchComponent  from "./components/OperatorComponent/DispatchComponent.vue"

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
    LogoutComponent,
    BinComponent,
    DockComponent,
    DispatchComponent
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

    this.store.mandatory_uncompleted.loadFromStorage(this.role);
    console.log(this.store.mandatory_uncompleted)

    if (this.store.mandatory_uncompleted.screen) {
      this.store.setCurrentScreen(this.store.mandatory_uncompleted.screen);
    } else if (this.role.is_identified && !this.store.current_screen) {
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
html, body, #app {
  margin: 0;
  padding: 0;
  width: 100%;
  height: 100%;
}
</style>