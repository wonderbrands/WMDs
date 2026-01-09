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
    
            try {
                const picks = await this.store.odoo_middleware.getFromOdoo(
                    "pending_tasks",
                    "picks",
                    { email: this.store.role.email }
                );
    
                console.log("Picks response:", picks);
    
                if (picks && Array.isArray(picks)) {
                    this.assigned_tasks.picks[0].children = picks.map((p, i) => ({
                        key: `picks-${i}`,
                        label: p.label || p.name || p,
                        data: p.data || p.id || p,
                        leaf: true
                    }));
                } else if (picks && picks.data && Array.isArray(picks.data)) {
                    this.assigned_tasks.picks[0].children = picks.data.map((p, i) => ({
                        key: `picks-${i}`,
                        label: p.label || p.name || p,
                        data: p.data || p.id || p,
                        leaf: true
                    }));
                } else {
                    console.warn("Unexpected picks format:", picks);
                    this.assigned_tasks.picks[0].children = [];
                }
            } catch (error) {
                console.error("Error fetching picks:", error);
                this.assigned_tasks.picks[0].children = [];
            } finally {
                this.store.loading = false;
            }
        },
    
        watch: {
            operator_task(newVal) {
                if (!newVal) return;
    
                this.$nextTick(async () => {
                    const video = this.$refs.qrScanner;
                    if (!video) {
                        console.error("Video element not found");
                        return;
                    }
    
                    try {
                        // Wait a bit to ensure video is in DOM
                        await new Promise(resolve => setTimeout(resolve, 100));
    
                        this.scanner = new window.QrScanner(
                            video,
                            result => {
                                console.log("Decoded QR:", result.data || result);
                                this.closeScanner();
                            },
                            {
                                preferredCamera: "environment",
                                highlightScanRegion: true,
                                highlightCodeOutline: true,
                                returnDetailedScanResult: true
                            }
                        );
    
                        // Start scanner first, then play video
                        await this.scanner.start();
                    } catch (error) {
                        console.error("QR Scanner error:", error);
                        alert("Error al iniciar el escáner");
                        this.closeScanner();
                    }
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
                    alert("Cámara no disponible o permiso denegado");
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
    
                const allowed = await this.requestCameraPermission();
                if (!allowed) return;
    
                this.operator_task = true;
            },
    
            closeScanner() {
                if (this.scanner) {
                    try {
                        this.scanner.stop();
                        this.scanner.destroy();
                    } catch (error) {
                        console.error("Error closing scanner:", error);
                    }
                    this.scanner = null;
                }
                this.operator_task = false;
            }
        },
    
        beforeUnmount() {
            // Clean up scanner when component is destroyed
            this.closeScanner();
        }
    };
    </script>