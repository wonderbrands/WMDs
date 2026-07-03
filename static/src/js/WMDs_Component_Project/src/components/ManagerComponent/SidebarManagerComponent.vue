<template>
    <div class="sidebar_manager" :class="{'collapsed': store.sidebar_collapsed}">
        <Button class="toggle_sidebar" :icon="store.sidebar_collapsed ? 'fa fa-chevron-right' : 'fa fa-bars'" @click="store.sidebar_collapsed = !store.sidebar_collapsed" />
        <div class="sidebar_content" v-show="!store.sidebar_collapsed">
            <div style="margin-top: 1em; width: 100%; margin-bottom: 5em;">
                <img src="https://mma.prnewswire.com/media/1447948/LogoWonderBrands_Logo.jpg?p=facebook" style="max-width: 100%;">
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

                <div class="logout-wrapper">
                    <LogoutComponent />
                </div>

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

<style scoped>
.sidebar_manager {
    height: calc(100vh - var(--o-we-toolbar-height, 46px));
    width: 25vw;
    min-width: 217px;
    background-color: #F9FAFB;
    position: relative;
    display: flex;
    flex-direction: column;
    overflow: visible !important; 
    z-index: 10;
    transition: all 0.3s ease;
    flex-shrink: 0;
}

.sidebar_manager.collapsed {
    width: 15px !important;
    min-width: 15px !important;
    background-color: #facc15 !important;
    border-right: 1px solid #cbd5e1;
}

.sidebar_content {
    width: 100%;
    height: 100%;
    overflow-y: auto;
    overflow-x: hidden;
    display: flex;
    flex-direction: column;
    align-items: center;
}

.toggle_sidebar {
    z-index: 15;
    width: 40px;
    height: 40px;
    border-radius: 20px;
    position: absolute;
    right: -20px;
    margin: 0px;
    padding: 0px;
    margin-top: 2em;
}

.options {
    width: 100%;
    display: flex;
    flex-direction: column;
    align-items: center;
}

.options button {
    width: 100%;
    background-color: white;
    padding: .7em;
    text-align: left;
    border: none;
    border-bottom: 1px solid #eee;
    transition: all 0.2s ease;
    color: #4b5563;
}

.options .selected_option {
    background-color: #111827 !important;
    color: #facc15 !important;
    font-weight: bold !important;
    border-left: 4px solid #facc15 !important;
    opacity: 1 !important;
}

.options .active_submenu {
    background-color: #f3f4f6;
    font-weight: 600;
}

.options .submenu_child {
    width: 90% !important; 
    margin-left: 1.5em !important;
    font-size: 0.85em;
    border-bottom: 1px solid #f3f4f6;
}

.logout-wrapper {
    width: 100%;
    display: flex;
    justify-content: center;
    margin-top: auto;
    padding-bottom: 2em;
}

/* Specific styling for LogoutComponent when in sidebar if needed, 
   but it's better to keep LogoutComponent's own styles inside it */
:deep(.logout-wrapper button) {
    width: 80% !important;
    height: auto !important;
    border-radius: 8px !important;
    margin: 0px !important;
    background-color: #ef4444 !important;
    color: white !important;
}
</style>