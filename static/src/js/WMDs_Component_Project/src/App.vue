<template>
  <LoadingComponent v-if="store.loading" />

  <component 
    v-if="store.mandatory_uncompleted.component"
    :is="store.mandatory_uncompleted.component"
    v-bind="store.mandatory_uncompleted.component_props"
  />

  <QRScannerComponent 
    v-else-if="!role.is_identified"
    context="user_initial_scanner" 
    instructions="Escanea tu QR para iniciar sesión"
    :can_close="false"
    :onScan="(data) => store.role.getUserFromServer(data)" 
  />

  <component 
    v-else
    :is="currentScreenComponent" 
  />
</template>

<script>
import { nextTick } from "vue"
import LoadingComponent from "./components/LoadingComponent/LoadingComponent.vue"
import RolePicker from "./components/RolePicker/RolePicker.vue"
import ManagerComponent from "./components/ManagerComponent/ManagerComponent.vue"
import OperatorComponent from "./components/OperatorComponent/OperatorComponent.vue"
import QRScannerComponent from "./components/QRScannerComponent/QRScannerComponent.vue"
import LogoutComponent from "./components/RolePicker/LogoutComponent.vue"
import { useGeneralStore } from "./store/index"

export default {
  name: 'App',
  components: {
    LoadingComponent,
    RolePicker,
    ManagerComponent,
    OperatorComponent,
    QRScannerComponent,
    LogoutComponent
  },
  data() {
    return {
      store: useGeneralStore()
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