export default class MandatoryUncompleted{
    constructor(kw = {}){
        const defaults = {
            screen : null,
            component: null,
            component_props: {},
            data: {},
            user: null,
            logged: false
        }
        
        Object.assign(this, {...defaults, ...kw})
    }

    loadToStorage(){
        localStorage.setItem("mandatory_uncompleted",
            JSON.stringify({
                screen: this.screen,
                component: this.component,
                component_props: this.component_props,
                data: this.data,
                user: this.user
            })
        )
    }

    loadFromStorage(logged){
        let parsed = {}
        let mandatory = localStorage.getItem("mandadoty_uncompleted")
        if(!mandatory){
            return null
        }
        let json_mandatory = JSON.parse(mandatory)
        Object.assign(parsed, json_mandatory)
        if (logged.email == parsed.user){
            Object.assign(this, parsed)
            this.logged = true
        } 
    }
    
    doneMandatory(){
        localStorage.removeItem("mandadoty_uncompleted")
        const defaults = {
            screen : null,
            component: null,
            component_props: {},
            data: {},
            user: null,
            logged: false
        }
        Object.assign(this, {...defaults})
    }
}