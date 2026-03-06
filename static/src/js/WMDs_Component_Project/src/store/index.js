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
            title: "Recepciones",
            description: "Validación de los productos ingresados a almacén.",
            value: "ingresos"
        },
        disponibilizar: {
            title: "Rackeo",
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
                        {name: "responsible", label: "Responsable", non_blocked_field: true, source: "operadores"},
                        {name: "date", label: "Fecha"},
                        {name: "status", label: "Estado"}
                    ],
                    form_config: {
                        save_context: "assign_pick",
                        related_data_endpoint: "pick_products",
                        on_save_actions: [
                            {
                                context: "log_record",
                                params: {
                                    pick_id: "{id}",
                                    operator_mail: "{user_email}",
                                    message: "Traslado {name} asignado a {responsible.name}"
                                }
                            },
                            {
                                context: "log_record",
                                params: {
                                    pick_id: "{id}",
                                    type: "external",
                                    operator_mail: "{user_email}",
                                    message: ""
                                }
                            },
                            {
                                context: "change_status",
                                params: {
                                    pick_id: "{id}",
                                    status: "not_started"
                                }
                            }
                        ]
                    }
                },
                batch_pick: {
                    title: "Planes de pickeo", 
                    description: "Agrupación de órdenes para surtido masivo",
                    screen: "batch_pick",
                    value: "batch_pick", 
                    form_title: "Detalle del Plan de Pickeo:",
                    map_columns:[
                        {name: "id", label: "ID"},
                        {name: "name", label: "Referencia"},
                        {name: "operator", label: "Operador", non_blocked_field: true, source: "operadores"},
                        {name: "scheduled_date", label: "Fecha Programada"},
                        {name: "state", label: "Estado"}
                    ],
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
                    },
                    form_config: {
                        save_context: "assign_pick",
                        related_data_endpoint: "pick_products",
                        on_save_actions: [
                        ]
                    }
                }
            ]
        },
        pack: {
            title: "Packs",
            description: "Pack",
            value: "pack",
            form_title: "Asignación de Pack:",
            map_columns:[
                {name: "id", label: "ID"},
                {name: "sale_order", label: "Pedido"},
                {name: "name", label: "Nombre"},
                {name: "responsible", label: "Responsable", non_blocked_field: true, source: "operadores"},
                {name: "date", label: "Fecha"},
                {name: "status", label: "Estado"}
            ],
            form_config: {
                save_context: "assign_pack",
                related_data_endpoint: "pick_products",
                on_save_actions: [
                    {
                        context: "log_record",
                        params: {
                            pick_id: "{id}",
                            operator_mail: "{user_email}",
                            message: "Traslado {name} asignado a {responsible.name}"
                        }
                    },
                    {
                        context: "log_record",
                        params: {
                            pick_id: "{id}",
                            type: "external",
                            operator_mail: "{user_email}",
                            message: ""
                        }
                    },
                    {
                        context: "change_status",
                        params: {
                            pick_id: "{id}",
                            status: "not_started"
                        }
                    }
                ]
            }
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
    async callOdoo(context, term, params) {
        this.loading = true;
        try {
            const result = await this.odoo_middleware.getFromOdoo(context, term, params);

            if (result && result.error) {
                const errorMessage = result.error.data?.message || result.error.message || 'Ocurrió un error no especificado.';
                this.toast.add({ severity: 'error', summary: 'Error', detail: errorMessage, life: 4000 });
                return result; 
            }
            
            const endpointConfig = this.odoo_middleware.endpointMap[context];
            if (endpointConfig && endpointConfig.url.includes('/post/')) {
                this.toast.add({ severity: 'success', summary: 'Éxito', detail: 'Operación completada.', life: 3000 });
            }

            return result;
        } catch (e) {
            this.toast.add({ severity: 'error', summary: 'Error de Conexión', detail: 'No se pudo contactar al servidor.', life: 4000 });
            console.error("Error en callOdoo:", e);
            return { error: { message: 'Error de Conexión: No se pudo contactar al servidor.' } };
        }
        finally {
            this.loading = false;
        }
    },
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
                           this.main_manager_screen = child
                       }
                   })
               }
           })
        }else{
            this.main_manager_screen = this.available_main_manager_screens[newScreen]
        }
        
    },
    executeActionByContext(context, data, extra) {
        const actionsMap = {
            'assign_pack_for_operator': async (qr, extra) => {
                await this.callOdoo(
                    'assign_pick',
                    null,
                    {
                        id: extra.pick_id,
                        is_batch: extra.is_batch,
                        operation_type: "Pack",
                        operator_mail: JSON.parse(qr).email
                    }
                )
                this.mandatory_uncompleted.doneMandatory()
            },
        };

        if (actionsMap[context]) {
            actionsMap[context](data, extra);
        }
    }
  }
})