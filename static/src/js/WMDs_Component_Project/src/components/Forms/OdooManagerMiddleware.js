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
            
            default:
                break;
        }
    }
}

class OdooManagerMiddlewareProd extends OdooManagerMiddlewareDefinition {
    constructor() {
        super()
    }

    setRole(role){
        super.setRole(role)
    }

    async getFromOdoo(context, term, params={}) {
        var regex = null;
        term = String(term).toLowerCase();
        switch (String(context)){
            case "ingreso":
                return await this.getIngresos(term)

            case "operadores":
                return await this.getOperadores(term)

            case "assign_pick":
                return await this.assignPick(params)

            case "pick_products":
                return await this.getPickProducts(params)
            
            case "pick":
                return await this.getPicks(params)
            
            case "pending_tasks":
                return await this.getPendingTasks(term, params)

            case "get_barcode_url":
                return await this.getBarcodeUrl(params)

            case "log_record":
                return await this.logRecord(term, params)
            
            case "change_status":
                return await this.changeStatus(term, params)
            
            case "validate_pick_for_batch":
                return await this.validatePickForBatch(term)
                   
            case "save_picks_in_batch":
                return await this.savePicksInBatch(params)
                    
            default:
                break;
        }
    }

    async getOperadores(term) {
        try {
            const response = await fetch('/wmds/engine/available_operators', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    jsonrpc: "2.0",
                    params: {
                        name: term
                    }
                  })
            })   
            const result = await response.json()
            console.log(result)
            if (result.result.error) {
                console.log(result.result.error)
                return []
            }
            return result.result.results
            
        } catch (error) {
            return {
                'error': 'Error while doing request',
                'message': error
            }
        }
    }

    async getIngresos(term) {
        try {
            const response = await fetch('/wmds/engine/picks', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    jsonrpc: "2.0",
                    params: {
                        type: "ingreso",
                        name: term
                    }
                  })
            })   
            const result = await response.json()
            console.log(result)
            if (result.result.error) {
                console.log(result.result.error)
                return []
            }
            return result.result
        } catch (error) {
            return {
                'error': 'Error while doing request',
                'message': error
            }
        }
    }

    async getPicks(params){
        try {
            const response = await fetch('/wmds/v2/engine/get/picks', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    jsonrpc: "2.0",
                    params: params
                  })
            })   
            const result = await response.json()
            console.log(result)
            if (result.error) {
                console.log(result.error)
                return []
            }
            return result.result
        } catch (error) {
            return {
                'error': 'Error while doing request',
                'message': error
            }
        }
    }

    async getPickProducts(params){
        try {
            const response = await fetch('/wmds/v2/engine/get/pick_products', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    jsonrpc: "2.0",
                    params: params
                  })
            })   
            const result = await response.json()
            console.log(result)
            if (result.error) {
                console.log(result.error)
                return []
            }
            return result.result
        } catch (error) {
            return {
                'error': 'Error while doing request',
                'message': error
            }
        }
    }


    async assignPick(params){
        try {
            const response = await fetch('/wmds/v2/engine/post/pick_assign_operator', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    jsonrpc: "2.0",
                    params: params
                  })
            })   
            const result = await response.json()
            console.log(result)
            if (result.error) {
                console.log(result.error)
                return []
            }
            return result.result
        } catch (error) {
            return {
                'error': 'Error while doing request',
                'message': error
            }
        }
    }
    async getPendingTasks(term, params){
        try {
            const response = await fetch('/wmds/v2/engine/get/pending_tasks', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    jsonrpc: "2.0",
                    params: {task: term, ...params}
                  })
            })   
            const result = await response.json()
            console.log(result)
            if (result.error) {
                console.log(result.error)
                return []
            }
            return result.result
        } catch (error) {
            return {
                'error': 'Error while doing request',
                'message': error
            }
        }
    }

    async getBarcodeUrl(params){
        try {
            const response = await fetch('/wmds/v2/engine/get/barcode_url', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    jsonrpc: "2.0",
                    params: params
                  })
            })   
            const result = await response.json()
            console.log(result)
            if (result.error) {
                console.log(result.error)
                return []
            }
            return result.result.url
        } catch (error) {
            return {
                'error': 'Error while doing request',
                'message': error
            }
        }
    }

    async logRecord(term, params){
        try {
            const response = await fetch('/wmds/v2/engine/post/log_stock_record', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    jsonrpc: "2.0",
                    params: params
                  })
            })   
            const result = await response.json()
            console.log(result)
            if (result.error) {
                console.log(result.error)
                return []
            }
            return result.result
        } catch (error) {
            return {
                'error': 'Error while doing request',
                'message': error
            }
        }
    }

    async changeStatus(term, params){
        try {
            const response = await fetch('/wmds/v2/engine/post/change_wmds_status', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    jsonrpc: "2.0",
                    params: params
                  })
            })   
            const result = await response.json()
            console.log(result)
            if (result.error) {
                console.log(result.error)
                return []
            }
            return result.result
        } catch (error) {
            return {
                'error': 'Error while doing request',
                'message': error
            }
        }
    }

    async validatePickForBatch(term){
        try {
            const response = await fetch('/wmds/v2/engine/post/validate_pick_for_batch', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                 },
                body: JSON.stringify({
                    jsonrpc: "2.0",
                    params:{
                        pick: term
                    }
                  })
            })   
            const result = await response.json()
            console.log(result)
            if (result.error) {
                console.log(result.error)
                return []
            }
            return result.result
        } catch (error) {
            return {
                'error': 'Error while doing request',
                'message': error
            }
        }
    }
                   
    async savePicksInBatch(params){
        try {
            const response = await fetch('/wmds/v2/engine/post/save_batch', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    jsonrpc: "2.0",
                    params: params
                  })
            })   
            const result = await response.json()
            console.log(result)
            if (result.error) {
                console.log(result.error)
                return []
            }
            return result.result
        } catch (error) {
            return {
                'error': 'Error while doing request',
                'message': error
            }
        }
    }
}

export default function OdooManagerMiddleware() {
    if(import.meta.env.VITE_ENVIRONMENT === 'DEV') {
        return new OdooManagerMiddlewareDev()
    } else if (import.meta.env.VITE_ENVIRONMENT === 'PROD') {
        return new OdooManagerMiddlewareProd()
    }
}