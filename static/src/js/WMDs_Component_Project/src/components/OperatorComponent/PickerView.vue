<template>
    <div class="pack-container">
        <h1>{{ store.role.name }}</h1>
        
        <div class="task-list">
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
        </div>

        <div v-if="packTasks.length === 0" class="empty-state">
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
    name: "PickerView",
    components: { LogoutComponent, Tag },

    data() {
        return {
            store: useGeneralStore(),
            rawPackData: [] 
        };
    },

    computed: {
        packTasks() {
            return this.rawPackData;
        }
    },

    async mounted() {
        try {
            const data = await this.store.callOdoo(
                "pending_tasks",
                "pack",
                { email: this.store.role.email }
            );

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
.pack-container {
    padding: 1rem;
    width: 100%;
}

/* Contenedor principal de las cards */
.task-list {
    display: flex;       /* Activa Flexbox */
    flex-wrap: wrap;    /* Permite que salten de línea */
    gap: 1rem;          /* Espacio entre cards sin usar márgenes manuales */
    justify-content: flex-start; /* Alinea al inicio */
}

.task-item {
    border: 1px solid #dee2e6;
    border-radius: 6px;
    padding: 1rem;
    cursor: pointer;
    background: white;
    
    /* Manejo del ancho:
       Intentará ocupar el 25% menos el espacio del gap, 
       pero no bajará de 280px para que no se vea mal en móviles */
    flex: 1 1 calc(25% - 1rem); 
    min-width: 280px; 
    max-width: 100%; /* Evita que se desborde en pantallas muy pequeñas */
    
    box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    transition: transform 0.2s;
}

.task-item:hover {
    transform: translateY(-2px);
    border-color: #3B82F6; /* Un color de énfasis al pasar el mouse */
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
    margin-top: 2rem;
    padding-bottom: 2rem;
}

.logout-button {
    width: 60% !important; 
}

.empty-state {
    text-align: center;
    padding: 3rem;
    color: #6c757d;
}
</style>