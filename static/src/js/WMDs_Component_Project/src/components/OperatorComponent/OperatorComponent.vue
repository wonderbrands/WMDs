<template>
    <div
        v-if="!operator_task"
        style="overflow-y: scroll; padding: 1em; width: 100%; height: 100%; display: flex; flex-direction: column;"
    >
        <Card v-for="task in tasks" :key="task.id" style="margin: 1em;">
            <template #title>{{ task.title }}</template>
            <template #subtitle>{{ task.description }}</template>

            <template #footer>
                <Tree
                    v-if="assigned_tasks[task.id]?.length"
                    :value="assigned_tasks[task.id]"
                    selectionMode="single"
                    v-model:selectionKeys="current_task[task.id]"
                    style="width: 100%;"
                    @node-select="openTask"
                />
            </template>
        </Card>
    </div>

    <div v-else style="padding: 1em;">
        <button @click="closeScanner">⬅ Volver</button>

        <video
            ref="qrScanner"
            playsinline
            muted
            style="
                width: 100%;
                height: 60vh;
                object-fit: cover;
                background: black;
                margin-top: 1em;
            "
        ></video>
    </div>
</template>

<script>
import Card from "primevue/card";
import Tree from "primevue/tree";
import { useGeneralStore } from "../../store/index";

export default {
    name: "OperatorComponent",

    components: { Card, Tree },

    data() {
        return {
            store: useGeneralStore(),
            operator_task: false,
            current_task: {},
            scanner: null,

            tasks: [
                { id: "ingreso", title: "Recepciones", description: "" },
                { id: "disponibilizar", title: "Disponibilizar", description: "" }
            ],

            assigned_tasks: {
                ingreso: [{ key: "root", label: "Asignados", selectable: false, children: [] }],
                disponibilizar: [{ key: "root", label: "Asignados", selectable: false, children: [] }]
            }
        };
    },

    watch: {
        operator_task(enabled) {
            if (!enabled) return;

            this.$nextTick(() => {
                const video = this.$refs.qrScanner;
                if (!video) return;

                this.scanner = new window.QrScanner(
                    video,
                    result => {
                        console.log("✅ QR decoded:", result.data || result);
                        this.closeScanner();
                    },
                    {
                        preferredCamera: "environment",
                        highlightScanRegion: true,
                        highlightCodeOutline: true,
                        returnDetailedScanResult: true
                    }
                );

                // ✅ DO NOT call video.play()
                this.scanner.start().catch(err => {
                    console.error("Scanner start failed:", err);
                });
            });
        }
    },

    methods: {
        async requestCameraPermission() {
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ video: true });
                stream.getTracks().forEach(t => t.stop());
                return true;
            } catch (e) {
                alert("Camera permission denied or unavailable");
                return false;
            }
        },

        async openTask(event) {
            const node = event?.node;
            if (!node || node.selectable === false) return;

            const allowed = await this.requestCameraPermission();
            if (!allowed) return;

            this.operator_task = true;
        },

        closeScanner() {
            if (this.scanner) {
                this.scanner.stop();
                this.scanner.destroy();
                this.scanner = null;
            }
            this.operator_task = false;
        }
    },

    beforeUnmount() {
        if (this.scanner) {
            this.scanner.stop();
            this.scanner.destroy();
        }
    }
};
</script>
