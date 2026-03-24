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
                 {
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
            form_context_key: "cycle_count_management",
            cycle_count: {
                button_string: "Crear conteo cíclico"
            },
            map_columns: [
                { name: "id", label: "ID" },
                { name: "name", label: "Código" },
                { name: "notes", label: "Referencia" },
                { name: "state_label", label: "Estado" }
            ],
        },
        devolucion: {
            title: "Devoluciones",
            description: ""
        },
        operators: {
            title: "Operadores",
            description: "Gestión de operadores",
            value: "operator_list",
            form_context_key: "operator_definition",
            create_new: {
                button_string: "Dar de alta operador"
            },
            map_columns: [
                { name: "id", label: "ID" },
                { name: "name", label: "Nombre", non_blocked_field: true, type: "text" },
                { name: "login", label: "Correo", non_blocked_field: true, type: "text" },
                { name: "role_ids", label: "Roles", non_blocked_field: true, type: "multiselect", source: "operator_roles" },
            ],
            form_config: {
                save_context: "save_operator",
                on_save_actions: []
            }
        },
      },
      main_manager_screen: null,
      odoo_middleware: OdooManagerMiddleware()
  }),
  getters: {
  },
  actions: {
    formatDate(utcDate) {
        if (!utcDate) return '';
        // If it's already a Date object, just return local string
        if (utcDate instanceof Date) return utcDate.toLocaleString();
        
        let dateStr = String(utcDate);
        // Odoo datetime strings are typically 'YYYY-MM-DD HH:MM:SS' in UTC
        // We append 'Z' to ensure the browser treats it as UTC before converting to local
        if (!dateStr.endsWith('Z') && !dateStr.includes('+')) {
            dateStr += 'Z';
        }
        
        const date = new Date(dateStr);
        return isNaN(date.getTime()) ? utcDate : date.toLocaleString();
    },
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
            'bin_scan_so': async (scannedData, component) => {
                if (component.so.some(o => o.name === scannedData)) {
                    component.restartScanner();
                    return;
                }
                const response = await this.callOdoo("validate_attachment_guide", "", {
                    attachment_id: scannedData,
                });
                if (response.valid) {
                    const state = response.state;
                    if (state.dispatched) {
                        this.toast.add({ severity: 'error', summary: 'Error', detail: 'Esta guía ya ha sido despachada.', life: 3000 });
                    } else if (state.on_bin) {
                        this.toast.add({ severity: 'error', summary: 'Error', detail: `Esta guía ya está en el BIN ${state.bin_name}.`, life: 3000 });
                    } else if (state.on_dock) {
                        this.toast.add({ severity: 'error', summary: 'Error', detail: `Esta guía ya está en el DOCK ${state.dock_name}.`, life: 3000 });
                    } else {
                        component.so.push({
                            name: response.name,
                            so_name: response.so,
                            total: response.total,
                            current: response.current,
                            processed_count: response.processed_count || 0
                        });
                    }
                } else {
                    this.toast.add({ severity: 'error', summary: 'Guía Inválida', detail: 'La guía no es válida o ya fue procesada.', life: 3000 });
                }
                component.restartScanner();
            },
            'dock_validate_bin': async (scannedData, component) => {
                try {
                    const parsedData = JSON.parse(scannedData);
                    const binName = parsedData.name;
                    const response = await this.callOdoo("validate_bin", "", { bin: binName });
                    if (response.valid) {
                        component.scannedBin = binName;
                        component.packageCount = response.total_packages || 0;
                        component.packageDetails = response.package_details || [];
                    } else {
                        this.toast.add({ severity: 'error', summary: 'Error', detail: response.error, life: 3000 });
                        component.scannerKey++;
                    }
                } catch (e) {
                    this.toast.add({ severity: 'error', summary: 'Error de Lectura', detail: 'El código del bin no es válido.', life: 3000 });
                    component.scannerKey++;
                }
            },
            'assign_pack_for_operator': async (qr, extra) => {
                const operatorEmail = JSON.parse(qr).email;

                const operatorPermissions = await this.callOdoo(
                    'get_user_role_permissions',
                    '',
                    { email: operatorEmail }
                );

                if (!operatorPermissions.permissions || !operatorPermissions.permissions.includes('WMDs Operator - Packer')) {
                    this.toast.add({ 
                        severity: 'error', 
                        summary: 'Permiso Denegado', 
                        detail: 'El operador escaneado no tiene permisos de Packer. Escanee otro operador.', 
                        life: 5000 
                    });
                    // Re-trigger the scanner by resetting the component in the mandatory_uncompleted state but keeping the context
                    const currentProps = this.mandatory_uncompleted.component_props;
                    this.mandatory_uncompleted.component = null; // Force re-mount
                    await new Promise(resolve => setTimeout(resolve, 50)); // Allow Vue to process the change
                    this.mandatory_uncompleted.component = 'BarcodeScannerComponent';
                    this.mandatory_uncompleted.component_props = { ...currentProps }; // Re-assign props
                    return;
                }

                await this.callOdoo(
                    'assign_pick',
                    null,
                    {
                        id: extra.pick_id,
                        is_batch: extra.is_batch,
                        operation_type: "Pack",
                        operator_mail: operatorEmail
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