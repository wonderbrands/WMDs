<template>
    <div class="back_button">
        <Button label="←" @click="store.setCurrentScreen(where)" rounded/>
    </div>
</template>
<script>
    import Button from 'primevue/button';
    import { useGeneralStore } from "../../store/index"
    export default {
        name: "BackButton", 
        props: ['where'],
        data: function() {
            return {
                store: useGeneralStore()
            }
        },
        components: {
            Button
        }
    }
</script>