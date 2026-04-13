<template>
    <div 
        class="scanner-wrapper" 
        @click="focusLaserInput"
        @touchstart="handleTouchStart"
        @touchmove="handleTouchMove"
        @touchend="handleTouchEnd"
    >
        <div v-if="pulling" class="pull-to-refresh-indicator" :style="{ height: pullDistance + 'px', opacity: pullDistance / 100 }">
            <i class="fa fa-refresh" :class="{ 'fa-spin': refreshing }"></i>
            <span>{{ refreshing ? 'Actualizando...' : 'Tire para actualizar' }}</span>
        </div>
        <div class="controls-overlay">
            <div class="switch-container">
                <i class="fa fa-barcode" :class="{ 'active-icon': !isCameraMode }"></i>
                <ToggleSwitch v-model="isCameraMode" @change="onToggleChange" class="tiny-switch" />
                <i class="fa fa-camera" :class="{ 'active-icon': isCameraMode }"></i>
            </div>
            <Button v-if="can_close" @click="closeScanner" label="&#10006;" class="control-btn close-btn" />
        </div>

        <div v-if="reader === 'camera'" v-show="camera_init" class="camera-container">
            <div ref="barcodeScanner" class="quagga-container"></div>
            <div class="laser-line" :class="{ 'laser-locked': scan_lockout }"></div>
        </div>

        <div v-if="reader === 'laser'" class="laser-container" :class="{ 'focus-disabled': disableFocus }">
            <input 
                ref="laserInput"
                type="text" 
                v-model="laser_input" 
                @input="handleInput"
                @blur="keepFocus"
                class="hidden-input"
                inputmode="none"
            >
            <div v-if="disableFocus" class="focus-warning">
                <i class="fa fa-keyboard-o"></i> MODO ESCRITURA ACTIVO
            </div>
        </div>

        <Message v-if="!camera_init && error && reader === 'camera'" class="error-msg" severity="error">{{ error }}</Message>
        
        <div class="message-container" v-if="!hideInstructions">
            <Message v-if="instructions && (camera_init || reader === 'laser')" class="instruction-msg" :severity="disableFocus ? 'warn' : 'info'">
                {{ disableFocus ? 'Escaneo pausado por teclado' : (scan_lockout ? 'Procesando...' : instructions) }}
            </Message>
        </div>
    </div>
</template>

<script>
import Button from 'primevue/button';
import Message from 'primevue/message';
import ToggleSwitch from 'primevue/toggleswitch';
import { useGeneralStore } from "../../store/index"

export default {
    name: "BarcodeScannerComponent", 
    data() {
        return {
            store: useGeneralStore(),
            camera_init: false,
            error: null,
            is_scanning: false,
            reader: "laser",
            isCameraMode: false,
            laser_input: "",
            scan_lockout: false,
            inputTimeout: null,
            quagga_running: false,
            // Pull to refresh state
            startY: 0,
            pullDistance: 0,
            pulling: false,
            refreshing: false,
            maxPullDistance: 100
        }
    },
    props: {
        context: String,
        instructions: String,
        hideInstructions: { type: Boolean, default: false },
        can_close: { type: Boolean, default: false },
        onScan: Function,
        extra_data: Object,
        disableFocus: { type: Boolean, default: false }
    },
    mounted() {
        console.log("mounted");
        if (this.reader === 'camera') {
            this.initCamera();
        } else {
            this.$nextTick(() => {
                this.focusLaserInput();
            });
        }
        window.addEventListener('keydown', this.handleGlobalKeydown);
    },
    beforeUnmount() {
        console.log("beforeUnmount");
        this.closeScanner();
        window.removeEventListener('keydown', this.handleGlobalKeydown);
    },
    methods: {
        handleGlobalKeydown(e) {
            if (this.disableFocus) return;
            console.log("handleGlobalKeydown", e.key);
            if (this.reader === 'laser' && document.activeElement !== this.$refs.laserInput) {
                this.focusLaserInput();
            }
        },
        async initCamera() {
            console.log("initCamera");
            this.camera_init = true;
            this.is_scanning = true;
            this.scan_lockout = false;
            
            await this.$nextTick();
            
            window.Quagga.init({
                inputStream: {
                    name: "Live",
                    type: "LiveStream",
                    target: this.$refs.barcodeScanner,
                    constraints: {
                        width: { min: 640 },
                        height: { min: 480 },
                        facingMode: "environment",
                        aspectRatio: { min: 1, max: 2 }
                    },
                },
                locator: {
                    patchSize: "medium",
                    halfSample: true
                },
                decoder: {
                    readers: ["code_128_reader"]
                },
                locate: true
            }, (err) => {
                if (err) {
                    console.log("Camera access failed");
                    this.error = "Camera access failed";
                    this.camera_init = false;
                    return;
                }
                console.log("Quagga start");
                window.Quagga.start();
                this.quagga_running = true;
                this.setupDetection();
            });
        },
        setupDetection() {
            console.log("setupDetection");
            window.Quagga.onDetected((result) => {
                if (!this.is_scanning || this.scan_lockout) return;

                if (result && result.codeResult && result.codeResult.code) {
                    console.log("Detected code", result.codeResult.code);
                    this.triggerScan(result.codeResult.code);
                }
            });
        },
        onToggleChange() {
            this.setReader(this.isCameraMode ? 'camera' : 'laser');
        },
        setReader(newReader) {
            console.log("setReader", newReader);
            this.reader = newReader;
            this.isCameraMode = newReader === 'camera';
            this.scan_lockout = false;
            
            if (newReader === 'camera') {
                this.initCamera();
            } else {
                this.closeScanner();
                this.$nextTick(() => {
                    this.focusLaserInput();
                });
            }
        },
        closeScanner() {
            console.log("closeScanner");
            this.is_scanning = false;
            if (window.Quagga && this.quagga_running) {
                window.Quagga.stop();
                window.Quagga.offDetected();
                this.quagga_running = false;
            }
            this.camera_init = false;
        },
        focusLaserInput() {
            if (this.disableFocus) return;
            console.log("focusLaserInput");
            if (this.reader === 'laser' && this.$refs.laserInput) {
                this.$refs.laserInput.focus();
            }
        },
        keepFocus() {
            if (this.disableFocus) return;
            console.log("keepFocus");
            if (this.reader === 'laser') {
                setTimeout(() => {
                    this.focusLaserInput();
                }, 10);
            }
        },
        handleInput() {
            console.log("handleInput", this.laser_input);
            if (this.scan_lockout) {
                this.laser_input = "";
                return;
            }

            if (this.inputTimeout) {
                clearTimeout(this.inputTimeout);
            }

            this.inputTimeout = setTimeout(() => {
                this.processScanedData();
            }, 50); 
        },
        processScanedData() {
            console.log("processScanedData");
            if (this.laser_input.trim() !== "") {
                this.triggerScan(this.laser_input); 
                this.laser_input = "";
            }
        },
        playBeep() {
            console.log("playBeep");
            try {
                const AudioContext = window.AudioContext || window.webkitAudioContext;
                const ctx = new AudioContext();
                const oscillator = ctx.createOscillator();
                const gainNode = ctx.createGain();
                
                oscillator.type = 'sine';
                oscillator.frequency.setValueAtTime(880, ctx.currentTime);
                
                gainNode.gain.setValueAtTime(0.1, ctx.currentTime);
                
                oscillator.connect(gainNode);
                gainNode.connect(ctx.destination);
                
                oscillator.start();
                oscillator.stop(ctx.currentTime + 0.1);
            } catch (error) {
                console.log("AudioContext not supported");
            }
        },
        triggerScan(code) {
            console.log("triggerScan", code);
            this.scan_lockout = true;
            this.playBeep();
            
            if (this.context) {
                this.store.executeActionByContext(this.context, code, this.extra_data);
            }
            else if (this.onScan) {
                this.onScan(code);
            }

            setTimeout(() => {
                console.log("scan_lockout lifted");
                this.scan_lockout = false;
            }, 3000);
        },
        handleTouchStart(e) {
            if (this.$el.scrollTop === 0) {
                this.startY = e.touches[0].pageY;
                this.pulling = true;
            }
        },
        handleTouchMove(e) {
            if (!this.pulling || this.refreshing) return;
            const currentY = e.touches[0].pageY;
            const diff = currentY - this.startY;
            if (diff > 0) {
                this.pullDistance = Math.min(diff, this.maxPullDistance);
                if (diff > 10) e.preventDefault(); // Prevent native scroll
            }
        },
        async handleTouchEnd() {
            if (!this.pulling) return;
            if (this.pullDistance >= 60) {
                this.refreshing = true;
                await this.store.executeBeforeMount();
                this.refreshing = false;
            }
            this.pulling = false;
            this.pullDistance = 0;
        }
    },
    components: { Button, Message, ToggleSwitch }
}
</script>

<style scoped>
.scanner-wrapper {
    padding: 0.5rem;
    width: 100%;
    height: 100%;
    display: flex;
    flex-direction: column; 
    position: relative;
    box-sizing: border-box;
    overflow: hidden;
}

.pull-to-refresh-indicator {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    overflow: hidden;
    background: rgba(59, 130, 246, 0.1);
    color: #3B82F6;
    z-index: 1001;
    transition: height 0.1s ease;
    font-size: 0.8rem;
    font-weight: bold;
    gap: 5px;
}

.pull-to-refresh-indicator i {
    font-size: 1.2rem;
}

.controls-overlay {
    position: absolute;
    top: 5px;
    right: 5px;
    z-index: 100;
    display: flex;
    align-items: center;
    gap: 12px;
}

.switch-container {
    display: flex;
    align-items: center;
    gap: 4px;
    background: rgba(255, 255, 255, 0.8);
    padding: 2px 6px;
    border-radius: 12px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
}

.switch-container i {
    font-size: 0.7rem;
    color: #94a3b8;
    transition: color 0.2s;
}

.switch-container i.active-icon {
    color: #3b82f6;
}

:deep(.tiny-switch) {
    transform: scale(0.6);
}

.camera-container {
    width: 100%;
    flex: 1;
    min-height: 120px;
    position: relative;
    border-radius: 8px;
    overflow: hidden;
    background: #000;
}

.quagga-container {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    overflow: hidden;
}

:deep(.quagga-container video), 
:deep(.quagga-container canvas) {
    width: 100%;
    height: 100%;
    object-fit: cover;
}

.laser-line {
    position: absolute;
    top: 50%;
    left: 10%;
    right: 10%;
    height: 2px;
    background: red;
    opacity: 0.6;
    z-index: 50;
    box-shadow: 0 0 8px red;
    pointer-events: none;
    transition: background 0.3s, box-shadow 0.3s;
}

.laser-locked {
    background: gray;
    box-shadow: 0 0 8px gray;
}

.laser-container {
    width: 100%;
    flex: 1;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    background: #e2e8f0;
    border-radius: 8px;
    min-height: 80px;
    transition: background 0.3s ease;
}

.laser-container:not(.focus-disabled)::after {
    content: "ESCANER LASER LISTO";
    font-weight: 800;
    color: #475569;
    font-size: 0.8rem;
}

.focus-disabled {
    background: #ffedd5;
    border: 2px dashed #f97316;
}

.focus-warning {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 5px;
    color: #c2410c;
    font-weight: 900;
    font-size: 0.8rem;
}

.focus-warning i {
    font-size: 1.5rem;
}

.hidden-input {
    opacity: 0;
    position: absolute;
    left: -9999px;
    width: 1px;
    height: 1px;
}

.error-msg {
    width: 100%;
    margin-top: 5px;
}

.message-container {
    width: 100%;
    margin-top: 5px;
}

.instruction-msg {
    width: 100%;
    margin: 0;
}

:deep(.p-message-wrapper) {
    padding: 0.5rem !important;
}
</style>