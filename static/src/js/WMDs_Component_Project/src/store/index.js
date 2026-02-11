import { defineStore } from 'pinia'
import { reactive } from 'vue'
import RolePickerEngine from "../components/RolePicker/RolePickerEngine"
import OdooManagerMiddleware from '../components/Forms/OdooManagerMiddleware'
import MandatoryUncompleted from './MandatoryUncompleted'


export const useGeneralStore = defineStore('general_store', {
  state: () => ({
      role: reactive(RolePickerEngine()),
      current_role: null,
      loading: false,
      current_screen:"role_picker",
      modal_open: false,
      modal_context: null,
      form_context: null,
      last_scanned_element: null,
      mandatory_uncompleted: new MandatoryUncompleted(),
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
                    title: "Planes de pickeo", 
                    description: "",
                    screen: "batch_pick",
                    value: "batch_pick",
                    create_by_aggregate: {
                        button_string: "Crear plan de pickeo",
                        input_aggregate_instructions: "Pedidos o Picks",
                        validate_item_endpoint: "validate_pick_for_batch",
                        save_aggregate_endpoint: "save_picks_in_batch",
                        extra_fields: [
                            {
                                name: "operator_id",     
                                label: "Asignar Operador", 
                                type: "selectable",       
                                source: "operadores",     
                                optionLabel: "name",      
                                optionValue: "id",     
                                required: true
                            }
                        ]                        
                    }
                }
            ]
        },
        cycle_count: {
            title: "Conteo cíclico",
            description: "Creación y asignación de rutinas de conteo cíclico de inventario",
            value: "cycle_count",
            cycle_count: {
                button_string: "Crear conteo cíclico"
            }
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
        this.loading = false
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