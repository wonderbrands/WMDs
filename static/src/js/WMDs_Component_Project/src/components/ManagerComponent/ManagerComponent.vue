<template>
    <ModalContextComponent v-if="store.modal_open"/>
    <div class="manager_screen">
        <SidebarManagerComponent v-if="show_sidebar"/>
        <main class="main_manager_screen_container">
            <MainManagerScreen v-if="store.main_manager_screen"/>
        </main>
    </div>
</template>
<script>
    import Button from 'primevue/button';
    import BackButton from '../BackButton/BackButton.vue';
    import ModalContextComponent from '../ModalContextComponent/ModalContextComponent.vue';
    import SidebarManagerComponent from './SidebarManagerComponent.vue';
    import MainManagerScreen from './MainManagerScreen.vue';
    import { useGeneralStore } from "../../store/index"
    export default {
        name: "ManagerComponent", 
        data: function() {
            return {
                store: useGeneralStore(),
                show_sidebar: true
            }
        },
        mounted (){
            if(this.store.role.role != "manager") {
                this.store.setCurrentScreen("role_picker")
            } else{
                this.store.setMainManagerScreen('home')
                this.store.currentScreenLoaded()
            }
        },
        components: {
            Button,
            BackButton,
            ModalContextComponent,
            SidebarManagerComponent, 
            MainManagerScreen
        }
    }
</script>

<style scoped>
.manager_screen {
    height: 100vh;
    width: 100vw;
    display: flex;
    flex-direction: row;
    position: relative;
}

.manager_screen button {
    margin: 10px;
    width: 40vw;
}

.main_manager_screen_container {
    width: 75vw;
    height: 100vh;
    display: flex;
    flex-direction: column-reverse;
    align-items: center;
}
</style>