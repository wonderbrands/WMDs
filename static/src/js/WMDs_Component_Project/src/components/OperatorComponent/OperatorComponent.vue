<template>
    <!-- TASK LIST -->
    <div
        v-if="!operator_task"
        style="overflow-y: scroll; padding: 1em; width: 100%; height: 100%; display: flex; flex-direction: column;"
    >
        <h3 style="margin: 1em;">Bienvendido {{ store.role.user }}</h3>
        <Card v-for="task in tasks" :key="task.id" style="margin: 1em;">
            <template #title>{{ task.title }}</template>
            <template #subtitle>{{ task.description }}</template>

            <template
                #content
                v-if="
                    assigned_tasks[task.id] &&
                    assigned_tasks[task.id][0] &&
                    assigned_tasks[task.id][0].children
                "
            >
                <span v-if="assigned_tasks[task.id][0].children.length > 0" style="font-style: italic; color: red;">
                    {{ assigned_tasks[task.id][0].children.length }} pendientes
                </span>
            </template>

            <template #footer>
                <Tree
                    v-if="assigned_tasks[task.id] && assigned_tasks[task.id][0] && assigned_tasks[task.id][0].children.length > 0"
                    :value="assigned_tasks[task.id]"
                    selectionMode="single"
                    v-model:selectionKeys="current_task[task.id]"
                    style="width: 100%;"
                    @node-select="openTask"
                />

                <div v-else style="padding: 1em; color: #666; font-style: italic;">
                    Sin tareas asignadas
                </div>
            </template>
        </Card>
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
                        ]
                    }
                ],

                disponibilizar: [
                    {
                        key: "disponibilizar-root",
                        label: "Asignados a mi",
                        selectable: false,
                        children: [
                           
                        ]
                    }
                ],

                traslados: [
                    {
                        key: "traslados-root",
                        label: "Asignados a mi",
                        selectable: false,
                        children: [
                           
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


    methods: {

        async openTask(event) {
            console.log("openTask", event)
            const pick = event.data;
            const urlBarcode = await this.store.odoo_middleware.getFromOdoo(
                "get_barcode_url", 
                "",
                { pick_name: pick }
            )
            await this.store.odoo_middleware.getFromOdoo(
                "log_record",
                "",
                {
                    pick_name: pick,
                    operator_mail: this.store.role.email,
                    message: `La operación ha sido abierta por el operador`,
                }
            )
            await this.store.odoo_middleware.getFromOdoo(
                "change_status", 
                "",
                { pick_name: pick, status: "in_progress" }
            )
            window.location.href = urlBarcode
            
        },
    }
};
</script>
