class OdooManagerMiddlewareDefinition{
    constructor() {
        this.role = null
    }

    setRole(role){
        this.role = role
    }

    async getFromOdoo(context, term, params={}){
        return null
    }
}

class OdooManagerMiddlewareDev extends OdooManagerMiddlewareDefinition{
    constructor() {
        super()
    }

    setRole(role){
        super.setRole(role)
    }

    async getFromOdoo(context, term, params={}){
        var regex = null;
        term = String(term).toLowerCase();
        switch (String(context)){
            case "ingreso":
                const ingresos = [
                    { name: 'AG/IN/0001', code: '0001' },
                    { name: 'AG/IN/0002', code: '0002' },
                    { name: 'AG/IN/0003', code: '0003' },
                    { name: 'AG/IN/0004', code: '0004' },
                    { name: 'AG/IN/0005', code: '0005' },
                    { name: 'AG/IN/0006', code: '0006' },
                    { name: 'AG/IN/0007', code: '0007' },
                    { name: 'AG/IN/0008', code: '0008' },
                    { name: 'AG/IN/0009', code: '0009' },
                    { name: 'AG/IN/0010', code: '0010' },
                    { name: 'AG/IN/0011', code: '0011' },
                    { name: 'AG/IN/0012', code: '0012' },
                    { name: 'AG/IN/0013', code: '0013' },
                    { name: 'AG/IN/0014', code: '0014' },
                    { name: 'AG/IN/0015', code: '0015' },
                    { name: 'AG/IN/0016', code: '0016' },
                    { name: 'AG/IN/0017', code: '0017' },
                    { name: 'AG/IN/0018', code: '0018' },
                    { name: 'AG/IN/0019', code: '0019' },
                    { name: 'AG/IN/0020', code: '0020' },
                    { name: 'AG/IN/0021', code: '0021' },
                    { name: 'AG/IN/0022', code: '0022' },
                    { name: 'AG/IN/0023', code: '0023' },
                    { name: 'AG/IN/0024', code: '0024' },
                    { name: 'AG/IN/0025', code: '0025' },
                    { name: 'AG/IN/0026', code: '0026' },
                    { name: 'AG/IN/0027', code: '0027' },
                    { name: 'AG/IN/0028', code: '0028' },
                    { name: 'AG/IN/0029', code: '0029' },
                    { name: 'AG/IN/0030', code: '0030' },
                    { name: 'AG/IN/0031', code: '0031' },
                    { name: 'AG/IN/0032', code: '0032' },
                    { name: 'AG/IN/0033', code: '0033' },
                    { name: 'AG/IN/0034', code: '0034' },
                    { name: 'AG/IN/0035', code: '0035' },
                    { name: 'AG/IN/0036', code: '0036' },
                    { name: 'AG/IN/0037', code: '0037' },
                    { name: 'AG/IN/0038', code: '0038' },
                    { name: 'AG/IN/0039', code: '0039' },
                    { name: 'AG/IN/0040', code: '0040' },
                    { name: 'AG/IN/0041', code: '0041' }
                ]
                regex = new RegExp(".*" + term + ".*", "i")
                const filteredIngresos = ingresos.filter(ingreso => regex.test(ingreso.name)).slice(0, 5)
                return filteredIngresos;

            case "operadores":
                const operadores = [
                    { name: 'Juan Perez', code: 'JP' },
                    { name: 'Pedro Gomez', code: 'PG' },
                    { name: 'Maria Rodriguez', code: 'MR' },
                    { name: 'Luis Hernandez', code: 'LH' },
                    { name: 'Ana Martinez', code: 'AM' },
                    { name: 'Carlos Sanchez', code: 'CS' },
                    { name: 'Sofia Lopez', code: 'SL' },
                    { name: 'Miguel Garcia', code: 'MG' },
                    { name: 'Lucia Torres', code: 'LT' },
                    { name: 'Pedro Fernandez', code: 'PF' },
                    { name: 'Maria Sanchez', code: 'MS' },
                    { name: 'Luis Gomez', code: 'LG' },
                ]
                regex = new RegExp(".*" + term + ".*", "i")
                const filteredOperadores = operadores.filter(operador => regex.test(operador.name)).slice(0, 5)
                return filteredOperadores;
            case "operator_list":
                return {
                    map_cols: [
                        { field: "id", name: "ID" },
                        { field: "name", name: "Nombre" },
                        { field: "login", name: "Correo" },
                    ],
                    total_count: 12,
                    data: [
                        { id: 1, name: "Juan Perez", login: "juan@test.com", role_ids: [101] },
                        { id: 2, name: "Pedro Gomez", login: "pedro@test.com", role_ids: [102, 103] },
                    ]
                }

            case "operator_roles":
                return [
                    { id: 101, name: "Reception" },
                    { id: 102, name: "Picker" },
                    { id: 103, name: "Packer" },
                ]

            case "save_operator":
                return { saved: true }

            case "pick":
                console.log("in pick")
                const picks = {
                    map_cols: [
                        { field: "id", name: "ID" },
                        { field: "sale_order", name: "SO" },
                        { field: "name", name: "Nombre" },
                        { field: "responsible", name: "Responsable", non_blocked_field: true },
                        { field: "date", name: "Fecha" },
                        { field: "status", name: "Status", type: "selectable", options: [
                            { name: "Borrador", value: "draft" }, 
                            { name: "En espera de otra operación", value: "waiting" },
                            { name: "En espera", value: "confirmed" },
                            { name: "Disponible", value: "assigned", default: true },
                            { name: "Hecho", value: "done" },
                            { name: "Cancelado", value: "cancel" },
                        ] },
                        { field: "wmds_stock_status", name: "Status WMDs", type: "selectable", options: [
                            { name: "No asignado", value: "not_assigned", default: true }, 
                            { name: "No iniciado", value: "not_started" },
                            { name: "En progreso", value: "in_progress" },
                            { name: "Completado", value: "completed" },
                        ] },
                    ],
                    total_count: 1012,
                    data: [
                        {id: 78, sale_order: "SO00265", name: "WH/Pick/0078", responsible: null, date: "06/01/2026", status: "Pendiente"},
                        {id: 79, sale_order: "SO00265", name: "WH/Pick/0079", responsible: null, date: "06/01/2026", status: "Pendiente"},
                        {id: 80, sale_order: "SO00265", name: "WH/Pick/0080", responsible: null, date: "06/01/2026", status: "Pendiente"},
                        {id: 81, sale_order: "SO00265", name: "WH/Pick/0081", responsible: null, date: "06/01/2026", status: "Pendiente"},
                        {id: 82, sale_order: "SO00265", name: "WH/Pick/0082", responsible: null, date: "06/01/2026", status: "Pendiente"},
                        {id: 83, sale_order: "SO00265", name: "WH/Pick/0083", responsible: null, date: "06/01/2026", status: "Pendiente"},
                        {id: 84, sale_order: "SO00265", name: "WH/Pick/0084", responsible: null, date: "06/01/2026", status: "Pendiente"},
                        {id: 85, sale_order: "SO00265", name: "WH/Pick/0085", responsible: null, date: "06/01/2026", status: "Pendiente"},
                        {id: 86, sale_order: "SO00265", name: "WH/Pick/0086", responsible: null, date: "06/01/2026", status: "Pendiente"},
                        {id: 87, sale_order: "SO00265", name: "WH/Pick/0087", responsible: null, date: "06/01/2026", status: "Pendiente"},
                        {id: 88, sale_order: "SO00265", name: "WH/Pick/0088", responsible: null, date: "06/01/2026", status: "Pendiente"},
                        {id: 89, sale_order: "SO00265", name: "WH/Pick/0089", responsible: null, date: "06/01/2026", status: "Pendiente"},
                        {id: 90, sale_order: "SO00265", name: "WH/Pick/0090", responsible: null, date: "06/01/2026", status: "Pendiente"},    
                    ]
                }
                return picks
            case "pick_products":
                return {
                    title: "Productos del traslado",
                    map_cols: [
                        { field: "id", name: "ID" },
                        { field: "product", name: "Producto" },
                        { field: "barcode", name: "Codigo de barras" },
                        { field: "sku", name: "SKU" },
                        { field: "location", name: "Ubicacion desde" },
                        { field: "location_dest", name: "Ubicacion hacia" },
                        { field: "quantity", name: "Cantidad" },
                    ],
                    total_count: 890,
                    data: [
                        {id: 78, product: "Producto 1", barcode: "12345678", sku: "12345678", location: "Almacen 1", location_dest: "Almacen 2", quantity: 10},
                        {id: 79, product: "Producto 2", barcode: "12345679", sku: "12345679", location: "Almacen 1", location_dest: "Almacen 2", quantity: 10},
                        {id: 80, product: "Producto 3", barcode: "12345680", sku: "12345680", location: "Almacen 1", location_dest: "Almacen 2", quantity: 10},
                        {id: 81, product: "Producto 4", barcode: "12345681", sku: "12345681", location: "Almacen 1", location_dest: "Almacen 2", quantity: 10},
                        {id: 82, product: "Producto 5", barcode: "12345682", sku: "12345682", location: "Almacen 1", location_dest: "Almacen 2", quantity: 10},
                        {id: 83, product: "Producto 6", barcode: "12345683", sku: "12345683", location: "Almacen 1", location_dest: "Almacen 2", quantity: 10},
                        {id: 84, product: "Producto 7", barcode: "12345684", sku: "12345684", location: "Almacen 1", location_dest: "Almacen 2", quantity: 10},
                        {id: 85, product: "Producto 8", barcode: "12345685", sku: "12345685", location: "Almacen 1", location_dest: "Almacen 2", quantity: 10},
                        {id: 86, product: "Producto 9", barcode: "12345686", sku: "12345686", location: "Almacen 1", location_dest: "Almacen 2", quantity: 10},
                        {id: 87, product: "Producto 10", barcode: "12345687", sku: "12345687", location: "Almacen 1", location_dest: "Almacen 2", quantity: 10},
                    ]
                }
            case "assign_pick":
                return {
                    saved: true
                }
            case "pending_tasks":
                return [
                    {
                        key: 'picks-0',
                        label: 'WH/Pick/0047',
                        data: 'WH/Pick/0047',
                    },
                    {
                        key: 'picks-1',
                        label: 'WH/Pick/0048',
                        data: 'WH/Pick/0048',
                    },
                    {
                        key: 'picks-2',
                        label: 'WH/Pick/0049',
                        data: 'WH/Pick/0049',
                    },
                    {
                        key: 'picks-3',
                        label: 'WH/Pick/0050',
                        data: 'WH/Pick/0050',
                    }
                ]
            case "get_barcode_url":
                return {
                    url: "https://www.google.com"
                }
            
            case "log_record":
                return {
                    saved: true
                }
            
            case "change_status":
                return {
                    saved: true
                }
            
            case "validate_pick_for_batch":
                return {
                    valid: true
                }

            case "save_picks_in_batch":
                return {
                    saved: true
                }
            case "validate_attachment_guide":
                return {
                    ok: true
                }
            case "move_to_bin":
                return {
                    ok: true
                }
            case "validate_bin":
                return {
                    valid: true,
                    bin: params.bin,
                    packages: ["GUIA-TEST-01", "GUIA-TEST-02"],
                    total_packages: 2
                }

            case "move_bin_to_dock":
                return {
                    ok: true,
                    moved_packages: 2
                }
            case "skip_log_if_manager":
                return {
                    "is_manager": true,
                    "json_user": "{}"
                }
            case "get_locations_by_range":
                return {
                    "locations":["WH/Stock"]
                }
            
            case "cycle_count_assigned":
                return [
                    { key: 1, label: "CC000001-WAVE0001 (10:00)", data: "CC000001-WAVE0001", pick: "CC000001-WAVE0001" },
                    { key: 2, label: "CC000001-WAVE0002 (10:30)", data: "CC000001-WAVE0002", pick: "CC000001-WAVE0002" }
                ]

            case "get_cycle_count_comparison":
                return {
                    ok: true,
                    waves: [
                        { id: 1, name: "W001", operator: "Juan" },
                        { id: 2, name: "W002", operator: "Pedro" }
                    ],
                    data: [
                        { 
                            product_id: 10, product_sku: "123", product_name: "Prod A", 
                            location_id: 5, location_name: "Loc 1",
                            wave_counts: { "1": 1, "2": 1 }, theoretical_qty: 4, has_discrepancy: true 
                        },
                        { 
                            product_id: 11, product_sku: "456", product_name: "Prod B", 
                            location_id: 5, location_name: "Loc 1",
                            wave_counts: { "1": 2, "2": 2 }, theoretical_qty: 2, has_discrepancy: false 
                        }
                    ]
                }
            
            case "adjust_cycle_count_stock":
                return { ok: true }

            case "validate_cycle_count_location":
                return { ok: true, location_id: 5, location_name: params.location_name }
            
            case "validate_cycle_count_product":
                return { ok: true, product_id: 10, product_name: "Prod Mock", product_sku: "SKU-MOCK" }

            case "log_cycle_count_line":
                return { ok: true }

            case "get_cycle_count_details_minimal":
                return { ok: true, name: "CC0001-WAVE001" }

            case "get_cycle_count_logs":
                return {
                    ok: true,
                    data: [
                        { id: 1, date: "2026-03-25 10:00:00", user: "Juan Perez", log: "Operador Juan Perez contó 10 productos en WH/Stock/A-01" },
                        { id: 2, date: "2026-03-25 10:05:00", user: "Pedro Gomez", log: "Operador Pedro Gomez contó 5 productos en WH/Stock/A-02" }
                    ]
                }
            
            case "reopen_cycle_count_wave":
                return { ok: true }

            case "batch_type":
                return [
                    { id: 'sale', name: 'Pedido' },
                    { id: 'full', name: 'Full' }
                ]

            default:
                break;
        }
    }
}

class OdooManagerMiddlewareProd extends OdooManagerMiddlewareDefinition {
    constructor() {
        super()
        this.endpointMap = {
            operator_list: {url: '/wmds/v2/engine/get/operators', method: 'POST'},
            operator_roles: {url: '/wmds/v2/engine/get/operator_roles', method: 'POST'},
            save_operator: {url: '/wmds/v2/engine/post/save_operator', method: 'POST'},
            skip_log_if_manager: {url: '/wmds/v2/engine/post/skip_log_if_manager', method: 'POST'},
            ingreso: {url: '/wmds/engine/picks', method: 'POST'},
            operadores: {url: '/wmds/engine/available_operators', method: 'POST'},
            assign_pick: {url: '/wmds/v2/engine/post/pick_assign_operator', method: 'POST'},
            pick_products: {url: '/wmds/v2/engine/get/pick_products', method: 'POST'},
            pick: {url: '/wmds/v2/engine/get/picks', method: 'POST'},
            pending_tasks: {url: '/wmds/v2/engine/get/pending_tasks', method: 'POST'},
            get_barcode_url: {url: '/wmds/v2/engine/get/barcode_url', method: 'POST'},
            log_record: {url: '/wmds/v2/engine/post/log_stock_record', method: 'POST'},
            change_status: {url: '/wmds/v2/engine/post/change_wmds_status', method: 'POST'},
            validate_pick_for_batch: {url: '/wmds/v2/engine/post/validate_pick_for_batch', method: 'POST'},
            save_picks_in_batch: {url: '/wmds/v2/engine/post/save_batch', method: 'POST'},
            validate_attachment_guide: {url: '/wmds/v2/engine/post/validate_attachment_guide', method: 'POST'},
            move_to_bin: {url: '/wmds/v2/engine/post/move_to_bin', method: 'POST'},
            validate_bin: {url: '/wmds/v2/engine/post/validate_bin', method: 'POST'},
            validate_dock: {url: '/wmds/v2/engine/post/validate_dock', method: 'POST'},
            move_bin_to_dock: {url: '/wmds/v2/engine/post/move_bin_to_dock', method: 'POST'},
            pack: {url: '/wmds/v2/engine/get/pack', method: 'POST'},
            assign_pack: {url: '/wmds/v2/engine/post/pick_assign_operator', method: 'POST'},
            dispatch_orders: {url: '/wmds/v2/engine/post/dispatch_packet', method: 'POST'},
            batch_pick: {url: '/wmds/v2/engine/get/batch_pick', method: 'POST'},
            batch_details: {url: '/wmds/v2/engine/get/batch_details', method: 'POST'},
            get_locations_by_range: {url: '/wmds/v2/engine/get/locations_by_range', method: 'POST'},
            pending_full_dispatch: {url: '/wmds/v2/engine/get/pending_full_dispatch', method: 'POST'},
            dispatch_full_items: {url: '/wmds/v2/engine/post/dispatch_full_items', method: 'POST'},
            cycle_count: {url: '/wmds/v2/engine/get/cycle_counts', method: 'POST'},
            get_cycle_count_details: {url: '/wmds/v2/engine/get/cycle_count_details', method: 'POST'},
            get_cycle_count_logs: {url: '/wmds/v2/engine/get/cycle_count_logs', method: 'POST'},
            reopen_cycle_count_wave: {url: '/wmds/v2/engine/reopen_cycle_count_wave', method: 'POST'},
            finish_cycle_count_wave: {url: '/wmds/v2/engine/finish_cycle_count_wave', method: 'POST'},
            close_cycle_count: {url: '/wmds/v2/engine/close_cycle_count', method: 'POST'},
            cancel_cycle_count: {url: '/wmds/v2/engine/cancel_cycle_count', method: 'POST'},
            create_full_cycle_count: {url: '/wmds/v2/engine/create_full_cycle_count', method: 'POST'},
            reassign_cycle_count_wave_operator: {url: '/wmds/v2/engine/reassign_cycle_count_wave_operator', method: 'POST'},
            cancel_cycle_count_wave: {url: '/wmds/v2/engine/cancel_cycle_count_wave', method: 'POST'},
            get_cycle_wave_lines: {url: '/wmds/v2/engine/get/cycle_wave_lines', method: 'POST'},
            create_waves_for_cycle: {url: '/wmds/v2/engine/create_waves_for_cycle', method: 'POST'},
            cycle_count_assigned: {url: '/wmds/v2/engine/cycle_count_assigned', method: 'POST'},
            validate_cycle_count_location: {url: '/wmds/v2/engine/validate_cycle_count_location', method: 'POST'},
            validate_cycle_count_product: {url: '/wmds/v2/engine/validate_cycle_count_product', method: 'POST'},
            log_cycle_count_line: {url: '/wmds/v2/engine/log_cycle_count_line', method: 'POST'},
            get_cycle_count_comparison: {url: '/wmds/v2/engine/get/cycle_count_comparison', method: 'POST'},
            adjust_cycle_count_stock: {url: '/wmds/v2/engine/adjust_cycle_count_stock', method: 'POST'},
            get_cycle_count_details_minimal: {url: '/wmds/v2/engine/get/cycle_count_details_minimal', method: 'POST'},
            get_user_role_permissions: {url: '/wmds/v2/engine/get/user_role_permissions', method: 'POST'},
            batch_type: {url: '/wmds/v2/engine/get/batch_types', method: 'POST'},
        };
    }

    setRole(role){
        super.setRole(role)
    }

    async _fetch(endpoint, params, method) {
        console.log("Call backend")
        console.log(params)
        console.log(method)
        console.log(endpoint)
        try {
            const response = await fetch(endpoint, {
                method: method,
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    jsonrpc: "2.0",
                    params: params
                  })
            });
            const result = await response.json();
            console.log(result);
            return result;
        } catch (error) {
            console.error("Fetch/JSON Parse Error:", error);
            return {
                error: {
                    message: 'Error de red o al procesar la respuesta del servidor.',
                    data: { debug: error.toString() }
                }
            };
        }
    }

    async getFromOdoo(context, term, params={}) {
        const endpointConfig = this.endpointMap[context];
        if (!endpointConfig) {
            return { error: { message: `Endpoint no configurado para: ${context}` } };
        }

        let fetchParams;
        term = String(term).toLowerCase();

        switch (String(context)){
            case "ingreso":
                fetchParams = { type: "ingreso", name: term };
                break;
            case "operadores":
                fetchParams = { name: term };
                break;
            case "pending_tasks":
                fetchParams = {task: term, ...params};
                break;
            case "validate_pick_for_batch":
                fetchParams = { pick: term, ...params };
                break;
            case "batch_type":
                return [
                    { id: 'sale', name: 'Pedido' },
                    { id: 'full', name: 'Full' }
                ];
            default:
                fetchParams = params;
                break;
        }
        
        const result = await this._fetch(endpointConfig.url, fetchParams, endpointConfig.method);

        if (result.error) {
             return result;
        }

        if (Object.prototype.hasOwnProperty.call(result, 'result')) {
            switch(context){
                case 'get_barcode_url':
                    return result.result?.url;
                case 'operadores':
                    return result.result?.results;
                default:
                    return result.result;
            }
        }
        
        return { error: { message: "Respuesta inválida del servidor (sin result ni error)." } };
    }
}

export default function OdooManagerMiddleware() {
    if(import.meta.env.VITE_ENVIRONMENT === 'DEV') {
        return new OdooManagerMiddlewareDev()
    } else if (import.meta.env.VITE_ENVIRONMENT === 'PROD') {
        return new OdooManagerMiddlewareProd()
    }
}