<template>
    <div  class="task-container">
        <h3 class="welcome-header">Bienvenido {{ store.role.user }}</h3>
        
        <Card v-for="task in activeTasks" :key="task.id" class="task-card">
            <template #title>{{ task.title }}</template> 
            <template #subtitle>{{ task.description }}</template>

            <template #content v-if="task.assigned.length > 0 && !task.view">
                <span class="pending-badge">
                    {{ task.assigned[0].children.length }} pendientes
                </span>
            </template>

            <template #footer>
                <Tree
                    v-if="hasChildren(task)"
                    :value="task.assigned"
                    selectionMode="single"
                    v-model:selectionKeys="current_task[task.id]"
                    @node-select="openTask"
                    class="full-width"
                />
                <div v-else-if="task.view"
                @click="createView(task)">
                    {{ task.label }}
                </div>
                <div v-else class="empty-tasks">
                    Sin tareas asignadas
                </div>
            </template>
        </Card>
        <LogoutComponent style="width: 100%;"/>
    </div>
</template>

<script>
import Card from "primevue/card";
import Tree from "primevue/tree";
import LogoutComponent from "../RolePicker/LogoutComponent.vue"
import { useGeneralStore } from "../../store/index";

export default {
    name: "OperatorComponent",
    components: { Card, Tree, LogoutComponent },

    data() {
        return {
            store: useGeneralStore(),
            current_task: {},
            mountExtraView: false,
            taskDefinitions: [
                { id: "ingresos", title: "Recepciones", description: "Validación de productos ingresados.", fetch: true, label: "Asignados a mi" },
                { id: "acomodo", title: "Acomodo/Storage", description: "Acomodo de productos.", fetch: true, label: "Abiertos" },
                { id: "traslados", title: "Traslados", description: "Traslado interno entre ubicaciones.", fetch: false, label: "Asignados a mi" },
                { id: "batch_pick", title: "Plan de pickeo", description: "Preparación para empaque.", fetch: true, label: "Asignados a mi" },
                { id: "conteo_ciclico", title: "Conteo cíclico", description: "Conteo de unidades.", fetch: false, label: "Pendientes" },
                { id: "bin", title:"Ingresar pedidos a BIN", description:"Ingresar pedidos a BIN", fetch: false, label: "Registrar", view: "BinComponent" },
                { id: "dock", title:"Trasladar a DOCK", description:"Trasladar a DOCK", fetch: false, label: "Registrar", view: "DockComponent" },

            ],
            tasks: []
        };
    },

    computed: {
        activeTasks() {
            return this.tasks;
        }
    },

    async mounted() {
        this.store.loading = true;
        
        this.tasks = this.taskDefinitions.map(t => ({
            ...t,
            assigned: [{
                key: `${t.id}-root`,
                label: t.label,
                selectable: false,
                children: []
            }]
        }));

        try {
            const fetchPromises = this.tasks
                .filter(t => t.fetch)
                .map(async (task) => {
                    const data = await this.store.odoo_middleware.getFromOdoo(
                        "pending_tasks",
                        task.id,
                        { email: this.store.role.email }
                    );
                    
                    task.assigned[0].children = (data || []).map((p, i) => ({
                        key: `${task.id}-${i}`,
                        label: p.label || p,
                        data: p.data || p,
                        leaf: true
                    }));
                });

            await Promise.all(fetchPromises);
        } catch (error) {
            console.error("Error cargando tareas:", error);
        } finally {
            this.store.loading = false;
        }
    },

    methods: {
        hasChildren(task) {
            return task.assigned?.[0]?.children?.length > 0;
        },

        async openTask({ data: pick }) {
            const { odoo_middleware, role } = this.store;
            
            const urlPromise = odoo_middleware.getFromOdoo("get_barcode_url", "", { pick_name: pick });
            window.location.href = await urlPromise;
        },
        createView(task){
            this.store.mandatory_uncompleted.component = task.view
        }
    }
};
</script>
