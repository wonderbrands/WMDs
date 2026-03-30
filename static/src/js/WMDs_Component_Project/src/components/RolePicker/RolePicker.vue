<template>
    <div v-if="store.role.role === 'manager'" class="role_picker">
        <h1>¡Hola, {{ store.role.user }}!</h1>
        <h3>Elige el rol con el que usarás esta sesión</h3>
        <Button label="Manager" @click="store.setCurrentScreen('manager_screen')"/>
        <Button label="Operador" @click="store.setCurrentScreen('operator_screen')" />
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
                this.store.current_role = this.store.role.role;
                if (this.store.current_role !== "manager") {
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

<style scoped>
.role_picker {
    height: 100vh;
    width: 100vw;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
}

.role_picker button {
    margin: 10px;
    width: 40vw;
}
</style>