<template>
    <div class="pack-container">
        <div class="pack-header">
            <h1>{{ store.role.name }}</h1>
            <Button 
                icon="fa fa-refresh" 
                class="p-button-rounded p-button-text p-button-info" 
                @click="loadPackTasks" 
                :loading="loading"
                v-tooltip.bottom="'Actualizar tareas'"
            />
        </div>
        
        <div class="tasks-wrapper" v-if="rawPackData.length > 0 && !loading">
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
                        </div>
                        <div class="task-origin">
                            {{ task.carrier ? task.carrier : "Sin carrier" }}
                        </div>
                        <div class="task-footer">
                            <span>{{ store.role.user }}</span>
                            <span class="task-date">{{ store.formatDate(task.date) }}</span>
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
import Button from 'primevue/button';
import LogoutComponent from "../RolePicker/LogoutComponent.vue"
import { useGeneralStore } from "../../store/index";

export default {
    name: "PickerView",
    components: { LogoutComponent, Tag, Button },

    data() {
        return {
            store: useGeneralStore(),
            rawPackData: [],
            batchColors: {},
            loading: false
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
        await this.loadPackTasks();
    },

    methods: {
        async loadPackTasks() {
            this.loading = true;
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
                } else {
                    this.rawPackData = [];
                }
            } catch (error) {
                this.$toast.add({ 
                    severity: 'error', 
                    summary: 'Error de Carga', 
                    detail: 'No se pudieron recuperar las tareas de empaque. ' + (error.message || 'Error de conexión'), 
                    life: 5000 
                });
            } finally {
                this.loading = false;
            }
        },
        async openTask(pickName) {
            if (!pickName) return;
            const url = await this.store.callOdoo("get_barcode_url", "", { pick_name: pickName });
            if (url) {
                window.location.href = url;
            }
        },
        getBatchColor(batchId) {
            if (batchId === 'sin-batch') return 'transparent';
            if (!this.batchColors[batchId]) {
                const hue = Math.floor(Math.random() * 360);
                this.batchColors[batchId] = `hsl(${hue}, 70%, 92%)`;
            }
            return this.batchColors[batchId];
        }
    }
};
</script>

<style scoped>
.pack-container {
    padding: 1rem;
    width: 100%;
    height: calc(100vh - var(--o-we-toolbar-height, 46px));
    display: flex;
    flex-direction: column;
    background: #fff;
    overflow-y: auto;
}

.pack-header {
    display: flex;
    height: 3rem;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1rem;
    border-bottom: 2px solid #f8f9fa;
    padding-bottom: 0.5rem;

}

.tasks-wrapper {
    flex: 1;
    height: calc(100% - 3rem);
    overflow-y: scroll;
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