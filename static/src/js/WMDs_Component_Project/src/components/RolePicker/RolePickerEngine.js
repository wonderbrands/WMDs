class RolePickerEngineDefinition {
    constructor() {
        this.user = null
        this.email = null
        this.role = null
        this.permissions = null
    }

    async getRole() {
        return ""
    }

    async getPermissions() {
        return []
    }

    async getUserFromServer() {
        return {
            user: "",
            email: "",
        }
    }
    
}

class RolePickerDev extends RolePickerEngineDefinition {
    constructor() {
        super()
    }

    async getRole() {
        await new Promise(resolve => setTimeout(resolve, (Math.random() * (1.5 - 0.5) + 0.5) * 1000));
        this.role='manager'
    }

    async getPermissions() {
        await new Promise(resolve => setTimeout(resolve, (Math.random() * (1.5 - 0.5) + 0.5) * 1000));
        this.permissions=[]
    }

    async getUserFromServer() {
        await new Promise(resolve => setTimeout(resolve, (Math.random() * (1.5 - 0.5) + 0.5) * 1000));
        this.user = "John Doe"
        this.email = "test@valid.com"
    }

}

class RolePickerProd extends RolePickerEngineDefinition {
    constructor() {
        super()
    }

    async getUserFromServer() {
        const local_storage_info = localStorage.getItem("web.lastConnectedUser")
        if (!local_storage_info) {
            try {
                const response = await fetch('/wmds/engine/user_validate', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        "jsonrpc": "2.0",
                    })
                })
                const data = await response.json()
                console.log(data)
                this.user= data.result.name
                this.email= data.result.login
            } catch (error) {
                console.error(error)
            }
        } else {
            const users = JSON.parse(local_storage_info)        
            this.user= users[0].name
            this.email= users[0].login
        }
        
        
    }

    async getRole() {
        try {
            const response = await fetch('/wmds/engine/user', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    "jsonrpc": "2.0",
                    "params": {
                        "email": this.email
                    }
                  })
            })   
            const result = await response.json()
            console.log(result)
            this.role = result.result.role
        } catch (error) {
            return {
                'error': 'Error while doing request',
                'message': error
            }
        }
    }

    async getPermissions() {
        return []
    }

}

 
export default function RolePickerEngine() {
    if(import.meta.env.VITE_ENVIRONMENT === 'DEV') {
        return new RolePickerDev()
    } else if (import.meta.env.VITE_ENVIRONMENT === 'PROD') {
        return new RolePickerProd()
    }
}