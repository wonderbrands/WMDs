<template>
    <div>
        <div 
        @click="openTask(task)"
        v-for="task in taskDefinitions.filter(definition => definition.id==='pack').assigned[0].children" 
        key="task.key">
            <div>
                {{ task.pick }}
                <Tag severity="success" value="Disponible"></Tag>
            </div>
            <div>
                {{ task.origin }}
            </div>
            <div>
                {{ store.role.user }}
                {{ task.date }}
            </div>
        </div>
    </div>
</template>

<script>
import Card from "primevue/card";
import Tree from "primevue/tree";
import Tag from 'primevue/tag';
import LogoutComponent from "../RolePicker/LogoutComponent.vue"
import { useGeneralStore } from "../../store/index";

export default {
    name: "PickerView",
    components: { Card, Tree, LogoutComponent, Tag },

    data() {
        return {
            store: useGeneralStore(),
            current_task: {},
            taskDefinitions: [
                { id: "pack", title: "Pack", description: "Empaque de productos", fetch: true, label: "Asignados a mi" },
            ],
            tasks: []
        };
    },

    computed: {
        activeTasks() {
            return this.tasks;
        }
    },

    async beforeMount() {
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
                    const data = await this.store.callOdoo(
                        "pending_tasks",
                        task.id,
                        { email: this.store.role.email }
                    );
                    
                    task.assigned[0].children = (data || []).map((p, i) => ({
                        key: `${task.id}-${i}`,
                        label: p.label || p,
                        data: p.data || p,
                        leaf: true,
                        origin: p.origin,
                        pick: p.pick
                    }));
                });

            await Promise.all(fetchPromises);
        } catch (error) {
            this.$toast.add({ severity: 'error', summary: 'Error', detail: 'No se pudieron cargar las tareas pendientes.', life: 3000 });
            console.error("Error cargando tareas:", error);
        }
    },

    methods: {
        async openTask(pick) {
            const urlPromise = this.store.callOdoo("get_barcode_url", "", { pick_name: pick });
            window.location.href = await urlPromise;
        },
    }
};
</script>
