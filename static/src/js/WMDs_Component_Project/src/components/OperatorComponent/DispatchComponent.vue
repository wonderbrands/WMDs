<template>
    <div class="test-flow-container" style="display: flex; flex-direction: column; gap: 1rem; height: 100vh; padding: 10px;">
        
        <div class="scanner-section" style="display: flex; gap: 10px; height: 40%; min-height: 250px;">
            <div v-if="ready" style="flex: 1; overflow: hidden; position: relative;">
                <BarcodeScannerComponent 
                    :key="scannerKey"
                    instructions="Escanea la guía para despacho"
                    :onScan="(data) => searchAndValidateSO(data)"
                />
            </div>

            <div style="display: flex; flex-direction: column; gap: 10px; justify-content: center;">
                <Button v-if="so.length > 0"
                    @click="dispatchToCarrier"
                    class="p-button-success p-button-sm" 
                    label="Entregar a paquetería" 
                    icon="pi pi-truck"
                />
                <Button 
                    @click="exitFlow"
                    class="p-button-text p-button-danger p-button-sm" 
                    label="Salir / Finalizar" 
                    icon="pi pi-times"
                />
            </div>
        </div>

        <div class="log-section" style="flex: 1; display: flex; flex-direction: column; background: #2c3e50; border-radius: 8px; padding: 15px; color: #ecf0f1; overflow: hidden;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                <div style="display: flex; align-items: center; gap: 10px;">
                    <span style="font-weight: bold;">Guías listas para entrega: {{ so.length }}</span>
                    <Button icon="pi pi-trash" class="p-button-danger p-button-text p-button-sm" label="Limpiar Todo" @click="so = []" v-if="so.length > 0"/>
                </div>
            </div>

            <div class="log-list" style="flex: 1; overflow-y: auto; background: #34495e; border-radius: 4px; padding: 10px;">
                <div v-for="(order, index) in so" :key="index" 
                     style="padding: 8px 0; border-bottom: 1px solid #5d6d7e; font-family: monospace; display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <i class="pi pi-barcode" style="margin-right: 10px; color: #f1c40f;"></i>
                        {{ order }}
                    </div>
                    <Button icon="pi pi-times" class="p-button-rounded p-button-danger p-button-text" @click="so.splice(index,1)" />
                </div>
                
                <div v-if="so.length === 0" style="text-align: center; color: #7f8c8d; margin-top: 20px;">
                    <i class="pi pi-box" style="font-size: 2rem; display: block; margin-bottom: 10px;"></i>
                    Esperando escaneo de guía...
                </div>
            </div>
        </div>
    </div>
</template>

<script>
import BarcodeScannerComponent from '../QRScannerComponent/BarcodeScannerComponent.vue';
import Button from 'primevue/button';
import { useGeneralStore } from "../../store/index";

export default {
    name: "DispatchComponent",
    components: {
        BarcodeScannerComponent,
        Button
    },
    data() {
        return {
            store: useGeneralStore(),
            so: [],
            ready: false,
            scannerKey: 0
        }
    },
    mounted() {
        localStorage.removeItem("mandatory_uncompleted");
        setTimeout(() => {
            this.ready = true;
        }, 500);
    },
    methods: {
        async searchAndValidateSO(data) {
            try {
                if (this.so.includes(data)) {
                    this.restartScanner();
                    return;
                }

                let response = await this.store.callOdoo("validate_attachment_guide", "", {
                    attachment_id: data,
                });

                if (response.valid) {
                    this.so.push(data);
                } else {
                    if(this.$toast) {
                        this.$toast.add({ severity: 'error', summary: 'Guía Inválida', detail: 'La guía no es válida para despacho.', life: 3000 });
                    }
                }
                
                this.restartScanner();
            } catch (e) {
                console.log("Error:", e);
                this.restartScanner();
            }
        },
        restartScanner() {
            this.scannerKey++;
        },
        async dispatchToCarrier() {
            if (this.so.length === 0) return;
            
            try {
                let response = await this.store.callOdoo("dispatch_orders", "", {
                    operator_login: this.store.role.email,
                    picks_ids: this.so // Se envía el array de guías escaneadas
                });

                if (response.status === "success") {
                    if (response.warning) {
                        this.$toast.add({ 
                            severity: 'warn', 
                            summary: 'Entrega Parcial', 
                            detail: response.warning, 
                            life: 6000 
                        });
                    } else {
                        this.$toast.add({ 
                            severity: 'success', 
                            summary: 'Éxito', 
                            detail: 'Todas las órdenes han sido completadas y cerradas.', 
                            life: 3000 
                        });
                    }

                    this.store.mandatory_uncompleted.doneMandatory();
                    this.so = [];
                    this.restartScanner(); 
                } else {
                    throw new Error(response.message || "Error desconocido");
                }
            } catch (e) {
                if(this.$toast) {
                    this.$toast.add({ 
                        severity: 'error', 
                        summary: 'Error de Despacho', 
                        detail: e.message || 'No se pudo completar la entrega.', 
                        life: 4000 
                    });
                }
                console.error("Dispatch error", e);
            }
        },       
        exitFlow() {
            if (this.so.length > 0) {
                if (!confirm("Tienes guías escaneadas sin entregar a paquetería. ¿Estás seguro de que quieres salir?")) {
                    return;
                }
            }
            this.so = [];
            this.store.mandatory_uncompleted.doneMandatory();
        }
    }
}
</script>

<style scoped>
@keyframes bounce {
  0%, 20%, 50%, 80%, 100% {transform: translateY(0);}
  40% {transform: translateY(-15px);}
  60% {transform: translateY(-7px);}
}
</style>