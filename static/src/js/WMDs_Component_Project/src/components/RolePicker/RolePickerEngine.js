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
        await new Promise(resolve => setTimeout(resolve, 1000));
        this.role = 'manager'
        this.persistSessionInStorage()
    }

    async getPermissions() {
        await new Promise(resolve => setTimeout(resolve, 1000));
        this.permissions = []
        this.persistSessionInStorage()
    }

    async getUserFromServer() {
        await new Promise(resolve => setTimeout(resolve, 1000));
        this.user = "John Doe"
        this.email = "test@valid.com"
        this.is_identified = true
        this.persistSessionInStorage()
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
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    "jsonrpc": "2.0",
                    "params": { "email": tryEmail }
                })
            })
            const data = await response.json()
            if (data.result.error) {
                throw new Error(data.result.error)
            } 
            this.user = data.result.name
            this.email = data.result.login
            this.is_identified = true
            this.persistSessionInStorage()
        } catch (error) {
            console.error(error);
            throw new Error("No se pudo validar el usuario.");
        }
    }

    async getRole() {
        try {
            const response = await fetch('/wmds/engine/user', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    "jsonrpc": "2.0",
                    "params": { "email": this.email }
                })
            })   
            const result = await response.json()
            this.role = result.result.role
            this.persistSessionInStorage()
        } catch (error) {
            console.error(error);
            throw new Error("No se pudo obtener el rol.");
        }
    }

    async getPermissions() {
        try {
            const response = await fetch('/wmds/v2/engine/get/user_role_permissions', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    "jsonrpc": "2.0",
                    "params": { "email": this.email }
                })
            })   
            const result = await response.json()
            this.permissions = result.result.permissions
            this.persistSessionInStorage()
        } catch (error) {
            console.error(error);
            throw new Error("No se pudieron obtener los permisos.");
        }
    }

    persistSessionInStorage() {
        window.sessionStorage.setItem("wmds_logged_user", 
            JSON.stringify({
                "user": this.user,
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
        if (!itemStr) return false;
        try {
            const loggedUser = JSON.parse(itemStr);
            const loggedAt = new Date(loggedUser.logged_at);
            const now = new Date();
            const twelveHoursMs = 12 * 60 * 60 * 1000;
            if (now.getTime() - loggedAt.getTime() > twelveHoursMs) {
                this.logout();
                return false;
            }
            return true;
        } catch (error) {
            this.logout();
            return false;
        }
    }

    logout() {
        window.sessionStorage.removeItem("wmds_logged_user");
        this.user = null
        this.email = null
        this.role = null
        this.permissions = null
        this.is_identified = false
    }
}

export default function RolePickerEngine() {
    const env = import.meta.env.VITE_ENVIRONMENT
    if (env === 'DEV') return new RolePickerDev()
    return new RolePickerProd()
}