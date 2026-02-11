<template>
    <div class="blocking_modal">
        <div class="loader"></div>
    </div>
</template>

<script>
export default {
    name: "LoadingComponent",
};
</script>

<style>
.blocking_modal {
    background-color: rgb(9, 0, 10, 0.9);
    width: 100%;
    height: 100%;
    display: flex;
    justify-content: center;
    align-items: center;
    position: fixed;
    z-index: 500;
    left: 0;
    top: 0;
}
.loader {
    width: 60px;
    aspect-ratio: 2;
    --_g: no-repeat radial-gradient(circle closest-side, yellow 90%, #0000);
    background:
        var(--_g) 0% 50%,
        var(--_g) 50% 50%,
        var(--_g) 100% 50%;
    background-size: calc(100% / 3) 50%;
    animation: l3 0.6s infinite linear;
}
@keyframes l3 {
    20% {
        background-position:
            0% 0%,
            50% 50%,
            100% 50%;
    }
    40% {
        background-position:
            0% 100%,
            50% 0%,
            100% 50%;
    }
    60% {
        background-position:
            0% 50%,
            50% 100%,
            100% 0%;
    }
    80% {
        background-position:
            0% 50%,
            50% 50%,
            100% 100%;
    }
}
</style>
