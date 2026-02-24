<template>
    <div style="padding: 1em; width: 100%; height: 100%; display: flex; flex-direction: column;">
        <div v-if="camera_init" style="width: 100%; height: 100%; position:relative ">
            <Button v-if="can_close" @click="closeScanner" label="&#10006;" style="position: absolute; top: 10px; right: 10px; z-index: 100;" />
            <video
                ref="qrScanner"
                playsinline
                muted
                style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; object-fit: cover; background: black; color: white;"
            ></video>
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
        async mountQRScanner() {
            const video = this.$refs.qrScanner;
            if (!video) return false;

            let processing = false;

            try {
                this.scanner = new window.QrScanner(
                    video,
                    async result => {
                        if (processing) return;
                        processing = true;

                        this.scanner.pause(true);

                        const data = result.data || result;
                        if (this.context){
                            this.store.executeActionByContext(this.context, data, this.extra_data)
                        }
                        else if (this.onScan) {
                            await this.onScan(data);
                        }
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
                await this.$nextTick();
                await new Promise(resolve => setTimeout(resolve, 200));
                const success = await this.mountQRScanner();
                if (!success) this.camera_init = false;
            } catch (err) {
                this.error = "Camera error";
                this.camera_init = false;
            }
        },
        closeScanner() {
            if (this.scanner) {
                this.scanner.destroy();
                this.scanner = null;
            }
            this.camera_init = false;
        }
    },
    components: { Button, Message }
}
</script>