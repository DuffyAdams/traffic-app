<script>
    import { onMount, onDestroy } from "svelte";
    import { formatTimestamp } from "../utils/helpers.js";

    export let timestamp;

    let relativeTime = "";
    let interval;
    let staticTime = "";

    function updateTime() {
        if (!timestamp) {
            relativeTime = "Recent";
            staticTime = "Recent";
            return;
        }

        staticTime = formatTimestamp(timestamp);

        const date = new Date(timestamp);
        const now = new Date();
        const diffMs = now.getTime() - date.getTime();
        const diffSeconds = Math.floor(diffMs / 1000);

        if (diffSeconds < 0) {
            relativeTime = "Just now";
        } else if (diffSeconds < 60) {
            relativeTime = `${diffSeconds}s ago`;
        } else if (diffSeconds < 3600) {
            const minutes = Math.floor(diffSeconds / 60);
            relativeTime = `${minutes}m ago`;
        } else if (diffSeconds < 86400) {
            const hours = Math.floor(diffSeconds / 3600);
            relativeTime = `${hours}h ago`;
        } else {
            const days = Math.floor(diffSeconds / 86400);
            relativeTime = `${days}d ago`;
        }
    }

    onMount(() => {
        updateTime();
        interval = setInterval(updateTime, 1000);
    });

    onDestroy(() => {
        if (interval) clearInterval(interval);
    });

    $: {
        timestamp;
        updateTime();
        if (interval) {
            clearInterval(interval);
            interval = setInterval(updateTime, 1000);
        }
    }
</script>

<span class="timestamp-container">
    <span class="main-time">{staticTime}</span>
    <span class="custom-tooltip">{relativeTime}</span>
</span>

<style>
    .timestamp-container {
        position: relative;
        display: inline-flex;
        cursor: help;
        align-items: center;
    }

    .custom-tooltip {
        position: absolute;
        bottom: 100%;
        left: 50%;
        transform: translateX(-50%) translateY(-6px);
        background: var(--bg-surface-elevated, #1e293b);
        color: var(--accent-primary, #3b82f6);
        padding: 0.35rem 0.6rem;
        border-radius: 6px;
        font-family: var(--font-mono, monospace);
        font-size: 0.75rem;
        font-weight: 700;
        white-space: nowrap;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        opacity: 0;
        visibility: hidden;
        transition: all 0.2s cubic-bezier(0.175, 0.885, 0.32, 1.275);
        border: 1px solid var(--accent-primary, #3b82f6);
        box-shadow:
            0 4px 12px rgba(0, 0, 0, 0.5),
            0 0 8px
                color-mix(
                    in srgb,
                    var(--accent-primary, #3b82f6) 40%,
                    transparent
                );
        z-index: 100;
        pointer-events: none;
    }

    .custom-tooltip::after {
        content: "";
        position: absolute;
        top: 98%;
        left: 50%;
        transform: translateX(-50%);
        border-width: 5px;
        border-style: solid;
        border-color: var(--accent-primary, #3b82f6) transparent transparent
            transparent;
    }

    .timestamp-container:hover .custom-tooltip {
        opacity: 1;
        visibility: visible;
        transform: translateX(-50%) translateY(-2px);
    }
</style>
