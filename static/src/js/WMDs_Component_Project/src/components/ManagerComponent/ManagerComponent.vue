<template>
    <ModalContextComponent v-if="store.modal_open"/>
    <div class="manager_screen">
        <SidebarManagerComponent v-if="show_sidebar"/>
        <main class="main_manager_screen_container">
            <!--<BackButton where="role_picker" class="back_button"/>-->
            <MainManagerScreen/>
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