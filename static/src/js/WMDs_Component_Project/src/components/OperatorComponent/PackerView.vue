<template>
    <div class="pack-container">
        <h1>{{ store.role.name }}</h1>
        
        <div class="tasks-wrapper" v-if="rawPackData.length > 0">
            <div 
                v-for="(group, index) in groupedTasks" 
                :key="index" 
                class="batch-group"
                :style="{ backgroundColor: group.color }"
            >
                <div class="task-list">
                    <div 
                        v-for="task in group.tasks" 
                        :key="task.key"
                        class="task-item"
                        @click="openTask(task.pick)"
                    >
                        <div class="task-header">
                            <span class="pick-name">{{ task.pick }}</span>
                            <Tag severity="success" value="Disponible" />
                        </div>
                        <div class="task-origin">
                            {{ task.origin }}
                            {{ task.carrier ? task.carrier : "Sin carrier" }}
                        </div>
                        <div class="task-footer">
                            <span>{{ store.role.user }}</span>
                            <span class="task-date">{{ task.date }}</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <div v-if="rawPackData.length === 0" class="empty-state">
            No hay tareas de empaque asignadas.
        </div>
        
        <div class="button-logout-container">
            <LogoutComponent class="logout-button" />
        </div>
    </div>
</template>

<script>
import Tag from 'primevue/tag';
import LogoutComponent from "../RolePicker/LogoutComponent.vue"
import { useGeneralStore } from "../../store/index";

export default {
    name: "PackerView",
    components: { LogoutComponent, Tag },

    data() {
        return {
            store: useGeneralStore(),
            rawPackData: [] 
        };
    },

    computed: {
        groupedTasks() {
            const groups = {};
            this.rawPackData.forEach(task => {
                const batchId = task.batch || 'sin-batch';
                if (!groups[batchId]) {
                    groups[batchId] = {
                        tasks: [],
                        color: this.getBatchColor(batchId)
                    };
                }
                groups[batchId].tasks.push(task);
            });
            return Object.values(groups);
        }
    },

    async mounted() {
        try {
            const clientTimeZone = Intl.DateTimeFormat().resolvedOptions().timeZone;

            const data = await this.store.callOdoo(
                "pending_tasks",
                "pack",
                { 
                    email: this.store.role.email,
                    tz: clientTimeZone 
                }
            );

            if (data && Array.isArray(data)) {
                this.rawPackData = data.map((p, i) => ({
                    key: `pack-${i}`,
                    label: p.label || p,
                    data: p.data || p,
                    origin: p.origin || 'Sin origen',
                    pick: p.pick || p,
                    date: p.date || new Date().toLocaleDateString(),
                    carrier: p.carrier,
                    batch: p.batch
                }));
            }
        } catch (error) {
            this.$toast.add({ 
                severity: 'error', 
                summary: 'Error', 
                detail: 'No se pudieron cargar las tareas de empaque.', 
                life: 3000 
            });
        }
    },

    methods: {
        async openTask(pickName) {
            if (!pickName) return;
            const url = await this.store.callOdoo("get_barcode_url", "", { pick_name: pickName });
            if (url) {
                window.location.href = url;
            }
        },
        getBatchColor(batchId) {
            if (batchId === 'sin-batch') return 'transparent';
            let hash = 0;
            const str = String(batchId);
            for (let i = 0; i < str.length; i++) {
                hash = str.charCodeAt(i) + ((hash << 5) - hash);
            }
            const hue = Math.abs(hash) % 360;
            return `hsl(${hue}, 60%, 94%)`;
        }
    }
};
</script>

<style scoped>
.pack-container {
    padding: 1rem;
    width: 100%;
    height: 100vh;
    display: flex;
    flex-direction: column;
}

.tasks-wrapper {
    flex: 1;
    overflow-y: auto;
    padding-right: 0.5rem;
    margin-bottom: 1rem;
}

.batch-group {
    padding: 1.5rem;
    border-radius: 12px;
    margin-bottom: 1.5rem;
}

.task-list {
    display: flex;
    flex-wrap: wrap;
    gap: 1rem;
    justify-content: flex-start;
}

.task-item {
    border: 1px solid #dee2e6;
    border-radius: 6px;
    padding: 1rem;
    cursor: pointer;
    background: white;
    flex: 1 1 calc(25% - 1rem); 
    min-width: 280px; 
    max-width: 25%;
    box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    transition: transform 0.2s;
}

.task-item:hover {
    transform: translateY(-2px);
    border-color: #3B82F6;
}

.task-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-weight: bold;
    margin-bottom: 0.5rem;
}

.task-origin {
    color: #6c757d;
    margin-bottom: 0.5rem;
    font-size: 0.9rem;
}

.task-footer {
    display: flex;
    justify-content: space-between;
    font-size: 0.85rem;
    color: #495057;
    border-top: 1px solid #f8f9fa;
    padding-top: 0.5rem;
}

.button-logout-container {
    display: flex;
    justify-content: center;
    width: 100%;
    padding-bottom: 1rem;
    flex-shrink: 0;
}

.logout-button {
    width: 60% !important; 
}

.empty-state {
    text-align: center;
    padding: 3rem;
    color: #6c757d;
}

::-webkit-scrollbar {
    width: 8px;
}

::-webkit-scrollbar-track {
    background: #f1f1f1;
    border-radius: 4px;
}

::-webkit-scrollbar-thumb {
    background: #c1c1c1;
    border-radius: 4px;
}

::-webkit-scrollbar-thumb:hover {
    background: #a8a8a8;
}
</style>