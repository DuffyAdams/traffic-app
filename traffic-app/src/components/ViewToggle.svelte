<script>
    import { fade } from "svelte/transition";
    import ChevronLeft from "lucide-svelte/icons/chevron-left";
    import ChevronRight from "lucide-svelte/icons/chevron-right";
    import LayoutGrid from "lucide-svelte/icons/layout-grid";
    import LayoutList from "lucide-svelte/icons/layout-list";

    export let condensedView = false;
    export let swipeIndicator = false;
    export let swipeDirection = "";

    import { createEventDispatcher } from "svelte";
    const dispatch = createEventDispatcher();

    function toggleView() {
        dispatch("toggle");
    }
</script>

<!-- Swipe indicator -->
{#if swipeIndicator}
    <div class="swipe-indicator {swipeDirection}" in:fade={{ duration: 150 }}>
        <div class="swipe-content">
            <span class="swipe-icon">
                {#if swipeDirection === "left"}
                    <ChevronLeft size={32} />
                {:else}
                    <ChevronRight size={32} />
                {/if}
            </span>
            <span class="swipe-label">
                {swipeDirection === "left" ? "Table View" : "Card View"}
            </span>
            <span class="swipe-icon-secondary">
                {#if swipeDirection === "left"}
                    <LayoutList size={20} />
                {:else}
                    <LayoutGrid size={20} />
                {/if}
            </span>
        </div>
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
        background: var(--bg-surface-elevated);
        border: 1px solid var(--border-color);
        color: var(--text-main);
        padding: 0;
        border-radius: 2px;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        z-index: 100;
        pointer-events: none;
        backdrop-filter: blur(12px);
        box-shadow:
            0 8px 32px rgba(0, 0, 0, 0.3),
            0 0 0 1px rgba(255, 255, 255, 0.1);
        width: 120px;
        height: 100px;
        text-align: center;
        opacity: 0.95;
    }

    .swipe-indicator.left {
        right: 20px;
        animation: slideInRight 0.3s forwards;
    }

    .swipe-indicator.right {
        left: 20px;
        animation: slideInLeft 0.3s forwards;
    }

    .swipe-content {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 0.5rem;
        height: 100%;
        justify-content: center;
    }

    .swipe-icon {
        display: flex;
        align-items: center;
        justify-content: center;
        color: rgba(255, 255, 255, 0.95);
        animation: bounce 0.6s ease-in-out;
    }

    .swipe-label {
        font-size: 0.85rem;
        font-family: var(--font-mono);
        font-weight: normal;
        letter-spacing: 0.5px;
        text-transform: uppercase;
        color: var(--accent-primary);
    }

    .swipe-icon-secondary {
        display: flex;
        align-items: center;
        justify-content: center;
        color: rgba(255, 255, 255, 0.5);
        margin-top: -0.25rem;
    }

    @keyframes bounce {
        0%,
        100% {
            transform: translateX(0);
        }
        50% {
            transform: translateX(-6px);
        }
    }

    .swipe-indicator.right .swipe-icon {
        animation: bounceRight 0.6s ease-in-out;
    }

    @keyframes bounceRight {
        0%,
        100% {
            transform: translateX(0);
        }
        50% {
            transform: translateX(6px);
        }
    }

    .pull-refresh-indicator {
        position: fixed;
        top: 0;
        left: 50%;
        background-color: #1e3a5f;
        color: white;
        padding: 0.75rem 1.5rem;
        border-radius: 0 0 2px 2px;
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
        background: var(--bg-surface-elevated);
        border: 1px solid var(--border-color);
        border-right: none;
        color: var(--accent-primary);
        border-radius: 2px 0 0 2px;
        padding: 0.8rem 0.4rem;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: 0.5rem;
        cursor: pointer;
        z-index: 100;
        transition: all 0.15s ease;
    }

    .side-toggle:hover {
        background: rgba(0, 229, 255, 0.15);
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
            transform: translate(30px, -50%) scale(0.9);
        }
        to {
            opacity: 0.95;
            transform: translate(0, -50%) scale(1);
        }
    }

    @keyframes slideInLeft {
        from {
            opacity: 0;
            transform: translate(-30px, -50%) scale(0.9);
        }
        to {
            opacity: 0.95;
            transform: translate(0, -50%) scale(1);
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

        .swipe-indicator {
            width: 100px;
            height: 85px;
        }

        .swipe-icon :global(svg) {
            width: 28px;
            height: 28px;
        }

        .swipe-label {
            font-size: 0.75rem;
        }

        .swipe-icon-secondary :global(svg) {
            width: 16px;
            height: 16px;
        }
    }
</style>
