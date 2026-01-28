class RolePickerEngineDefinition {
    constructor() {
        this.user = null
        this.email = null
        this.role = null
        this.permissions = null
        this.is_identified = false
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

    async getUserFromServer(qrContent) {
        const qrContentJson = JSON.parse(qrContent)
        const tryEmail = qrContentJson.email
        try {
            const response = await fetch('/wmds/v2/engine/get/valid_user', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    "jsonrpc": "2.0",
                    "params": {
                        "email": tryEmail
                    }
                })
            })
            const data = await response.json()
            console.log(data)
            if (data.result.error){
                console.log(data.result.error)
                return
            } 
            console.log(data.result)
            console.log("correctly identified user")
            this.user= data.result.name
            this.email= data.result.login
            this.is_identified = true
            this.persistSessionInStorage()
            
            
            
        } catch (error) {
            console.error(error)
        }
        /*
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
        }*/
        
        
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
        try {
            const response = await fetch('/wmds/v2/engine/get/user_role_permissions', {
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
            this.permissions = result.result.permissions
        } catch (error) {
            return {
                'error': 'Error while doing request',
                'message': error
            }
        }
    }

    persistSessionInStorage(){
        window.sessionStorage.setItem("wmds_logged_user", 
            JSON.stringify({
                "name": this.user,
                "email": this.email,
                "permissions": this.permissions,
                "role": this.role,
                "is_identified": this.is_identified,
                "logged_at": new Date()
            }))
    }


    checkIfPersisted() {
        const KEY = "wmds_logged_user";
        const itemStr = window.sessionStorage.getItem(KEY);

        if (!itemStr) {
            return false;
        }

        try {
            const loggedUser = JSON.parse(itemStr);
            const loggedAt = new Date(loggedUser.logged_at);
            const now = new Date();

            const twelveHoursMs = 12 * 60 * 60 * 1000;

            if (now.getTime() - loggedAt.getTime() > twelveHoursMs) {
                window.sessionStorage.removeItem(KEY);
                return false;
            }
            return true;

        } catch (error) {
            window.sessionStorage.removeItem(KEY);
            return false;
        }
    }

    logout(){
        window.sessionStorage.removeItem("wmds_logged_user");
        this.user = null
        this.email = null
        this.role = null
        this.permissions = null
        this.is_identified = false
    }

}

export default function RolePickerEngine() {
    if(import.meta.env.VITE_ENVIRONMENT === 'DEV') {
        return new RolePickerDev()
    } else if (import.meta.env.VITE_ENVIRONMENT === 'PROD') {
        return new RolePickerProd()
    }
}