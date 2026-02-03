<template>
    <div class="sidebar_manager">
        <Button class="toggle_sidebar"/>
        <div style="margin-top: 7em; width: 100%; height: 100%;">
            <div class="options" v-for="option in Object.keys(store.available_main_manager_screens)" :key="option">
                <Button v-if="!with_submenu.includes(option)" 
                @click="selectScreen(option)"
                :disabled="selected==option"
                :raised="selected==option"
                :severity="selected==option ? 'warn' : undefined"
                :style="selected==option ? 'text:black': undefined"
                >
                    {{ store.available_main_manager_screens[option].title }}
                </Button>
                <Button v-else @click="deploySubMenu(option)">
                    {{ store.available_main_manager_screens[option].title }}
                </Button>
                <template v-if="deployed_submenus.includes(option)">
                    <Button v-for="child in store.available_main_manager_screens[option].children" 
                    @click="selectScreen(child.screen)"
                    :disabled="selected==child.screen"
                    :raised="selected==child.screen"
                    :severity="selected==child.screen ? 'warn' : undefined"
                    :style="selected==child.screen ? 'text:black': undefined"
                    >
                        {{ child.title }}
                    </Button>
                </template>
                <!--
                <Button @click="store.setMainManagerScreen('home')">Inicio</Button>
                <Button @click="store.setMainManagerScreen('ingreso')">Recibos</Button>
                <Button @click="store.setMainManagerScreen('disponibilizar')">Disponibilizar</Button>
                <Button @click="store.setMainManagerScreen('traslado')">Traslado</Button>
                <Button @click="store.setMainManagerScreen('pick')">Pick</Button>

                <Button @click="store.setMainManagerScreen('devolucion')">Devoluciones</Button>
                <Button @click="store.setMainManagerScreen('resurtido')">Resurtido</Button>
                <Button @click="store.setMainManagerScreen('conteos')">Conteos</Button>-->
            </div>

            <LogoutComponent />
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