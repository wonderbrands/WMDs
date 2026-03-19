<template>
    <div class="role_picker">
        <template v-if="store.role.role === 'manager'">
            <h1>¡Hola, {{ store.role.user }}!</h1>
            <h3>Elige el rol con el que usarás esta sesión</h3>
            <Button label="Manager" @click="store.setCurrentScreen('manager_screen')"/>
            <Button label="Operador" @click="store.setCurrentScreen('operator_screen')" />
        </template>
    </div>
</template>

<script>
    import Button from 'primevue/button';
    import {useGeneralStore} from "../../store/index"
    export default {
        name: 'RolePicker',
        data: function() {
            return {
                store: useGeneralStore()
            }
        },
        mounted: async function() {
            this.store.loading = true;
            try {
                await this.store.role.getRole();
                await this.store.role.getPermissions();
                if (this.store.role.role !== "manager") {
                    this.store.setCurrentScreen("operator_screen");
                }
            } catch (e) {
                this.$toast.add({ severity: 'error', summary: 'Error de Permisos', detail: e.message, life: 3000 });
            } finally {
                this.store.loading = false;
            }
        },
        components: {
            Button
        }
    }
</script>

