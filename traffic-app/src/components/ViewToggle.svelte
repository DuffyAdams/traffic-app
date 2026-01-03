<script>
    import { fade } from "svelte/transition";

    export let condensedView = false;
    export let swipeIndicator = false;
    export let swipeDirection = "";
    export let isPulling = false;
    export let pullDistance = 0;
    export let refreshing = false;

    import { createEventDispatcher } from "svelte";
    const dispatch = createEventDispatcher();

    function toggleView() {
        dispatch("toggle");
    }
</script>

<!-- Swipe indicator -->
{#if swipeIndicator}
    <div class="swipe-indicator {swipeDirection}" in:fade={{ duration: 100 }}>
        <span class="swipe-arrow"
            >{swipeDirection === "left" ? "👈" : "👉"}</span
        >
        <span class="swipe-text"
            >{swipeDirection === "left" ? "Table View" : "Card View"}</span
        >
    </div>
{/if}

<!-- Pull-to-refresh indicator -->
{#if isPulling || refreshing}
    <div
        class="pull-refresh-indicator {refreshing ? 'refreshing' : ''}"
        style="transform: translateX(-50%) translateY({isPulling
            ? pullDistance
            : 0}px)"
    >
        {#if refreshing}
            <span>🔄 Refreshing...</span>
        {:else}
            <span>⬇️ Pull to refresh</span>
        {/if}
    </div>
{/if}

<!-- Side toggle button -->
<button
    class="side-toggle"
    class:condensed={condensedView}
    on:click={toggleView}
    aria-label={condensedView
        ? "Expand to card view"
        : "Condense to table view"}
>
    <span class="side-toggle-arrow">{condensedView ? "→" : "←"}</span>
    <span class="side-toggle-text">{condensedView ? "Cards" : "Table"}</span>
</button>

<style>
    .swipe-indicator {
        position: fixed;
        top: 50%;
        transform: translateY(-50%);
        background-color: rgba(0, 0, 0, 0.7);
        color: white;
        padding: 1rem;
        border-radius: 8px;
        display: flex;
        flex-direction: column;
        align-items: center;
        z-index: 100;
        pointer-events: none;
        backdrop-filter: blur(4px);
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
        width: 100px;
        text-align: center;
    }

    .swipe-indicator.left {
        right: 20px;
        animation: slideInRight 0.3s forwards;
    }

    .swipe-indicator.right {
        left: 20px;
        animation: slideInLeft 0.3s forwards;
    }

    .swipe-arrow {
        font-size: 1.8rem;
        margin-bottom: 0.5rem;
    }

    .swipe-text {
        font-size: 0.9rem;
        font-weight: 600;
    }

    .pull-refresh-indicator {
        position: fixed;
        top: 0;
        left: 50%;
        background-color: #1e3a5f;
        color: white;
        padding: 0.75rem 1.5rem;
        border-radius: 0 0 12px 12px;
        font-weight: 600;
        font-size: 0.9rem;
        z-index: 100;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
        transition: transform 0.1s ease-out;
    }

    .pull-refresh-indicator.refreshing {
        animation: pulse 1s infinite;
    }

    .side-toggle {
        position: fixed;
        right: 0;
        top: 50%;
        transform: translateY(-50%);
        background: linear-gradient(135deg, #1e3a5f 0%, #0d2137 100%);
        color: white;
        border: none;
        border-radius: 8px 0 0 8px;
        padding: 0.8rem 0.5rem;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: 0.5rem;
        cursor: pointer;
        z-index: 100;
        box-shadow: -2px 0 15px rgba(0, 0, 0, 0.2);
        transition: all 0.3s ease;
    }

    .side-toggle:hover {
        background: linear-gradient(135deg, #2a4a6f 0%, #1a3050 100%);
        transform: translateY(-50%) translateX(-5px);
    }

    .side-toggle-arrow {
        font-size: 1.5rem;
        font-weight: bold;
        line-height: 1;
    }

    .side-toggle-text {
        font-size: 0.8rem;
        writing-mode: vertical-rl;
        transform: rotate(180deg);
        text-transform: uppercase;
        letter-spacing: 1px;
    }

    @keyframes slideInRight {
        from {
            opacity: 0;
            transform: translate(20px, -50%);
        }
        to {
            opacity: 1;
            transform: translate(0, -50%);
        }
    }

    @keyframes slideInLeft {
        from {
            opacity: 0;
            transform: translate(-20px, -50%);
        }
        to {
            opacity: 1;
            transform: translate(0, -50%);
        }
    }

    @keyframes pulse {
        0%,
        100% {
            opacity: 1;
        }
        50% {
            opacity: 0.7;
        }
    }

    @media (max-width: 768px) {
        .side-toggle {
            display: none;
        }
    }
</style>
