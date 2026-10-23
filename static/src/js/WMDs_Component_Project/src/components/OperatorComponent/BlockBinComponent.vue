<template>
    <div class="block-bin-container">
        <!-- Top Navigation / Header -->
        <div class="block-bin-header">
            <div class="header-titles">
                <h2 class="title">
                    <i class="fa fa-lock mr-2 text-warning"></i> Bloqueo de BIN
                </h2>
                <p class="subtitle">Escanea el código QR o código de barras de un BIN para bloquearlo</p>
            </div>
            <Button 
                icon="fa fa-times" 
                class="p-button-rounded p-button-text p-button-secondary close-btn" 
                @click="exitFlow" 
                title="Cerrar y volver a tareas"
            />
        </div>

        <!-- Body: Scanning State -->
        <div v-if="!lastBlockedBin" class="scanner-body">
            <div class="scanner-card shadow-1">
                <QRScannerComponent 
                    :key="scannerKey"
                    instructions="Apunta la cámara o pistola láser al código del BIN"
                    :can_close="false"
                    :onScan="handleBinScan"
                />
            </div>

            <!-- Manual input fallback -->
            <div class="manual-input-section shadow-1">
                <span class="manual-label">¿Problemas con el código? Ingrésalo manualmente:</span>
                <div class="input-row">
                    <InputText 
                        v-model="manualBin" 
                        placeholder="Ej. BIN-01, BIN-A12" 
                        class="p-inputtext-sm manual-input"
                        :disabled="isProcessing"
                        @keyup.enter="submitManualBin"
                    />
                    <Button 
                        label="Bloquear" 
                        icon="fa fa-lock" 
                        class="p-button-warning p-button-sm btn-submit" 
                        :loading="isProcessing"
                        :disabled="!manualBin.trim() || isProcessing"
                        @click="submitManualBin"
                    />
                </div>
            </div>
        </div>

        <!-- Body: Success / Result State -->
        <div v-else class="result-body">
            <div class="result-card shadow-2">
                <div class="icon-circle success-bg">
                    <i class="fa fa-check-circle success-icon"></i>
                </div>
                
                <h3 class="result-title">BIN Bloqueado Correctamente</h3>
                
                <div class="bin-display-box">
                    <span class="bin-name">{{ lastBlockedBin.bin_name }}</span>
                    <span class="badge-blocked"><i class="fa fa-lock mr-1"></i> Estado: Bloqueado</span>
                </div>

                <div class="bin-info-summary">
                    <div class="info-row" v-if="lastBlockedBin.packages_count > 0">
                        <span class="info-label"><i class="fa fa-cubes mr-1"></i> Paquetes / Movimientos en BIN:</span>
                        <span class="info-val font-bold">{{ lastBlockedBin.packages_count }}</span>
                    </div>
                    <div class="info-row" v-else>
                        <span class="info-label"><i class="fa fa-inbox mr-1"></i> Contenido:</span>
                        <span class="info-val text-muted">BIN vacío (sin producto)</span>
                    </div>
                </div>

                <p class="result-note">
                    Este BIN no podrá recibir nuevos productos ni paquetes hasta que sea trasladado a DOCK o liberado por un supervisor.
                </p>

                <div class="action-buttons-group">
                    <Button 
                        label="Bloquear otro BIN" 
                        icon="fa fa-refresh" 
                        class="p-button-warning btn-block-another" 
                        @click="resetScan"
                    />
                    <Button 
                        label="Volver a Inicio" 
                        icon="fa fa-arrow-left" 
                        class="p-button-secondary p-button-outlined btn-back" 
                        @click="exitFlow"
                    />
                </div>
            </div>
        </div>
    </div>
</template>

<script>
import QRScannerComponent from '../QRScannerComponent/QRScannerComponent.vue';
import Button from 'primevue/button';
import InputText from 'primevue/inputtext';
import { useGeneralStore } from "../../store/index";

export default {
    name: "BlockBinComponent",
    components: {
        QRScannerComponent,
        Button,
        InputText
    },
    data() {
        return {
            store: useGeneralStore(),
            scannerKey: 1,
            manualBin: "",
            isProcessing: false,
            lastBlockedBin: null
        };
    },
    methods: {
        exitFlow() {
            this.manualBin = "";
            this.lastBlockedBin = null;
            this.store.mandatory_uncompleted.doneMandatory();
        },
        resetScan() {
            this.manualBin = "";
            this.lastBlockedBin = null;
            this.scannerKey++;
        },
        async handleBinScan(data) {
            if (this.isProcessing) return;
            let binName = "";
            try {
                let parsed = typeof data === 'string' ? JSON.parse(data) : data;
                binName = (parsed && parsed.name) ? parsed.name : String(data);
            } catch (e) {
                binName = String(data);
            }
            binName = binName.trim();
            if (!binName) return;
            await this.processBlockBin(binName);
        },
        async submitManualBin() {
            const clean = this.manualBin.trim();
            if (!clean || this.isProcessing) return;
            await this.processBlockBin(clean);
        },
        async processBlockBin(binName) {
            this.isProcessing = true;
            try {
                const res = await this.store.callOdoo("block_bin", "", {
                    bin: binName
                });

                if (res && res.ok) {
                    this.lastBlockedBin = {
                        bin_name: res.bin_name || binName,
                        packages_count: res.packages_count || 0,
                        has_stock: res.has_stock || false
                    };
                    if (this.$toast) {
                        this.$toast.add({
                            severity: 'success',
                            summary: 'BIN Bloqueado',
                            detail: `El BIN ${res.bin_name || binName} ha sido bloqueado exitosamente.`,
                            life: 4000
                        });
                    }
                } else {
                    const errMsg = (res && res.error) ? res.error : "No se pudo bloquear el BIN.";
                    if (this.$toast) {
                        this.$toast.add({
                            severity: res && res.already_blocked ? 'warn' : 'error',
                            summary: res && res.already_blocked ? 'BIN ya Bloqueado' : 'Error al Bloquear',
                            detail: errMsg,
                            life: 5000
                        });
                    }
                    this.scannerKey++;
                }
            } catch (err) {
                console.error("Error al bloquear BIN:", err);
                if (this.$toast) {
                    this.$toast.add({
                        severity: 'error',
                        summary: 'Error de Conexión',
                        detail: 'Ocurrió un error inesperado al procesar el bloqueo del BIN.',
                        life: 4000
                    });
                }
                this.scannerKey++;
            } finally {
                this.isProcessing = false;
            }
        }
    }
};
</script>

<style scoped>
.block-bin-container {
    width: 100%;
    height: 100%;
    display: flex;
    flex-direction: column;
    background: #f8fafc;
    padding: 1rem;
    box-sizing: border-box;
    overflow-y: auto;
}

.block-bin-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 1rem;
    background: #ffffff;
    padding: 1rem 1.25rem;
    border-radius: 12px;
    border: 1px solid #e2e8f0;
}

.header-titles .title {
    margin: 0;
    font-size: 1.4rem;
    font-weight: 700;
    color: #0f172a;
    display: flex;
    align-items: center;
}

.header-titles .subtitle {
    margin: 0.25rem 0 0 0;
    font-size: 0.85rem;
    color: #64748b;
}

.close-btn {
    font-size: 1.25rem !important;
}

.scanner-body {
    display: flex;
    flex-direction: column;
    gap: 1rem;
    align-items: center;
    width: 100%;
    max-width: 600px;
    margin: 0 auto;
}

.scanner-card {
    width: 100%;
    background: #ffffff;
    border-radius: 12px;
    padding: 1rem;
    border: 1px solid #e2e8f0;
    display: flex;
    justify-content: center;
    align-items: center;
    overflow: hidden;
}

.manual-input-section {
    width: 100%;
    background: #ffffff;
    border-radius: 12px;
    padding: 1rem 1.25rem;
    border: 1px solid #e2e8f0;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
}

.manual-label {
    font-size: 0.85rem;
    font-weight: 600;
    color: #475569;
}

.input-row {
    display: flex;
    gap: 0.5rem;
    width: 100%;
}

.manual-input {
    flex: 1;
}

.btn-submit {
    white-space: nowrap;
}

.result-body {
    display: flex;
    justify-content: center;
    align-items: center;
    padding: 1.5rem 0;
    width: 100%;
}

.result-card {
    background: #ffffff;
    border-radius: 16px;
    padding: 2rem 1.5rem;
    border: 1px solid #e2e8f0;
    max-width: 500px;
    width: 100%;
    display: flex;
    flex-direction: column;
    align-items: center;
    text-align: center;
}

.icon-circle {
    width: 72px;
    height: 72px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    margin-bottom: 1rem;
}

.success-bg {
    background: #ecfdf5;
}

.success-icon {
    font-size: 2.5rem;
    color: #10b981;
}

.result-title {
    margin: 0 0 1rem 0;
    font-size: 1.3rem;
    font-weight: 700;
    color: #0f172a;
}

.bin-display-box {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.5rem;
    background: #f1f5f9;
    padding: 1rem 1.5rem;
    border-radius: 10px;
    width: 100%;
    margin-bottom: 1.25rem;
}

.bin-name {
    font-size: 1.75rem;
    font-weight: 800;
    color: #1e293b;
    letter-spacing: 0.05em;
}

.badge-blocked {
    background: #fee2e2;
    color: #991b1b;
    font-size: 0.8rem;
    font-weight: 700;
    padding: 0.25rem 0.75rem;
    border-radius: 9999px;
    display: inline-flex;
    align-items: center;
}

.bin-info-summary {
    width: 100%;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    padding: 0.75rem 1rem;
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    margin-bottom: 1rem;
}

.info-row {
    display: flex;
    justify-content: space-between;
    font-size: 0.85rem;
}

.info-label {
    color: #64748b;
}

.info-val {
    color: #0f172a;
}

.result-desc, .result-note {
    font-size: 0.85rem;
    color: #64748b;
    line-height: 1.4;
    margin: 0 0 1.5rem 0;
}

.actions-row, .action-buttons-group {
    display: flex;
    gap: 0.75rem;
    width: 100%;
}

.btn-block-another, .btn-back {
    flex: 1;
}

@media (max-width: 600px) {
    .block-bin-header {
        padding: 0.75rem 1rem;
    }
    .header-titles .title {
        font-size: 1.2rem;
    }
    .action-buttons-group {
        flex-direction: column;
    }
}
</style>
