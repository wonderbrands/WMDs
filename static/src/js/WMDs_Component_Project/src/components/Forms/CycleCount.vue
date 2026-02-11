<template>
    
</template>

<script>
    import { useGeneralStore } from "../../store/index"

    export default {
        name: "CycleCount", 
        data: function() {
            return {
                store: useGeneralStore(),
                
            }
        }
    }
</script>