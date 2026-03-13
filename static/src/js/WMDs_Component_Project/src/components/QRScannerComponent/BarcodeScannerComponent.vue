<template>
    <div class="scanner-wrapper" @click="focusLaserInput">
        <div class="controls-overlay">
            <ButtonCamera @click="setReader('camera')" class="control-btn" />
            <ButtonScanner @click="setReader('laser')" class="control-btn" />
            <Button v-if="can_close" @click="closeScanner" label="&#10006;" class="control-btn close-btn" />
        </div>

        <div v-if="reader === 'camera'" v-show="camera_init" class="camera-container">
            <div ref="barcodeScanner" class="quagga-container"></div>
            <div class="laser-line" :class="{ 'laser-locked': scan_lockout }"></div>
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
    name: "BarcodeScannerComponent", 
    data() {
        return {
            store: useGeneralStore(),
            camera_init: false,
            error: null,
            is_scanning: false,
            reader: "laser",
            laser_input: "",
            scan_lockout: false,
            inputTimeout: null,
            quagga_running: false
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
            this.is_scanning = false;
            if (window.Quagga && this.quagga_running) {
                window.Quagga.stop();
                window.Quagga.offDetected();
                this.quagga_running = false;
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
        triggerScan(code) {
            console.log("triggerScan", code);
            this.scan_lockout = true;
            this.playBeep();
            
            if (this.onScan) {
                this.onScan(code);
            }

            setTimeout(() => {
                console.log("scan_lockout lifted");
                this.scan_lockout = false;
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

.quagga-container {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: black;
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
    opacity: 0.5;
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
    flex: 0 0 10%; 
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