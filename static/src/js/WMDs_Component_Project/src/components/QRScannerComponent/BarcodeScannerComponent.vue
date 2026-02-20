<template>
    <div style="padding: 1em; width: 100%; height: 100%; display: flex; flex-direction: column;">
        <div v-show="camera_init" style="width: 100%; height: 100%; position:relative ">
            <Button v-if="can_close" @click="closeScanner" label="&#10006;" style="position: absolute; top: 10px; right: 10px; z-index: 100;" />
            
            <div 
                ref="barcodeScanner" 
                class="quagga-container"
                style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; background: black; overflow: hidden;"
            ></div>

            <div style="position: absolute; top: 50%; left: 10%; right: 10%; height: 2px; background: red; opacity: 0.5; z-index: 50; box-shadow: 0 0 8px red; pointer-events: none;"></div>
        </div>

        <Message v-if="!camera_init && error" style="width: 100%; height: 100%;" severity="error">{{ error }}</Message>
        <Message v-if="instructions && camera_init" style="position: absolute; bottom: 5px; width: 90%; left: 5%; z-index: 10;" severity="info">{{ instructions }}</Message>
    </div>
</template>

<script>
    import Button from 'primevue/button';
    import Message from 'primevue/message';
    import { useGeneralStore } from "../../store/index"

    export default {
    name: "BarcodeScannerComponent", 
    data() {
        return {
            store: useGeneralStore(),
            camera_init: false,
            error: null,
            is_scanning: false 
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
        this.initCamera();
    },
    beforeUnmount() {
        this.closeScanner();
    },
    methods: {
        initCamera() {
            this.camera_init = true;
            this.is_scanning = true;
            
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
                    // Optimized to only read the most common industrial formats
                    readers: ["code_128_reader", "ean_reader", "code_39_reader"]
                },
                locate: true
            }, (err) => {
                if (err) {
                    this.error = "Camera access failed";
                    this.camera_init = false;
                    return;
                }
                window.Quagga.start();
                this.setupDetection();
            });
        },

        setupDetection() {
            window.Quagga.onDetected((result) => {
                if (!this.is_scanning) return;

                if (result && result.codeResult && result.codeResult.code) {
                    const code = result.codeResult.code;
                    
                    // Immediately lock and stop to prevent multiple scans
                    this.is_scanning = false;
                    window.Quagga.stop();

                    if (this.onScan) {
                        this.onScan(code);
                    }
                }
            });
        },

        closeScanner() {
            this.is_scanning = false;
            if (window.Quagga) {
                window.Quagga.stop();
                window.Quagga.offDetected();
            }
            this.camera_init = false;
        }
    },
    components: { Button, Message }
}
</script>

<style>
:deep(.quagga-container video), :deep(.quagga-container canvas) {
    width: 100%;
    height: 100%;
    object-fit: cover;
}
</style>