import { reactive } from 'vue'

export default class MandatoryUncompleted {
    constructor() {
        this.screen = null
        this.component = null
        this.component_props = {}
        this.user = null
        this.is_done = false
    }

    loadToStorage() {
        // No longer using localStorage for persistence
    }

    loadFromStorage(user) {
        // No longer using localStorage for persistence
    }

    doneMandatory() {
        this.is_done = true
        this.screen = null
        this.component = null
        this.component_props = {}
        this.user = null
    }
}
