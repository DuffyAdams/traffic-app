<script>
    import { createEventDispatcher } from "svelte";
    import { t } from "../utils/i18n.js";

    const dispatch = createEventDispatcher();

    export let activeSource = "all";

    const tabs = [
        { value: "all", label: t("filters.all") },
        { value: "CHP", label: t("filters.traffic") },
        { value: "SDPD", label: t("filters.sdpd") },
        { value: "SDSO", label: t("filters.sheriff") },
        { value: "SDFD", label: t("filters.fire") },
        { value: "map", label: `🗺️ ${t("filters.map")}` },
    ];

    function setSourceFilter(source) {
        dispatch("changeSource", source);
    }
</script>

<div class="source-tabs">
    {#each tabs as tab}
        <button
            class="source-tab"
            class:active={activeSource === tab.value}
            type="button"
            aria-pressed={activeSource === tab.value}
            on:click={() => setSourceFilter(tab.value)}
        >
            {tab.label}
        </button>
    {/each}
</div>

<style>
    .source-tabs {
        display: flex;
        justify-content: center;
        gap: 0.4rem;
        padding: 5px 0 0.4rem 0;
        flex-wrap: wrap;
    }

    .source-tab {
        background: var(--bg-surface-elevated);
        border: 1px solid var(--border-color);
        color: var(--text-muted);
        padding: 0.4rem 1.2rem;
        border-radius: 6px;
        font-size: 0.85rem;
        font-family: var(--font-mono);
        text-transform: uppercase;
        cursor: pointer;
        transition: all 0.15s ease;
        white-space: nowrap;
        flex: 1 1 auto;
        text-align: center;
    }

    :global(body.dark-mode) .source-tab {
        background: rgba(0, 0, 0, 0.5);
        border: 1px solid var(--border-color);
    }

    .source-tab:hover {
        border-color: var(--accent-primary);
        background: rgba(51, 102, 255, 0.1);
        color: var(--text-main);
    }

    .source-tab.active {
        background: rgba(51, 102, 255, 0.15);
        color: #fff;
        border-color: var(--accent-primary);
        box-shadow: inset 0 0 0 1px rgba(51, 102, 255, 0.3);
    }

    :global(body.dark-mode) .source-tab.active {
        background: rgba(51, 102, 255, 0.15);
        color: #fff;
        border-color: var(--accent-primary);
    }

    @media (max-width: 480px) {
        .source-tabs {
            gap: 0.25rem;
        }

        .source-tab {
            padding: 0.4rem 0.5rem;
            font-size: 0.75rem;
        }
    }

    @media (min-width: 768px) {
        .source-tab {
            flex: 0 1 auto;
            padding: 0.3rem 1rem;
            font-size: 0.8rem;
        }
    }
</style>
