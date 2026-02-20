import { createApp } from 'vue'
import PrimeVue from 'primevue/config'
import { createPinia } from 'pinia'
import { definePreset } from '@primeuix/themes'
import Aura from '@primeuix/themes/aura'
import App from './App.vue'
import QrScanner from 'qr-scanner'
import Quagga from 'quagga';

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
  

const app = createApp(App)
app.use(createPinia())

app.use(PrimeVue, {
    theme: {
        preset: WMDSAuraLight,
        options: {
            darkModeSelector: false // force light mode
        }
    }
})

app.mount('#wmds-app')
