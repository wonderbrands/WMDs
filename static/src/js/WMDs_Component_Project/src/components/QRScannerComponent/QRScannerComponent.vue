<template>
    <div style="padding: 1em; width: 100%; height: 100%; display: flex; flex-direction: column;">
        <div  v-if="camera_init" style="width: 100%; height: 100%; position:relative ">
            <Button v-if="can_close" @click="closeScanner" label="&#10006;" style="position: absolute; top: 10px; right: 10px; z-index: 100;" />
            <video
                ref="qrScanner"
                playsinline
                muted
                style="
                    position: absolute;
                    top: 0;
                    left: 0;
                    width: 100%;
                    height: 50%;
                    object-fit: cover;
                    background: black;
                    color: white;"
            > 
            </video>
        </div>
        <Message v-else  style="width: 100%; height: 50%;" severity="error">{{ error }}</Message>

        <Message v-if="instructions" style="width: 100%; height: 50%;" severity="info">{{ instructions }}</Message>
        
    </div>
</template>
<script>
    import Button from 'primevue/button';
    import Message from 'primevue/message';
    import { useGeneralStore } from "../../store/index"

    export default {
        name: "QRScannerComponent", 
        data() {
            return {
                store: useGeneralStore(),
                camera_init: false,
                scanner: null,
                error: null
            }
        },
        props: {
            context:
                {
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
            onScan:{
                    type: Function,
                    required: false
                }
        },
        beforeMount() {
            this.initCamera();
        },
        methods: {
            async mountQRScanner() {
                const video = this.$refs.qrScanner;
                if (!video) return;

                this.scanner = new window.QrScanner(
                    video,
                    result => {
                        console.log("Decoded QR:", result.data || result);
                        if (this.onScan) this.onScan(result.data || result);
                        this.store.last_scanned_element = result.data || result;
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
            },
            async requestCameraPermission() {
                try {
                    const stream = await navigator.mediaDevices.getUserMedia({ video: true });
                    stream.getTracks().forEach(t => t.stop());
                    await this.mountQRScanner();
                    return true;
                } catch (err) {
                    this.error = `Error de permisos en la camara:, ${err}`
                    console.error(this.error);
                    alert("No se pudo obtener acceso a la cámara");
                    return false;
                }
            },

            async initCamera(event) {
                this.camera_init = await this.requestCameraPermission();
                
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