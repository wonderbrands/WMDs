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
            <video ref="qrScanner" playsinline muted class="qr-video"></video>
        </div>

        <div v-if="reader === 'laser'" class="laser-container">
            <input 
                ref="laserInput"
                type="text" 
                v-model="laser_input" 
                @input="handleInput"
                @blur="keepFocus"
                class="hidden-input"
                inputmode="none"
            >
        </div>

        <Message v-if="!camera_init && error && reader === 'camera'" class="error-msg" severity="error">{{ error }}</Message>
        
        <div class="message-container" v-if="!hideInstructions">
            <Message v-if="instructions && (camera_init || reader === 'laser')" class="instruction-msg" severity="info">
                {{ scan_lockout ? 'Procesando...' : instructions }}
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
    name: "QRScannerComponent", 
    data() {
        return {
            store: useGeneralStore(),
            camera_init: false,
            scanner: null,
            error: null,
            reader: "laser",
            isCameraMode: false,
            laser_input: "",
            scan_lockout: false,
            inputTimeout: null,
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
        queueMode: { type: Boolean, default: false }
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
            console.log("handleGlobalKeydown", e.key);
            if (this.reader === 'laser' && document.activeElement !== this.$refs.laserInput) {
                this.focusLaserInput();
            }
        },
        async mountQRScanner() {
            console.log("mountQRScanner");
            const video = this.$refs.qrScanner;
            if (!video) return false;

            try {
                this.scanner = new window.QrScanner(
                    video,
                    async result => {
                        if (this.scan_lockout) return;
                        const data = result.data || result;
                        console.log("QR scanned", data);
                        this.triggerScan(data);
                    },
                    { preferredCamera: "environment", highlightScanRegion: true }
                );
                await this.scanner.start();
                return true;
            } catch (err) {
                console.log("QR scanner error", err.message);
                this.error = `Error: ${err.message}`;
                return false;
            }
        },
        async initCamera() {
            console.log("initCamera");
            try {
                this.camera_init = true;
                this.scan_lockout = false;
                await this.$nextTick();
                await new Promise(resolve => setTimeout(resolve, 200));
                const success = await this.mountQRScanner();
                if (!success) this.camera_init = false;
            } catch (err) {
                console.log("Camera initialization failed");
                this.error = "Camera error";
                this.camera_init = false;
            }
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
            if (this.scanner) {
                this.scanner.destroy();
                this.scanner = null;
            }
            this.camera_init = false;
        },
        focusLaserInput() {
            console.log("focusLaserInput");
            if (this.reader === 'laser' && this.$refs.laserInput) {
                this.$refs.laserInput.focus();
            }
        },
        keepFocus() {
            console.log("keepFocus");
            if (this.reader === 'laser') {
                setTimeout(() => {
                    this.focusLaserInput();
                }, 10);
            }
        },
        handleInput() {
            if (this.scan_lockout && !this.queueMode && this.reader !== 'laser') {
                this.laser_input = "";
                return;
            }

            if (this.inputTimeout) {
                clearTimeout(this.inputTimeout);
            }

            this.inputTimeout = setTimeout(() => {
                this.processScanedData();
            }, 30); 
        },
        processScanedData() {
            const raw = this.laser_input.trim();
            if (raw !== "") {
                this.laser_input = "";
                this.triggerScan(raw); 
            }
        },
        playBeep() {
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
                oscillator.stop(ctx.currentTime + 0.08);
            } catch (error) {
                // AudioContext not supported
            }
        },
        async triggerScan(code) {
            console.log("triggerScan", code);
            this.playBeep();

            if (this.reader === 'camera') {
                this.scan_lockout = true;
                setTimeout(() => {
                    this.scan_lockout = false;
                }, 800);
            } else if (!this.queueMode) {
                this.scan_lockout = true;
                setTimeout(() => {
                    this.scan_lockout = false;
                }, 200);
            } else {
                this.scan_lockout = false;
            }
            
            if (this.context){
                this.store.executeActionByContext(this.context, code, this.extra_data);
            } else if (this.onScan) {
                await this.onScan(code);
            }
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

.qr-video {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    object-fit: cover;
    background: black;
    color: white;
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
}

.laser-container::after {
    content: "ESCANER LASER LISTO";
    font-weight: 800;
    color: #475569;
    font-size: 0.8rem;
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