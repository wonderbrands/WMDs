<template>
    <div style="padding: 1em; width: 100%; height: 100%; display: flex; flex-direction: column;">
        <div v-if="camera_init" style="width: 100%; height: 100%; position:relative ">
            <Button v-if="can_close" @click="closeScanner" label="&#10006;" style="position: absolute; top: 10px; right: 10px; z-index: 100;" />
            <video
                ref="barcodeScanner"
                playsinline
                muted
                style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; object-fit: cover; background: black; color: white;"
            ></video>
            <div style="position: absolute; top: 50%; left: 10%; right: 10%; height: 2px; background: red; opacity: 0.5; z-index: 50; box-shadow: 0 0 8px red;"></div>
        </div>
        <Message v-else style="width: 100%; height: 100%;" severity="error">{{ error }}</Message>
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
            scanner: null,
            error: null
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
        console.log("BarcodeScanner: Iniciando flujo de montaje");
        this.initCamera();
    },
    beforeUnmount() {
        console.log("BarcodeScanner: Destruyendo instancia antes del desmontaje");
        this.closeScanner();
    },
    methods: {
        async mountBarcodeScanner() {
            const video = this.$refs.barcodeScanner;
            if (!video) {
                console.log("BarcodeScanner Error: Referencia de video no encontrada");
                return false;
            }

            try {
                this.scanner = new window.QrScanner(
                    video,
                    result => {
                        const data = result.data || result;
                        console.log("BarcodeScanner detectado:", data);
                        if (this.onScan) this.onScan(data);
                    },
                    { 
                        preferredCamera: "environment", 
                        highlightScanRegion: true, 
                        returnDetailedScanResult: true,
                        maxScansPerSecond: 10,
                        highlightCodeOutline: true
                    }
                );

                console.log("BarcodeScanner: Instancia creada, iniciando motor");
                await this.scanner.start();
                
                const hasFlash = await this.scanner.hasFlash();
                console.log("BarcodeScanner: Cámara iniciada. Flash disponible:", hasFlash);
                
                return true;
            } catch (err) {
                console.log("BarcodeScanner Excepción:", err.message);
                this.error = `Error: ${err.message}`;
                return false;
            }
        },
        async initCamera() {
            try {
                this.camera_init = true;
                console.log("BarcodeScanner: Solicitando acceso a cámara");
                await this.$nextTick();
                await new Promise(resolve => setTimeout(resolve, 300));
                
                const success = await this.mountBarcodeScanner();
                if (!success) {
                    console.log("BarcodeScanner: Falló mountBarcodeScanner");
                    this.camera_init = false;
                }
            } catch (err) {
                console.log("BarcodeScanner Critical Error:", err);
                this.error = "Permissions error";
                this.camera_init = false;
            }
        },
        closeScanner() {
            if (this.scanner) {
                console.log("BarcodeScanner: Ejecutando destroy()");
                this.scanner.destroy();
                this.scanner = null;
            }
            this.camera_init = false;
        }
    },
    components: { Button, Message }
}
</script>