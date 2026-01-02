import { defineStore } from 'pinia'
import RolePickerEngine from "../components/RolePicker/RolePickerEngine"
import OdooManagerMiddleware from '../components/Forms/OdooManagerMiddleware'


export const useGeneralStore = defineStore('general_store', {
  state: () => ({
      role: RolePickerEngine(),
      current_role: null,
      loading: false,
      current_screen:"role_picker",
      modal_open: false,
      modal_context: null,
      odoo_middleware: OdooManagerMiddleware()
  }),
  getters: {
  },
  actions: {
    setCurrentScreen(newScreen) {
        this.loading = true
        this.current_screen = newScreen
    },
    currentScreenLoaded() {
        this.loading = false
    },
    openModal(context) {
        this.modal_open = true
        this.modal_context = context
    },
    closeModal() {
        this.modal_open = false
        this.modal_context = null
    }
  }
})