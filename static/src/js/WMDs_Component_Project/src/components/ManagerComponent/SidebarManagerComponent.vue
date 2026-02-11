<template>
    <div class="sidebar_manager">
        <Button class="toggle_sidebar" icon="pi pi-bars" />
        <div class="sidebar_content">
            <div style="margin-top: 7em; width: 100%;">
                <div class="options" v-for="option in Object.keys(store.available_main_manager_screens)" :key="option">
                    
                    <Button v-if="!with_submenu.includes(option)" 
                        @click="selectScreen(option)"
                        :class="{'selected_option': selected == option}"
                        :disabled="selected == option"
                    >
                        {{ store.available_main_manager_screens[option].title }}
                    </Button>

                    <Button v-else 
                        @click="deploySubMenu(option)"
                        :class="{'active_submenu': deployed_submenus.includes(option)}"
                    >
                        {{ store.available_main_manager_screens[option].title }}
                    </Button>

                    <template v-if="deployed_submenus.includes(option)">
                        <Button v-for="child in store.available_main_manager_screens[option].children" 
                            :key="child.screen"
                            @click="selectScreen(child.screen)"
                            class="submenu_child"
                            :class="{'selected_option': selected == child.screen}"
                            :disabled="selected == child.screen"
                        >
                            {{ child.title }}
                        </Button>
                    </template>
                </div>
                
                    <LogoutComponent />
                </div><div class="options">
            </div>
        </div>
    </div>
</template>

<script>
    import Button from "primevue/button";
    import Tree from 'primevue/tree';
    import LogoutComponent from "../RolePicker/LogoutComponent.vue"
    import { useGeneralStore } from "../../store/index"

    export default {
        name: "SidebarManagerComponent", 
        data: function() {
            return {
                store: useGeneralStore(),
                with_submenu: ["pick"],
                deployed_submenus: [],
                selected: null
            }
        },
        methods: {
            deploySubMenu(option) {
                if(this.deployed_submenus.includes(option)) {
                    this.deployed_submenus.splice(this.deployed_submenus.indexOf(option), 1);
                    return;
                }
                this.deployed_submenus.push(option);
            },
            selectScreen(screen){
                this.selected = screen
                this.store.setMainManagerScreen(screen)
            }
        },
        components: {
            Button, 
            Tree,
            LogoutComponent
        }
    }
</script>