<template>
    <div style="padding: 1em; width: 100%; height: 100%; display: flex; flex-direction: column;">
        <div v-if="camera_init" style="width: 100%; height: 50%; position:relative ">
            <Button v-if="can_close" @click="closeScanner" label="&#10006;" style="position: absolute; top: 10px; right: 10px; z-index: 100;" />
            <video
                ref="barcodeScanner"
                playsinline
                muted
                style="
                    position: absolute;
                    top: 0;
                    left: 0;
                    width: 100%;
                    height: 100%;
                    object-fit: cover;
                    background: black;
                    color: white;"
            > 
            </video>
            <div style="position: absolute; top: 50%; left: 10%; right: 10%; height: 2px; background: red; opacity: 0.5; z-index: 50; box-shadow: 0 0 8px red;"></div>
        </div>
        <Message v-else style="width: 100%; height: 50%;" severity="error">{{ error }}</Message>

        <Message v-if="instructions" style="width: 100%; height: 50%;" severity="info">{{ instructions }}</Message>
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
            scanner: null,
            error: null
        }
    },
    props: {
        context: {
            type: String,
            required: true
        },
        instructions: {
            type: String,
            required: true
        },
        can_close: {
            type: Boolean,
            required: false,
            default: false
        },
        onScan: {
            type: Function,
            required: false
        },
        extra_data: {
            type: Object,
            required: false
        }
    },
    mounted() {
        this.initCamera();
        this.store.loading = false
    },
    beforeUnmount() {
        this.closeScanner();
    },
    methods: {
        async mountBarcodeScanner() {
            const video = this.$refs.barcodeScanner;
            if (!video) {
                console.error("Video element not found");
                return false;
            }

            try {
                this.scanner = new window.QrScanner(
                    video,
                    result => {
                        const barcodeData = result.data || result;
                        console.log("Decoded Barcode:", barcodeData);
                        
                        if (this.onScan) {
                            this.onScan(barcodeData);
                        } else if (this.context) {
                            this.store.executeActionByContext(this.context, barcodeData, this.extra_data);
                        }
                        this.store.last_scanned_element = barcodeData;
                        
                        this.closeScanner();
                    },
                    {
                        preferredCamera: "environment",
                        highlightScanRegion: true,
                        highlightCodeOutline: true,
                        returnDetailedScanResult: true 
                    }
                );
                
                await this.scanner.start();
                console.log("Barcode Scanner started successfully");
                return true;
            } catch (err) {
                console.error("Error starting barcode scanner:", err);
                this.error = `Error iniciando escáner: ${err.message || err}`;
                this.camera_init = false;
                return false;
            }
        },

        async initCamera() {
            try {
                this.camera_init = true;
                await this.$nextTick();
                const success = await this.mountBarcodeScanner();
                if (!success) {
                    this.camera_init = false;
                }
            } catch (err) {
                this.error = `Error de permisos en la cámara: ${err.message || err}`;
                console.error(this.error);
                this.camera_init = false;
            }
        },

        closeScanner() {
            console.log("Closing scanner");
            if (this.scanner) {
                this.scanner.stop();
                this.scanner.destroy();
                this.scanner = null;
            }
            this.camera_init = false;
        }
    },
    components: {
        Button,
        Message
    }
}
</script>