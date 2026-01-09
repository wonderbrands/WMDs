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
      form_context: null,
      available_main_manager_screens: {
        home:{
            title: "Inicio",
            description: "Pantalla principal",
            value: "home"
        },
        ingresos: {
            title: "Ingresos",
            description: "Validación de los productos ingresados a almacén.",
            value: "ingresos"
        },
        disponibilizar: {
            title: "Disponibilizar",
            description: "Traslado de productos desde posición de ingreso a alguna ubicación de almacén",
            value: "disponibilizar"
        },
        traslado: {
            title: "Traslados",
            description: "Traslado de una ubicación interna de almacen a otra",
            value: "traslado"
        },
        pick: {
            title: "Picks",
            children: [
                {
                    title: "Picks",
                    description: "Preparación del producto para proceso de entrega",
                    screen: "pick",
                    value: "pick",
                    form_title: "Asignación de Pick:",
                    map_columns:[
                        {name: "id", label: "ID"},
                        {name: "sale_order", label: "Pedido"},
                        {name: "name", label: "Nombre"},
                        {name: "responsible", label: "Responsable"},
                        {name: "date", label: "Fecha"},
                        {name: "status", label: "Estado"}
                    ]
                },
                {
                    title: "Crear plan de pickeo", 
                    description: "",
                    screen: "batch_pick",
                    value: "batch_pick"
                }
            ]
                        

        },
        devolucion: {
            title: "Devoluciones",
            description: ""
        },
      },
      main_manager_screen: null,
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
    openModal(context, form_context) {
        this.modal_open = true
        this.modal_context = context
        this.form_context = form_context
    },
    closeModal() {
        this.modal_open = false
        this.modal_context = null
    },
    setMainManagerScreen(newScreen) {
        if(!Object.keys(this.available_main_manager_screens).includes(newScreen) ||
            this.available_main_manager_screens[newScreen].children){
           Object.keys(this.available_main_manager_screens).forEach(screen => {
               if(this.available_main_manager_screens[screen].children){
                   this.available_main_manager_screens[screen].children.forEach(child => {
                       if(child.screen == newScreen){
                            console.log(child)
                           this.main_manager_screen = child
                       }
                   })
               }
           })
        }else{
            console.log(this.available_main_manager_screens[newScreen])
            this.main_manager_screen = this.available_main_manager_screens[newScreen]
        }
        
    }
  }
})