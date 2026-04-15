class RolePickerEngineDefinition {
    constructor() {
        this.user = null
        this.email = null
        this.role = null
        this.permissions = null
        this.is_identified = false
        this.packer_uuid = null
        this.packer_barcode_image = null
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
        let tryEmail = null;
        if (!qrContent) {
            throw new Error("Contenido de escaneo vacío.");
        }

        try {
            const qrContentJson = JSON.parse(qrContent);
            tryEmail = qrContentJson.email || qrContentJson.login || qrContent;
        } catch (e) {
            // If it's not JSON, it is a plain barcode login (UUID)
            tryEmail = qrContent.trim();
        }

        if (!tryEmail) {
            throw new Error("No se pudo extraer la identificación del escaneo.");
        }

        console.log("Attempting login with identifier:", tryEmail);
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
            this.packer_uuid = data.result.packer_uuid
            this.packer_barcode_image = data.result.packer_barcode_image
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
            this.packer_uuid = result.result.packer_uuid
            this.packer_barcode_image = result.result.packer_barcode_image
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
                "packer_uuid": this.packer_uuid,
                "packer_barcode_image": this.packer_barcode_image,
                "logged_at": new Date()
            }))
    }

    checkIfPersisted() {
        const KEY = "wmds_logged_user";
        const itemStr = window.sessionStorage.getItem(KEY);
        if (!itemStr) return false;
        try {
            const loggedUser = JSON.parse(itemStr);
            this.user = loggedUser.user;
            this.email = loggedUser.email;
            this.permissions = loggedUser.permissions;
            this.role = loggedUser.role;
            this.is_identified = loggedUser.is_identified;
            this.packer_uuid = loggedUser.packer_uuid;
            this.packer_barcode_image = loggedUser.packer_barcode_image;
            
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
        this.packer_uuid = null
        this.packer_barcode_image = null
    }
}

export default function RolePickerEngine() {
    const env = import.meta.env.VITE_ENVIRONMENT
    if (env === 'DEV') return new RolePickerDev()
    return new RolePickerProd()
}