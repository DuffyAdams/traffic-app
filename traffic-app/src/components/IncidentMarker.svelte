<script>
    import { onMount } from "svelte";
    import { fade, scale } from "svelte/transition";

    export let incident;

    let isHovered = false;
    let markerEl;

    function onEnter() {
        isHovered = true;
        // Walk up to the MapLibre marker wrapper and raise it above all others
        const mlMarker = markerEl?.closest(".maplibregl-marker");
        if (mlMarker) mlMarker.style.zIndex = "9999";
    }

    function onLeave() {
        isHovered = false;
        const mlMarker = markerEl?.closest(".maplibregl-marker");
        if (mlMarker) mlMarker.style.zIndex = "";
    }

    // Color based on active status
    $: dotColor = incident.active
        ? incident.type && incident.type.toLowerCase().includes("fire")
            ? "#ff4444"
            : "#ff3333"
        : "#666666";
</script>

<!-- svelte-ignore a11y-no-static-element-interactions -->
<!-- svelte-ignore a11y-mouse-events-have-key-events -->
<div
    class="marker-container"
    bind:this={markerEl}
    on:mouseenter={onEnter}
    on:mouseleave={onLeave}
>
    <!-- Pulsating Dot -->
    {#if incident.active}
        <div class="pulse-ring"></div>
    {/if}
    <div
        class="dot"
        class:inactive={!incident.active}
        style="background-color: {dotColor};"
    ></div>

    <!-- Hover Preview Card -->
    {#if isHovered}
        <div
            class="hover-card"
            transition:scale={{ duration: 150, start: 0.95 }}
        >
            <div class="card-header">
                <span class="type">{incident.type || "Incident"}</span>
                <span class="time">{incident.time}</span>
            </div>

            <div class="card-body">
                <div class="location">
                    <span class="label">LOC</span>
                    <span class="value text-truncate">{incident.location}</span>
                </div>
                {#if incident.neighborhood && incident.neighborhood !== "N/A" && incident.neighborhood !== ""}
                    <div class="neighborhood">
                        <span class="label">AREA</span>
                        <span class="value">{incident.neighborhood}</span>
                    </div>
                {/if}
                {#if incident.description && incident.description !== "No description available"}
                    <div class="description">
                        <span class="label">INFO</span>
                        <span class="value desc-text"
                            >{incident.description}</span
                        >
                    </div>
                {/if}
                {#if incident.details && incident.details.length > 0}
                    <div class="details">
                        {#each incident.details as detail}
                            <div class="detail-line">{detail}</div>
                        {/each}
                    </div>
                {/if}
            </div>
            <div class="arrow-down"></div>
        </div>
    {/if}
</div>

<style>
    .marker-container {
        position: relative;
        cursor: pointer;
        /* Center the dot on the coordinates */
        width: 14px;
        height: 14px;
        transform: translate(-50%, -50%);
        z-index: 10;
        display: flex;
        align-items: center;
        justify-content: center;
    }

    .marker-container:hover {
        z-index: 1000;
    }

    .marker-container:hover .pulse-ring {
        display: none;
    }

    .marker-container:hover .dot {
        box-shadow: 0 0 12px rgba(255, 51, 51, 1);
    }

    .dot {
        width: 10px;
        height: 10px;
        background-color: #ff3333;
        border-radius: 50%;
        position: relative;
        z-index: 2;
        box-shadow: 0 0 8px rgba(255, 51, 51, 0.8);
        border: 1px solid rgba(255, 255, 255, 0.5);
    }

    .dot.inactive {
        width: 8px;
        height: 8px;
        box-shadow: none;
        border: 1px solid rgba(255, 255, 255, 0.2);
        opacity: 0.6;
    }

    .marker-container:hover .dot.inactive {
        opacity: 1;
        box-shadow: 0 0 6px rgba(150, 150, 150, 0.5);
    }

    .pulse-ring {
        position: absolute;
        width: 24px;
        height: 24px;
        background-color: rgba(255, 51, 51, 0.4);
        border-radius: 50%;
        z-index: 1;
        animation: pulse 2s infinite cubic-bezier(0.4, 0, 0.2, 1);
        pointer-events: none;
    }

    @keyframes pulse {
        0% {
            transform: scale(0.5);
            opacity: 1;
        }
        100% {
            transform: scale(2.5);
            opacity: 0;
        }
    }

    /* Hover Card */
    .hover-card {
        position: absolute;
        bottom: 24px; /* Position above the dot */
        left: 50%;
        transform-origin: bottom center;
        transform: translateX(-50%);
        width: 280px;
        max-height: 300px;
        overflow-y: auto;
        background: rgba(8, 12, 18, 0.95);
        border: 1px solid rgba(136, 170, 255, 0.3);
        border-radius: 4px;
        padding: 10px;
        box-shadow:
            0 4px 12px rgba(0, 0, 0, 0.5),
            0 0 0 1px rgba(136, 170, 255, 0.1);
        backdrop-filter: blur(4px);
        pointer-events: none; /* Let mouse remain on dot */
        color: #e0e0e0;
        font-family: "Share Tech Mono", monospace, ui-monospace, SFMono-Regular;
        z-index: 9999;
    }

    .arrow-down {
        position: absolute;
        bottom: -6px;
        left: 50%;
        transform: translateX(-50%);
        width: 0;
        height: 0;
        border-left: 6px solid transparent;
        border-right: 6px solid transparent;
        border-top: 6px solid rgba(8, 12, 18, 0.95);
        filter: drop-shadow(0 1px 0 rgba(136, 170, 255, 0.3));
    }

    .card-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        border-bottom: 1px solid rgba(136, 170, 255, 0.2);
        padding-bottom: 6px;
        margin-bottom: 6px;
        font-size: 0.75rem;
    }

    .type {
        color: #ff5555;
        font-weight: bold;
        text-transform: uppercase;
        max-width: 140px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }

    .time {
        color: #88bbaa;
        font-size: 0.7rem;
    }

    .card-body {
        display: flex;
        flex-direction: column;
        gap: 4px;
        font-size: 0.75rem;
    }

    .location {
        display: flex;
        gap: 6px;
    }

    .neighborhood {
        display: flex;
        gap: 6px;
    }

    .label {
        color: #557799;
        font-weight: bold;
        min-width: 32px;
    }

    .value {
        color: #cccccc;
    }

    .text-truncate {
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        flex: 1;
    }

    .description {
        display: flex;
        gap: 6px;
        margin-top: 4px;
        padding-top: 4px;
        border-top: 1px solid rgba(136, 170, 255, 0.15);
    }

    .desc-text {
        white-space: normal;
        word-wrap: break-word;
        line-height: 1.3;
        color: #aabbcc;
        flex: 1;
    }

    .details {
        margin-top: 4px;
        padding-top: 4px;
        border-top: 1px solid rgba(136, 170, 255, 0.1);
        font-size: 0.7rem;
    }

    .detail-line {
        color: #8899aa;
        padding: 1px 0;
        white-space: normal;
        word-wrap: break-word;
    }
</style>
