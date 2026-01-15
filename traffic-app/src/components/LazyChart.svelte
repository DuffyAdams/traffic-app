<script>
    import { onMount } from "svelte";
    import { Chart as ChartJS, CategoryScale, TimeScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend, Filler, LineController } from "chart.js";
    import "chartjs-adapter-date-fns";

    export let data;
    export let options;

    let chart;
    let canvas;

    onMount(() => {
        if (canvas) {
            chart = new ChartJS(canvas, {
                type: 'line',
                data,
                options
            });
        }

        return () => {
            if (chart) {
                chart.destroy();
            }
        };
    });

    $: if (chart && data) {
        chart.data = data;
        chart.update();
    }
</script>

<div class="chart-container">
    <canvas bind:this={canvas}></canvas>
</div>

<style>
    .chart-container {
        position: relative;
        width: 100%;
        height: 100%;
    }

    canvas {
        width: 100% !important;
        height: 100% !important;
    }
</style>