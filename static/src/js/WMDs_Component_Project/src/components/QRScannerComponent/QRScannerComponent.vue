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
            <ButtonCamera @click="setReader('camera')" class="control-btn" />
            <ButtonScanner @click="setReader('laser')" class="control-btn" />
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
        
        <div class="message-container">
            <Message v-if="instructions && (camera_init || reader === 'laser')" class="instruction-msg" severity="info">
                {{ scan_lockout ? 'Please wait...' : instructions }}
            </Message>
        </div>
    </div>
</template>

<script>
import Button from 'primevue/button';
import Message from 'primevue/message';
import { useGeneralStore } from "../../store/index"
import ButtonCamera from '../ResuableComponentIcons/ButtonCamera.vue';
import ButtonScanner from '../ResuableComponentIcons/ButtonScanner.vue';

export default {
    name: "QRScannerComponent", 
    data() {
        return {
            store: useGeneralStore(),
            camera_init: false,
            scanner: null,
            error: null,
            reader: "laser",
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
        can_close: { type: Boolean, default: false },
        onScan: Function,
        extra_data: Object
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
        setReader(newReader) {
            console.log("setReader", newReader);
            this.reader = newReader;
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
        async triggerScan(code) {
            console.log("triggerScan", code);
            this.scan_lockout = true;
            this.playBeep();
            
            if (this.context){
                this.store.executeActionByContext(this.context, code, this.extra_data);
            } else if (this.onScan) {
                await this.onScan(code);
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
    components: { Button, Message, ButtonCamera, ButtonScanner }
}
</script>

<style scoped>
.scanner-wrapper {
    padding: 1em;
    width: 100%;
    display: flex;
    flex-direction: column; 
    position: relative;
    box-sizing: border-box;
    overflow-y: visible;
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
    z-index: 1000;
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
    top: 10px;
    right: 10px;
    z-index: 100;
    display: flex;
    gap: 10px;
}

.camera-container {
    width: 100%;
    height: 250px;
    position: relative;
    border-radius: 8px;
    overflow: hidden;
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
    display: flex;
    flex-direction: column;
    justify-content: center;
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
    margin-top: 10px;
}

.message-container {
    width: 100%;
    display: flex;
    align-items: center; 
    justify-content: center;
    margin-top: 10px;
}

.instruction-msg {
    width: 100%;
    margin: 0;
}
</style>