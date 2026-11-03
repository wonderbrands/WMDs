<template>
    <Teleport to="body">
        <div v-if="show" class="cancelled-modal-overlay">
            <div class="cancelled-modal">
                <!-- Header -->
                <div class="cancelled-modal-header">
                    <i class="fa fa-exclamation-triangle cancelled-modal-icon"></i>
                    <div>
                        <h2 class="cancelled-modal-title">¡Atención! Pedidos Cancelados</h2>
                        <p class="cancelled-modal-subtitle">
                            Tienes <strong>{{ pending.length }}</strong> guía(s) cancelada(s).
                            Sácalas físicamente del carro y escanéalas una a una para confirmar.
                            Si una guía ya está dentro del contenedor/carrier y no se puede sacar,
                            usa <strong>«Ya se embarcó»</strong>.
                        </p>
                    </div>
                </div>

                <!-- Lista de canceladas -->
                <div class="cancelled-modal-list">
                    <div 
                        v-for="item in pending" 
                        :key="item.name"
                        class="cancelled-modal-item"
                        :class="{ 'item-confirmed': confirmed.includes(item.name) }"
                    >
                        <i class="fa" :class="confirmed.includes(item.name) ? 'fa-check-circle' : 'fa-times-circle'"></i>
                        <div class="cancelled-modal-item-info">
                            <span class="item-ei">{{ item.name }}</span>
                            <span class="item-so">{{ item.so_name }}</span>
                        </div>
                        <span v-if="shipped.includes(item.name)" class="item-badge-shipped">Embarcada</span>
                        <span v-else-if="confirmed.includes(item.name)" class="item-badge-ok">Retirada</span>
                        <template v-else>
                            <button
                                v-if="item.hold"
                                type="button"
                                class="item-btn-shipped"
                                :disabled="!!askingShip || !!productChoice"
                                @click="askingShip = item"
                            >Ya se embarcó</button>
                            <span class="item-badge-pending">Pendiente</span>
                        </template>
                    </div>
                </div>

                <!-- Confirmación: el paquete ya está en el contenedor/carrier -->
                <div v-if="askingShip" class="cancelled-modal-ask">
                    <p>
                        ¿Confirmas que la guía <strong>{{ askingShip.name }}</strong> ya está dentro del
                        contenedor/carrier y <strong>no se puede sacar</strong>?
                    </p>
                    <p class="ask-note">
                        Se entregará al cliente como una venta normal y Operaciones gestionará la devolución.
                    </p>
                    <div class="ask-actions">
                        <button type="button" class="ask-btn ask-btn-yes" @click="confirmShipped">Sí, se embarcó</button>
                        <button type="button" class="ask-btn ask-btn-no" @click="askingShip = null">No, la voy a retirar</button>
                    </div>
                </div>

                <!-- Selección de producto (órdenes con varios productos: 1 guía = 1 pieza) -->
                <div v-if="productChoice" class="cancelled-modal-ask">
                    <p>¿Qué producto contiene la guía <strong>{{ productChoice.item.name }}</strong>?</p>
                    <div class="ask-products">
                        <button
                            v-for="product in productChoice.products"
                            :key="product.id"
                            type="button"
                            class="ask-btn ask-btn-product"
                            @click="onMarkShipped(productChoice.item, product.id)"
                        >
                            {{ product.name }}
                            <small>({{ product.remaining }} pendiente(s))</small>
                        </button>
                    </div>
                    <div class="ask-actions">
                        <button type="button" class="ask-btn ask-btn-no" @click="onCancelProductChoice()">Cancelar</button>
                    </div>
                </div>

                <!-- Progreso -->
                <div class="cancelled-modal-progress">
                    <div class="progress-label">
                        {{ confirmed.length }} / {{ pending.length }} resueltas
                    </div>
                    <div class="progress-track">
                        <div 
                            class="progress-track-fill" 
                            :style="{ width: (confirmed.length / pending.length * 100) + '%' }"
                        ></div>
                    </div>
                </div>

                <!-- Escáner utilizando BarcodeScannerComponent -->
                <div class="cancelled-modal-scanner">
                    <BarcodeScannerComponent 
                        instructions="Escanea la guía cancelada para confirmar"
                        :onScan="handleScan"
                        :key="scannerKey"
                    />
                    <div v-if="lastError" class="scanner-error">
                        <i class="fa fa-warning"></i> {{ lastError }}
                    </div>
                </div>

                <!-- Aviso de cierre automático cuando todas están confirmadas -->
                <div v-if="confirmed.length === pending.length && pending.length > 0" class="cancelled-modal-footer">
                    <i class="fa fa-spin fa-spinner" style="color: #2ecc71; font-size: 1.4rem;"></i>
                    <span style="color: #2ecc71; font-weight: 600;">Todas resueltas. Cerrando...</span>
                </div>
            </div>
        </div>
    </Teleport>
</template>

<script>
import BarcodeScannerComponent from '../QRScannerComponent/BarcodeScannerComponent.vue';

export default {
    name: "CancelledModalComponent",
    components: {
        BarcodeScannerComponent
    },
    props: {
        show: { type: Boolean, default: false },
        pending: { type: Array, required: true },       // [{ name, so_name, hold }]
        confirmed: { type: Array, required: true },     // ['SO12345/1'] retiradas o embarcadas
        shipped: { type: Array, default: () => [] },    // ['SO12345/1'] marcadas como embarcadas
        productChoice: { type: Object, default: null }, // { item, products: [{ id, name, remaining }] }
        lastError: { type: String, default: "" },
        onScanCancelled: { type: Function, required: true },
        onMarkShipped: { type: Function, default: () => {} },          // (item, productId|null)
        onCancelProductChoice: { type: Function, default: () => {} },
    },
    data() {
        return {
            scannerKey: 0,
            askingShip: null,
        };
    },
    watch: {
        show(newVal) {
            if (newVal) {
                this.scannerKey++;
            }
            this.askingShip = null;
        }
    },
    methods: {
        handleScan(scannedCode) {
            this.onScanCancelled(scannedCode);
        },
        confirmShipped() {
            const item = this.askingShip;
            this.askingShip = null;
            this.onMarkShipped(item, null);
        }
    }
}
</script>

<style scoped>
.cancelled-modal-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.75);
    z-index: 9999;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 1rem;
    backdrop-filter: blur(4px);
}

.cancelled-modal {
    background: #1a1a2e;
    border-radius: 16px;
    padding: 2rem;
    width: 100%;
    max-width: 520px;
    max-height: 90vh;
    overflow-y: auto;
    box-shadow: 0 20px 60px rgba(0,0,0,0.6), 0 0 0 1px rgba(231,76,60,0.3);
    display: flex;
    flex-direction: column;
    gap: 1.25rem;
    animation: modalIn 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
}

@keyframes modalIn {
    from { opacity: 0; transform: scale(0.85) translateY(20px); }
    to   { opacity: 1; transform: scale(1) translateY(0); }
}

.cancelled-modal-header {
    display: flex;
    align-items: flex-start;
    gap: 1rem;
}

.cancelled-modal-icon {
    font-size: 2.5rem;
    color: #e74c3c;
    animation: pulse 1.5s infinite;
    flex-shrink: 0;
    margin-top: 4px;
}

@keyframes pulse {
    0%, 100% { opacity: 1; }
    50%       { opacity: 0.5; }
}

.cancelled-modal-title {
    margin: 0 0 4px;
    color: #e74c3c;
    font-size: 1.2rem;
    font-weight: 700;
}

.cancelled-modal-subtitle {
    margin: 0;
    color: #bdc3c7;
    font-size: 0.9rem;
    line-height: 1.4;
}

.cancelled-modal-list {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    max-height: 220px;
    overflow-y: auto;
}

.cancelled-modal-item {
    background: #2c2c54;
    border: 1px solid #e74c3c;
    border-radius: 8px;
    padding: 0.6rem 1rem;
    display: flex;
    align-items: center;
    gap: 0.75rem;
    transition: all 0.3s ease;
}

.cancelled-modal-item.item-confirmed {
    background: #1a3a2a;
    border-color: #2ecc71;
    opacity: 0.8;
}

.cancelled-modal-item .fa-times-circle {
    color: #e74c3c;
    font-size: 1.2rem;
    flex-shrink: 0;
}

.cancelled-modal-item .fa-check-circle {
    color: #2ecc71;
    font-size: 1.2rem;
    flex-shrink: 0;
}

.cancelled-modal-item-info {
    display: flex;
    flex-direction: column;
    flex: 1;
}

.item-ei {
    font-family: monospace;
    font-size: 0.95rem;
    font-weight: bold;
    color: #ecf0f1;
}

.item-so {
    font-size: 0.78rem;
    color: #95a5a6;
}

.item-badge-pending {
    font-size: 0.7rem;
    background: #e74c3c;
    color: white;
    padding: 2px 8px;
    border-radius: 20px;
    font-weight: 600;
    white-space: nowrap;
}

.item-badge-ok {
    font-size: 0.7rem;
    background: #2ecc71;
    color: #1a3a2a;
    padding: 2px 8px;
    border-radius: 20px;
    font-weight: 600;
    white-space: nowrap;
}

.item-badge-shipped {
    background: rgba(52, 152, 219, 0.15);
    color: #5dade2;
    border: 1px solid rgba(52, 152, 219, 0.4);
    border-radius: 999px;
    padding: 2px 10px;
    font-size: 0.75rem;
    font-weight: 600;
    white-space: nowrap;
}

.item-btn-shipped {
    background: transparent;
    color: #5dade2;
    border: 1px solid #5dade2;
    border-radius: 8px;
    padding: 4px 10px;
    font-size: 0.75rem;
    font-weight: 600;
    margin-right: 6px;
    cursor: pointer;
    white-space: nowrap;
}

.item-btn-shipped:disabled {
    opacity: 0.4;
    cursor: not-allowed;
}

.cancelled-modal-ask {
    background: rgba(52, 152, 219, 0.08);
    border: 1px solid rgba(52, 152, 219, 0.35);
    border-radius: 12px;
    padding: 1rem;
    color: #ecf0f1;
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
}

.cancelled-modal-ask p {
    margin: 0;
}

.ask-note {
    font-size: 0.85rem;
    color: #bdc3c7;
}

.ask-actions,
.ask-products {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
}

.ask-btn {
    border: none;
    border-radius: 8px;
    padding: 8px 14px;
    font-weight: 600;
    cursor: pointer;
}

.ask-btn-yes {
    background: #3498db;
    color: #fff;
}

.ask-btn-no {
    background: transparent;
    color: #bdc3c7;
    border: 1px solid #7f8c8d;
}

.ask-btn-product {
    background: #2c3e50;
    color: #ecf0f1;
    text-align: left;
    width: 100%;
}

.cancelled-modal-progress {
    display: flex;
    flex-direction: column;
    gap: 6px;
}

.progress-label {
    font-size: 0.85rem;
    color: #bdc3c7;
    text-align: right;
}

.progress-track {
    height: 8px;
    background: #2c3e50;
    border-radius: 4px;
    overflow: hidden;
}

.progress-track-fill {
    height: 100%;
    background: linear-gradient(90deg, #e74c3c, #f39c12, #2ecc71);
    border-radius: 4px;
    transition: width 0.4s ease;
}

.cancelled-modal-scanner {
    display: flex;
    flex-direction: column;
    gap: 0.6rem;
    background: #16213e;
    border-radius: 10px;
    padding: 1rem;
    border: 1px solid #34495e;
}

.scanner-error {
    color: #e74c3c;
    font-size: 0.82rem;
    display: flex;
    align-items: center;
    gap: 6px;
    animation: shake 0.3s ease;
    margin-top: 5px;
}

@keyframes shake {
    0%, 100% { transform: translateX(0); }
    25%       { transform: translateX(-6px); }
    75%       { transform: translateX(6px); }
}

.cancelled-modal-footer {
    display: flex;
    justify-content: center;
    animation: fadeIn 0.4s ease;
}

@keyframes fadeIn {
    from { opacity: 0; transform: translateY(8px); }
    to   { opacity: 1; transform: translateY(0); }
}
</style>
