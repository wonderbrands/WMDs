class OdooManagerMiddlewareDefinition{
    constructor() {
        this.role = null
    }

    setRole(role){
        this.role = role
    }

    async getFromOdoo(context, term){
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

    async getFromOdoo(context, term){
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

    async getFromOdoo(context, term){
        var regex = null;
        term = String(term).toLowerCase();
        switch (String(context)){
            case "ingreso":
                return await this.getIngresos(term)

            case "operadores":
                return await this.getOperadores(term)

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
                console.log(result.resulterror)
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
}

export default function OdooManagerMiddleware() {
    if(import.meta.env.VITE_ENVIRONMENT === 'DEV') {
        return new OdooManagerMiddlewareDev()
    } else if (import.meta.env.VITE_ENVIRONMENT === 'PROD') {
        return new OdooManagerMiddlewareProd()
    }
}