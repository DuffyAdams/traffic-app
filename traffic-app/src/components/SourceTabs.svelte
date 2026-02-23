<script>
    import { createEventDispatcher } from "svelte";
    const dispatch = createEventDispatcher();

    export let activeSource = "all";

    function setSourceFilter(source) {
        dispatch("changeSource", source);
    }
</script>

<div class="source-tabs">
    <button
        class="source-tab"
        class:active={activeSource === "all"}
        on:click={() => setSourceFilter("all")}>All</button
    >
    <button
        class="source-tab"
        class:active={activeSource === "CHP"}
        on:click={() => setSourceFilter("CHP")}>Traffic</button
    >
    <button
        class="source-tab"
        class:active={activeSource === "SDPD"}
        on:click={() => setSourceFilter("SDPD")}>Police</button
    >
    <button
        class="source-tab"
        class:active={activeSource === "SDFD"}
        on:click={() => setSourceFilter("SDFD")}>Fire</button
    >
</div>

<style>
    .source-tabs {
        display: flex;
        justify-content: center;
        gap: 0.4rem;
        margin-bottom: 0.8rem;
        overflow-x: auto;
        padding: 5px 0 0.4rem 0;
    }

    .source-tab {
        background: var(--bg-surface-elevated);
        border: 1px solid var(--border-color);
        color: var(--text-muted);
        padding: 0.4rem 1.2rem;
        border-radius: 2px;
        font-size: 0.85rem;
        font-family: var(--font-mono);
        text-transform: uppercase;
        cursor: pointer;
        transition: all 0.15s ease;
        white-space: nowrap;
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
</style>
