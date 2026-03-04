<template>
    <div class="pack-container">
        <div 
            v-for="task in packTasks" 
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
            <div class="task-footer">
                <span>{{ store.role.user }}</span>
                <span class="task-date">{{ task.date }}</span>
            </div>
        </div>

        <div v-if="packTasks.length === 0" class="empty-state">
            No hay tareas de empaque asignadas.
        </div>
        
        <LogoutComponent style="width: 100%; margin-top: 1rem;"/>
    </div>
</template>

<script>
import Tag from 'primevue/tag';
import LogoutComponent from "../RolePicker/LogoutComponent.vue"
import { useGeneralStore } from "../../store/index";

export default {
    name: "PickerView",
    components: { LogoutComponent, Tag },

    data() {
        return {
            store: useGeneralStore(),
            // Simplificamos: no necesitamos taskDefinitions complejas si este componente es solo para PACK
            rawPackData: [] 
        };
    },

    computed: {
        // Esta propiedad computada evita el error de "undefined"
        packTasks() {
            return this.rawPackData;
        }
    },

    async mounted() {
        try {
            // Llamada directa a Odoo para el ID "pack"
            const data = await this.store.callOdoo(
                "pending_tasks",
                "pack",
                { email: this.store.role.email }
            );

            // Mapeamos los datos directamente a nuestro array local
            if (data && Array.isArray(data)) {
                this.rawPackData = data.map((p, i) => ({
                    key: `pack-${i}`,
                    label: p.label || p,
                    data: p.data || p,
                    origin: p.origin || 'Sin origen',
                    pick: p.pick || p,
                    date: p.date || new Date().toLocaleDateString() // Por si p.date no viene
                }));
            }
        } catch (error) {
            this.$toast.add({ 
                severity: 'error', 
                summary: 'Error', 
                detail: 'No se pudieron cargar las tareas de empaque.', 
                life: 3000 
            });
            console.error("Error cargando pack:", error);
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
    }
};
</script>

<style scoped>
.task-item {
    border: 1px solid #dee2e6;
    border-radius: 6px;
    padding: 1rem;
    margin-bottom: 1rem;
    cursor: pointer;
    background: white;
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
}
.task-footer {
    display: flex;
    justify-content: space-between;
    font-size: 0.85rem;
    color: #495057;
}
</style>