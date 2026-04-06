<template>
    <div class="test-flow-container">
        <div class="individual-mode">
            <div class="scanner-col">
                <div v-if="ready" class="scanner-wrapper">
                    <BarcodeScannerComponent 
                        :key="scannerKey"
                        instructions="Escanea la operación WH/DFUL/xxxxx para despacho"
                        :onScan="(data) => handleScan(data)"
                    />
                </div>
            </div>

            <div class="buttons-col">
                <Button 
                    @click="exitFlow"
                    class="p-button-text p-button-danger p-button-sm" 
                    label="Salir / Finalizar" 
                    icon="fa fa-times"
                />
            </div>

            <div class="log-col">
                <div class="log-header">
                    <span class="log-title">Despacho Fulfilment</span>
                </div>
                
                <div class="log-list">
                    <div v-if="loading" class="empty-log">
                        <i class="fa fa-spin fa-spinner search-icon"></i>
                        Validando operación...
                    </div>
                    <div v-else class="empty-log">
                        <i class="fa fa-barcode search-icon"></i>
                        Esperando escaneo de operación WH/DFUL...
                    </div>
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
    name: "DispatchComponentFul",
    components: {
        BarcodeScannerComponent,
        Button
    },
    data() {
        return {
            store: useGeneralStore(),
            ready: false,
            scannerKey: 0,
            loading: false
        }
    },
    mounted() {
        console.log("DispatchComponentFul: mounted");
        setTimeout(() => {
            this.ready = true;
        }, 500);
    },
    methods: {
        async handleScan(data) {
            console.log("DispatchComponentFul: Scanned", data);
            if (this.loading) return;
            this.loading = true;
            
            try {
                // Validate if it's a WH/DFUL picking and in correct state
                const validation = await this.store.callOdoo("validate_dfull_pick", "", {
                    pick_name: data
                });

                if (validation && validation.valid) {
                    console.log("DispatchComponentFul: Validated successfully, getting URL");
                    // Get the barcode URL and redirect
                    const url = await this.store.callOdoo("get_barcode_url", "", { 
                        pick_name: data 
                    });
                    
                    if (url) {
                        console.log("DispatchComponentFul: Redirecting to", url);
                        window.location.href = url;
                    } else {
                        console.error("DispatchComponentFul: No URL returned");
                        if (this.$toast) {
                            this.$toast.add({ 
                                severity: 'error', 
                                summary: 'Error de Redirección', 
                                detail: 'No se pudo obtener la dirección de la operación. Sin URL de retorno.', 
                                life: 4000 
                            });
                        }
                        this.restartScanner();
                    }
                } else {
                    console.warn("DispatchComponentFul: Validation failed", validation.message);
                    if (this.$toast) {
                        this.$toast.add({ 
                            severity: 'error', 
                            summary: 'Operación Inválida', 
                            detail: 'La operación no es válida para despacho fulfillment. ' + (validation.message || 'Estado incorrecto o tipo de pick inválido'), 
                            life: 5000 
                        });
                    }
                    this.restartScanner();
                }
            } catch (e) {
                console.error("DispatchComponentFul: Error in handleScan", e);
                if (this.$toast) {
                    this.$toast.add({ 
                        severity: 'error', 
                        summary: 'Error en Escaneo', 
                        detail: 'Ocurrió un error al procesar el código escaneado. ' + (e.message || 'Error de conexión'), 
                        life: 4000 
                    });
                }
                this.restartScanner();
            } finally {
                this.loading = false;
            }
        },
        restartScanner() {
            this.scannerKey++;
        },
        exitFlow() {
            console.log("DispatchComponentFul: Exiting flow");
            this.store.mandatory_uncompleted.doneMandatory();
        }
    }
}
</script>

<style scoped>
.test-flow-container {
    display: flex;
    flex-direction: column;
    gap: 1rem;
    min-height: 80vh;
    padding: 10px;
    box-sizing: border-box;
    overflow-y: auto;
}

.individual-mode {
    display: flex;
    flex-direction: column;
    gap: 1rem;
    height: 100%;
}

.scanner-col {
    height: 40%;
    display: flex;
    gap: 10px;
}

.scanner-wrapper {
    flex: 1;
    overflow: hidden;
    position: relative;
}

.buttons-col {
    height: 10%;
    display: flex;
    flex-direction: column;
    gap: 10px;
    justify-content: center;
    align-items: center;
}

.log-col {
    height: 50%;
    display: flex;
    flex-direction: column;
    background: #2c3e50;
    border-radius: 8px;
    padding: 15px;
    color: #ecf0f1;
    overflow: hidden;
}

.log-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 10px;
}

.log-title {
    font-weight: bold;
}

.log-list {
    flex: 1;
    overflow-y: auto;
    background: #34495e;
    border-radius: 4px;
    padding: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
}

.empty-log {
    text-align: center;
    color: #7f8c8d;
}

.search-icon {
    font-size: 2.5rem;
    display: block;
    margin-bottom: 10px;
}
</style>