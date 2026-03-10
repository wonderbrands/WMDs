<template>
    <div class="scanner-wrapper">
        <div class="controls-overlay">
            <ButtonCamera @click="setReader('camera')" class="control-btn" />
            <ButtonScanner @click="setReader('laser')" class="control-btn" />
            <Button v-if="can_close" @click="closeScanner" label="&#10006;" class="control-btn close-btn" />
        </div>

        <div v-if="reader === 'camera'" v-show="camera_init" class="camera-container">
            <video ref="qrScanner" playsinline muted class="qr-video"></video>
        </div>

        <div v-if="reader === 'laser'" class="laser-container">
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
            lastKeyTime: 0
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
        if (this.reader === 'camera') {
            this.initCamera();
        }
        window.addEventListener('keydown', this.handleGlobalKeydown);
    },
    beforeUnmount() {
        this.closeScanner();
        window.removeEventListener('keydown', this.handleGlobalKeydown);
    },
    methods: {
        handleGlobalKeydown(e) {
            if (this.reader !== 'laser' || this.scan_lockout) return;
            
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;

            const currentTime = Date.now();
            
            if (currentTime - this.lastKeyTime > 100) {
                this.laser_input = "";
            }
            this.lastKeyTime = currentTime;

            if (e.key === 'Enter') {
                if (this.laser_input.trim() !== "") {
                    e.preventDefault();
                    this.triggerScan(this.laser_input);
                    this.laser_input = "";
                }
                return;
            }

            if (e.key.length === 1) {
                this.laser_input += e.key;
            }
        },
        async mountQRScanner() {
            const video = this.$refs.qrScanner;
            if (!video) return false;
            try {
                this.scanner = new window.QrScanner(
                    video,
                    async result => {
                        if (this.scan_lockout) return;
                        const data = result.data || result;
                        this.triggerScan(data);
                    },
                    { preferredCamera: "environment", highlightScanRegion: true }
                );
                await this.scanner.start();
                return true;
            } catch (err) {
                this.error = `Error: ${err.message}`;
                return false;
            }
        },
        async initCamera() {
            try {
                this.camera_init = true;
                this.scan_lockout = false;
                await this.$nextTick();
                await new Promise(resolve => setTimeout(resolve, 200));
                const success = await this.mountQRScanner();
                if (!success) this.camera_init = false;
            } catch (err) {
                this.error = "Camera error";
                this.camera_init = false;
            }
        },
        setReader(newReader) {
            this.reader = newReader;
            this.scan_lockout = false;
            this.laser_input = "";
            if (newReader === 'camera') {
                this.initCamera();
            } else {
                this.closeScanner();
            }
        },
        closeScanner() {
            if (this.scanner) {
                this.scanner.destroy();
                this.scanner = null;
            }
            this.camera_init = false;
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
                oscillator.stop(ctx.currentTime + 0.1);
            } catch (error) {
                console.warn("AudioContext not supported");
            }
        },
        async triggerScan(code) {
            this.scan_lockout = true;
            this.playBeep();
            if (this.context){
                this.store.executeActionByContext(this.context, code, this.extra_data);
            } else if (this.onScan) {
                await this.onScan(code);
            }
            setTimeout(() => {
                this.scan_lockout = false;
                this.laser_input = "";
            }, 3000);
        }
    },
    components: { Button, Message, ButtonCamera, ButtonScanner }
}
</script>

<style scoped>
.scanner-wrapper {
    padding: 1em;
    width: 100%;
    height: 100%;
    display: flex;
    flex-direction: column; 
    position: relative;
    box-sizing: border-box;
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
    flex: 0 0 80%; 
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
    flex: 0 0 10%; 
    display: flex;
    flex-direction: column;
    justify-content: center;
}

.error-msg {
    width: 100%;
    margin-top: 10px;
}

.message-container {
    width: 100%;
    flex: 1; 
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