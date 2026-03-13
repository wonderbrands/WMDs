<template>
    <PickerView v-if="store.role.permissions.includes('WMDs Operator - Packer')" />

    <div class="task-container" v-else>
        <h3 class="welcome-header">Bienvenido {{ store.role.user }}</h3>
        
        <div class="cards-grid">
            <Card v-for="task in filteredTasks" :key="task.id" class="task-card">
                <template #title>{{ task.title }}</template> 
                <template #subtitle>{{ task.description }}</template>

                <template #content v-if="task.assigned.length > 0 && !task.view">
                    <span class="pending-badge">
                        {{ task.assigned[0].children.length }} pendientes
                    </span>
                </template>
                <template #content v-else-if="task.assigned.length === 0 && !task.view">
                    <span class="pending-badge">Sin pendientes</span>
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
                    <div v-else-if="task.view" class="custom-view-btn" @click="createView(task)">
                        {{ task.label }}
                    </div>
                    <div v-else class="empty-tasks">
                        Sin tareas asignadas
                    </div>
                </template>
            </Card>
        </div>

        <div class="logout-wrapper">
            <LogoutComponent class="logout-btn-60" />
        </div>
    </div>
</template>

<script>
import Card from "primevue/card";
import Tree from "primevue/tree";
import PickerView from "./PickerView.vue";
import LogoutComponent from "../RolePicker/LogoutComponent.vue";
import { useGeneralStore } from "../../store/index";

export default {
    name: "OperatorComponent",
    components: { Card, Tree, LogoutComponent, PickerView },

    data() {
        return {
            store: useGeneralStore(),
            current_task: {},
            taskDefinitions: [
                { id: "ingresos", title: "Recepciones", description: "Validación de ingresos.", fetch: true, label: "Abiertas", permission: "WMDs Operator - Reception" },
                { id: "acomodo", title: "Rackeo", description: "Acomodo de productos.", fetch: true, label: "Abiertos", permission: "WMDs Operator - Forklift operator" },
                { id: "traslados", title: "Traslados", description: "Traslado interno.", fetch: false, label: "Asignados", permission: "WMDs Operator - Forklift operator" },
                { id: "batch_pick", title: "Plan de pickeo", description: "Preparación empaque.", fetch: true, label: "Asignados", permission: "WMDs Operator - Picker" },
                { id: "conteo_ciclico", title: "Conteo cíclico", description: "Conteo de unidades.", fetch: false, label: "Pendientes", permission: "WMDs Operator - Forklift operator" },
                { id: "bin", title:"BIN", description:"Ingresar a BIN", fetch: false, label: "Registrar", view: "BinComponent", permission: "WMDs Operator - BIN" },
                { id: "dock", title:"DOCK", description:"Trasladar a DOCK", fetch: false, label: "Registrar", view: "DockComponent", permission: "WMDs Operator - DOCK" },
                { id: "dispatch", title:"Despacho", description:"Entrega paquetera", fetch: false, label: "Registrar", view: "DispatchComponent", permission: "WMDs Operator - Dispatch" },
                { id: "cycle_count_assigned", title: "Coneto cíclico", description: "Conteo de inventario por ubicación", fetch: true, label: "Asignados", permission: "WMDs Operator - Stock counter" },
            ],
            tasks: []
        };
    },

    computed: {
        filteredTasks() {
            const perms = this.store.role.permissions || [];
            // Si es Manager ve todo, si no, filtramos por el campo 'permission'
            if (perms.includes('WMDs Manager')) return this.tasks;
            return this.tasks.filter(t => perms.includes(t.permission));
        }
    },

    async mounted() {
        // 1. Obtener la zona horaria del navegador del cliente
        const clientTimeZone = Intl.DateTimeFormat().resolvedOptions().timeZone;

        this.tasks = this.taskDefinitions.map(t => ({
            ...t,
            assigned: [{ key: `${t.id}-root`, label: t.label, selectable: false, children: [] }]
        }));

        let data=null;
        const fetchPromises = this.filteredTasks
            .filter(t => t.fetch)
            .map(async (task) => {
                if(task.id==="cycle_count_assigned"){
                    data = await this.store.callOdoo(task.id, "" , { 
                            email: this.store.role.email,
                            tz: clientTimeZone 
                        });
                } else {
                    data = await this.store.callOdoo("pending_tasks", task.id, { 
                        email: this.store.role.email,
                        tz: clientTimeZone 
                    });
                }
                task.assigned[0].children = (data || []).map((p, i) => ({
                        key: `${task.id}-${i}`,
                        label: p.label || p,
                        data: p.data || p,
                        leaf: true
                }));
                
            });
        await Promise.all(fetchPromises);
    },

    methods: {
        hasChildren(task) {
            return task.assigned?.[0]?.children?.length > 0;
        },
        async openTask({ data: pick }) {
            const url = await this.store.callOdoo("get_barcode_url", "", { pick_name: pick });
            window.location.href = url;
        },
        createView(task){
            this.store.mandatory_uncompleted.component = task.view;
        }
    }
};
</script>

<style scoped>
.cards-grid {
    display: flex;
    flex-wrap: wrap;
    justify-content: center;
    gap: 20px;
    padding: 20px;
}
.task-card {
    width: 25%;
    min-width: 280px;
}
.logout-wrapper {
    display: flex;
    justify-content: center;
    width: 100%;
    margin-top: 2rem;
}
.logout-btn-60 {
    width: 60% !important;
}
.custom-view-btn {
    background: #3B82F6;
    color: white;
    text-align: center;
    padding: 10px;
    border-radius: 5px;
    cursor: pointer;
}
</style>