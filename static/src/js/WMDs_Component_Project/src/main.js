import { createApp } from 'vue'
import PrimeVue from 'primevue/config'
import { createPinia } from 'pinia'
import { definePreset } from '@primeuix/themes'
import Aura from '@primeuix/themes/aura'
import App from './App.vue'
import QrScanner from 'qr-scanner'
import Quagga from 'quagga';
import ToastService from 'primevue/toastservice';
import './style.css'

QrScanner.WORKER_PATH = null
window.QrScanner = QrScanner
window.Quagga = Quagga

const WMDSAuraLight = definePreset(Aura, {
    semantic: {
        primary: {
            50:  '#fefce8',
            100: '#fef9c3',
            200: '#fef08a',
            300: '#fde047',
            400: '#facc15',
            500: '#eab308',
            600: '#ca8a04',
            700: '#a16207',
            800: '#854d0e',
            900: '#713f12'
        }
    },
    components: {
        button: {
            primary: {
                color: '#000000'
            }
        }
    }
})

window.mountWMDSApp = function (selector = '#wmds-app') {
    const app = createApp(App)
    const pinia = createPinia()

    app.use(ToastService)
    
    pinia.use(({ store }) => {
        store.toast = app.config.globalProperties.$toast
    })
    
    app.use(pinia)

    app.use(PrimeVue, {
        theme: {
            preset: WMDSAuraLight,
            options: {
                darkModeSelector: false 
            }
        }
    })

    app.mount(selector)

    window.WMDS_App = app
    
    console.log('App mounted and available at window.WMDS_App')
    
    return app
}