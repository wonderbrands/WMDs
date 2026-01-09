<template>
    <!-- TASK LIST -->
    <div
        v-if="!operator_task"
        style="overflow-y: scroll; padding: 1em; width: 100%; height: 100%; display: flex; flex-direction: column;"
    >
        <Card v-for="task in tasks" :key="task.id" style="margin: 1em;">
            <!-- TITLE -->
            <template #title>{{ task.title }}</template>

            <!-- SUBTITLE -->
            <template #subtitle>{{ task.description }}</template>

            <!-- PENDING COUNT -->
            <template
                #content
                v-if="
                    assigned_tasks[task.id] &&
                    assigned_tasks[task.id][0] &&
                    assigned_tasks[task.id][0].children
                "
            >
                <span style="font-style: italic; color: red;">
                    {{ assigned_tasks[task.id][0].children.length }} pendientes
                </span>
            </template>

            <!-- TREE -->
            <template #footer>
                <Tree
                    v-if="assigned_tasks[task.id] && assigned_tasks[task.id].length > 0"
                    :value="assigned_tasks[task.id]"
                    selectionMode="single"
                    v-model:selectionKeys="current_task[task.id]"
                    style="width: 100%;"
                    @node-select="openTask"
                />

                <div
                    v-else
                    style="padding: 1em; color: #666; font-style: italic;"
                >
                    Sin tareas asignadas
                </div>
            </template>
        </Card>
    </div>

    <!-- QR SCANNER -->
    <div v-else style="padding: 1em;">
        <button @click="closeScanner">⬅ Volver</button>
        <video
            ref="qrScanner"
            playsinline
            muted
            style="width: 100%; margin-top: 1em;"
        ></video>
    </div>
</template>

<script>
import Card from "primevue/card";
import Tree from "primevue/tree";
import { useGeneralStore } from "../../store/index";

export default {
    name: "OperatorComponent",

    components: {
        Card,
        Tree
    },

    data() {
        return {
            store: useGeneralStore(),
            current_task: {},
            operator_task: false,
            scanner: null,

            tasks: [
                { id: "ingreso", title: "Recepciones", description: "Validación de los productos ingresados a almacén." },
                { id: "disponibilizar", title: "Disponibilizar", description: "Traslado de productos desde posición de ingreso a alguna ubicación de almacén" },
                { id: "traslados", title: "Traslados", description: "Traslado de una ubicación interna de almacen a otra" },
                { id: "picks", title: "Picks", description: "Preparación del producto para proceso de entrega" },
                { id: "devoluciones", title: "Devoluciones", description: "" },
                { id: "resurtidos", title: "Resurtidos", description: "" },
                { id: "conteo_ciclico", title: "Conteo cíclico", description: "Conteo de unidades disponibles de N producto en X ubicación" }
            ],

            assigned_tasks: {
                ingreso: [
                    {
                        key: "ingreso-root",
                        label: "Asignados a mi",
                        selectable: false,
                        children: [
                            { key: "ingreso-0", label: "WH/IN/0001", data: "WH/IN/0001", leaf: true },
                            { key: "ingreso-1", label: "WH/IN/0002", data: "WH/IN/0002", leaf: true },
                            { key: "ingreso-2", label: "WH/IN/0003", data: "WH/IN/0003", leaf: true },
                            { key: "ingreso-3", label: "WH/IN/0004", data: "WH/IN/0004", leaf: true }
                        ]
                    }
                ],

                disponibilizar: [
                    {
                        key: "disponibilizar-root",
                        label: "Asignados a mi",
                        selectable: false,
                        children: [
                            { key: "disponibilizar-0", label: "WH/INT/0001", data: "WH/INT/0001", leaf: true },
                            { key: "disponibilizar-1", label: "WH/INT/0002", data: "WH/INT/0002", leaf: true },
                            { key: "disponibilizar-2", label: "WH/INT/0003", data: "WH/INT/0003", leaf: true },
                            { key: "disponibilizar-3", label: "WH/INT/0004", data: "WH/INT/0004", leaf: true }
                        ]
                    }
                ],

                traslados: [
                    {
                        key: "traslados-root",
                        label: "Asignados a mi",
                        selectable: false,
                        children: [
                            { key: "traslados-0", label: "WH/INT/0012", data: "WH/INT/0012", leaf: true },
                            { key: "traslados-1", label: "WH/INT/0013", data: "WH/INT/0013", leaf: true },
                            { key: "traslados-2", label: "WH/INT/0014", data: "WH/INT/0014", leaf: true },
                            { key: "traslados-3", label: "WH/INT/0015", data: "WH/INT/0015", leaf: true }
                        ]
                    }
                ],

                picks: [
                    {
                        key: "picks-root",
                        label: "Asignados a mi",
                        selectable: false,
                        children: []
                    }
                ],

                devoluciones: [],
                resurtidos: [],
                conteo_ciclico: []
            }
        };
    },

    async mounted() {
        this.store.loading = true;

        const picks = await this.store.odoo_middleware.getFromOdoo(
            "pending_tasks",
            "picks",
            { email: this.store.role.email }
        );

        this.assigned_tasks.picks[0].children =
            (picks || []).map((p, i) => ({
                key: `picks-${i}`,
                label: p.label || p,
                data: p.data || p,
                leaf: true
            }));

        this.store.loading = false;
    },

    watch: {
        operator_task(newVal) {
            if (!newVal) return;

            this.$nextTick(() => {
                if (!this.$refs.qrScanner) return;

                this.scanner = new window.QrScanner(
                    this.$refs.qrScanner,
                    result => {
                        console.log("Decoded QR:", result.data || result);
                    },
                    { returnDetailedScanResult: true }
                );

                this.scanner.start();
            });
        }
    },

    methods: {
        async requestCameraPermission() {
            try {
                const stream = await navigator.mediaDevices.getUserMedia({
                    video: { facingMode: "environment" }
                });
                stream.getTracks().forEach(t => t.stop());
                return true;
            } catch (err) {
                console.error("Camera permission error:", err);
                alert("Camera not available or permission denied");
                return false;
            }
        },

        async openTask(event) {
            const node = event?.node || event;

            if (!node || !node.data || node.selectable === false) {
                return;
            }

            console.log("Task selected:", {
                label: node.label,
                value: node.data,
                key: node.key
            });

            // 🔐 Ask for permission INSIDE the click handler
            const allowed = await this.requestCameraPermission();
            if (!allowed) return;

            // ✅ Only now show the scanner
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
    }
};
</script>
