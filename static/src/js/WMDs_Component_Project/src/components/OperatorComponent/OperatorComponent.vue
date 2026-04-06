<template>
    <PackerView v-if="store.role.permissions.includes('WMDs Operator - Packer')" />

    <div 
        class="task-container" 
        v-else 
        @touchstart="handleTouchStart"
        @touchmove="handleTouchMove"
        @touchend="handleTouchEnd"
        ref="scrollContainer"
    >
        <div v-if="pulling" class="pull-to-refresh-indicator" :style="{ height: pullDistance + 'px', opacity: pullDistance / 100 }">
            <i class="fa fa-refresh" :class="{ 'fa-spin': refreshing }"></i>
            <span>{{ refreshing ? 'Actualizando...' : 'Tire para actualizar' }}</span>
        </div>
        <h3 class="welcome-header">Bienvenido {{ store.role.user }}</h3>
        
        <div class="cards-grid">
            <Card v-for="task in filteredTasks" :key="task.id" class="task-card" @click="toggleTree(task.id)">
                <template #title  @click="toggleTree(task.id)">{{ task.title }}</template> 
                <template #subtitle  @click="toggleTree(task.id)">{{ task.description }}</template>

                <template #content v-if="task.assigned.length > 0 && !task.view"  @click="toggleTree(task.id)">
                    <span class="pending-badge">
                        {{ task.assigned[0].children.length }} pendientes
                    </span>
                </template>
                <template #content v-else-if="task.assigned.length === 0 && !task.view"  @click="toggleTree(task.id)">
                    <span class="pending-badge">Sin pendientes</span>
                </template>

                <template #footer  @click="toggleTree(task.id)">
                    <Tree
                        v-if="hasChildren(task)"
                        :value="task.assigned"
                        selectionMode="single"
                        v-model:selectionKeys="current_task[task.id]"
                        v-model:expandedKeys="expandedKeys"
                        @node-select="(node) => openTask(node.pick, task.id, node.key)"
                        @click.stop
                        class="full-width"
                    />
                    <div v-else-if="task.view" class="custom-view-btn" @click.stop="createView(task)"  @click="toggleTree(task.id)">
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
import PackerView from "./PackerView.vue";
import CycleCountOperator from "./CycleCountOperator.vue";
import LogoutComponent from "../RolePicker/LogoutComponent.vue";
import { useGeneralStore } from "../../store/index";

export default {
    name: "OperatorComponent",
    components: { Card, Tree, LogoutComponent, PackerView, CycleCountOperator },

    data() {
        return {
            store: useGeneralStore(),
            current_task: {},
            expandedKeys: {},
            taskDefinitions: [
                { id: "ingresos", title: "Recepciones", description: "Validación de ingresos.", fetch: true, label: "Abiertas", permission: "WMDs Operator - Reception" },
                { id: "acomodo", title: "Rackeo", description: "Acomodo de productos.", fetch: true, label: "Abiertos", permission: "WMDs Operator - Forklift operator" },
                { id: "traslados", title: "Traslados", description: "Traslado interno.", fetch: false, label: "Asignados", permission: "WMDs Operator - Forklift operator" },
                { id: "batch_pick", title: "Plan de pickeo", description: "Preparación empaque.", fetch: true, label: "Asignados", permission: "WMDs Operator - Picker" },
                { id: "bin", title:"BIN", description:"Ingresar a BIN", fetch: false, label: "Registrar", view: "BinComponent", permission: "WMDs Operator - BIN" },
                { id: "dock", title:"DOCK", description:"Trasladar a DOCK", fetch: false, label: "Registrar", view: "DockComponent", permission: "WMDs Operator - DOCK" },
                { id: "dispatch", title:"Despacho", description:"Entrega paquetera", fetch: false, label: "Registrar", view: "DispatchComponent", permission: "WMDs Operator - Dispatch" },
                { id: "dispatch_ful", title:"Despacho fulfilment", description:"Entrega a paquetería de ordenes ful", fetch: false, label: "Registrar", view: "DispatchComponentFul", permission: "WMDs Operator - Dispatch" },
                { id: "cycle_count_assigned", title: "Conteo cíclico", description: "Conteo de inventario por ubicación", fetch: true, label: "Asignados", permission: "WMDs Operator - Stock Counter" },
                { id: "reabastecimiento", title: "Reabastecimiento", description: "Traslado de stock de niveles superiores a niveles inferiores para disponibilizar", fetch: true, label: "Abiertos", permission: "WMDs Operator - Replenishment" },
            ],
            tasks: [],
            // Pull to refresh state
            startY: 0,
            pullDistance: 0,
            pulling: false,
            refreshing: false,
            maxPullDistance: 100
        };
    },

    computed: {
        filteredTasks() {
            const perms = this.store.role.permissions || [];
            if (perms.includes('WMDs Manager')) return this.tasks;
            return this.tasks.filter(t => perms.includes(t.permission));
        }
    },

    async mounted() {
        await this.loadTasks();
    },

    methods: {
        async loadTasks() {
            const clientTimeZone = Intl.DateTimeFormat().resolvedOptions().timeZone;

            this.tasks = this.taskDefinitions.map(t => ({
                ...t,
                assigned: [{ key: `${t.id}-root`, label: t.label, selectable: false, children: [] }]
            }));

            const fetchPromises = this.filteredTasks
                .filter(t => t.fetch)
                .map(async (task) => {
                    let data = null;
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

                    if (Array.isArray(data)) {
                        task.assigned[0].children = data.map((p, i) => ({
                                key: p.key || `${task.id}-${i}`,
                                label: p.label || p,
                                data: p.data || p,
                                pick: p.pick || p,
                                leaf: true
                        }));
                    } else {
                        task.assigned[0].children = [];
                    }
                    
                });
            await Promise.all(fetchPromises);
        },
        handleTouchStart(e) {
            if (this.$refs.scrollContainer.scrollTop === 0) {
                this.startY = e.touches[0].pageY;
                this.pulling = true;
            }
        },
        handleTouchMove(e) {
            if (!this.pulling || this.refreshing) return;
            const currentY = e.touches[0].pageY;
            const diff = currentY - this.startY;
            if (diff > 0) {
                this.pullDistance = Math.min(diff, this.maxPullDistance);
                if (diff > 10) e.preventDefault(); // Prevent native scroll
            }
        },
        async handleTouchEnd() {
            if (!this.pulling) return;
            if (this.pullDistance >= 60) {
                this.refreshing = true;
                await this.loadTasks();
                this.refreshing = false;
            }
            this.pulling = false;
            this.pullDistance = 0;
        },
        toggleTree(taskId) {
            const rootKey = `${taskId}-root`;
            if (this.expandedKeys[rootKey]) {
                delete this.expandedKeys[rootKey];
            } else {
                this.expandedKeys[rootKey] = true;
            }
        },
        hasChildren(task) {
            return task.assigned?.[0]?.children?.length > 0;
        },
        async openTask(pick, task_id, record_id=null) {
            if (task_id==="cycle_count_assigned"){
                switch (task_id) {
                    case "cycle_count_assigned":
                    this.store.mandatory_uncompleted.component_props = {cc_id:record_id}
                    this.store.mandatory_uncompleted.component = CycleCountOperator;
                        break;
                
                    default:
                        break;
                }
            } else{
                const url = await this.store.callOdoo("get_barcode_url", "", { pick_name: pick });
                window.location.href = url;
            }
           
        },
        createView(task){
            this.store.mandatory_uncompleted.component = task.view;
        }
    }
};
</script>

<style scoped>
.task-container {
    overflow-y: scroll; 
    padding: 1em; 
    width: 100%; 
    height: 90vh; 
    margin-bottom: 3em;
    display: flex; 
    flex-direction: column;
    position: relative;
    overscroll-behavior-y: contain;
}

.pull-to-refresh-indicator {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    overflow: hidden;
    background: rgba(59, 130, 246, 0.1);
    color: #3B82F6;
    z-index: 10;
    transition: height 0.1s ease;
    font-size: 0.8rem;
    font-weight: bold;
    gap: 5px;
}

.pull-to-refresh-indicator i {
    font-size: 1.2rem;
}

.welcome-header { 
    margin: 1em; 
}

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
    cursor: pointer;
    transition: box-shadow 0.2s;
    margin: 1em;
}

.task-card:hover {
    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
}

.pending-badge { 
    font-style: italic; 
    color: red; 
}

.empty-tasks { 
    padding: 1em; 
    color: #666; 
    font-style: italic; 
}

.full-width { 
    width: 100%; 
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