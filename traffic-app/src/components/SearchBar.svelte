<script>
    import { createEventDispatcher, onMount } from "svelte";
    import Search from "lucide-svelte/icons/search";
    import X from "lucide-svelte/icons/x";

    export let value = "";
    export let placeholder = "Search incidents...";
    
    const dispatch = createEventDispatcher();
    let inputRef;

    function handleInput(e) {
        value = e.target.value;
        dispatch("input", value);
    }

    function clearSearch() {
        value = "";
        dispatch("input", value);
        if (inputRef) inputRef.focus();
    }
</script>

<div class="search-container">
    <div class="search-icon">
        <Search size={15} />
    </div>
    <input
        bind:this={inputRef}
        type="text"
        class="search-input"
        {placeholder}
        {value}
        on:input={handleInput}
    />
    {#if value.length > 0}
        <button class="clear-button" on:click={clearSearch} aria-label="Clear search">
            <X size={14} />
        </button>
    {/if}
</div>

<style>
    .search-container {
        display: flex;
        align-items: center;
        background: var(--bg-surface-elevated, #111824);
        border: 1px solid var(--border-color, #4a5568);
        border-radius: 6px;
        padding: 0.35rem 0.75rem;
        margin: 0;
        transition: all 0.2s ease;
        box-shadow: inset 0 0 0 1px rgba(51, 102, 255, 0.05);
        position: relative;
    }

    .search-container:focus-within {
        border-color: var(--accent-primary, #3182ce);
        box-shadow: 0 0 0 1px var(--accent-primary, #3182ce), inset 0 0 0 1px rgba(51, 102, 255, 0.1);
        transform: translateY(-1px);
    }

    .search-icon {
        color: var(--text-muted, #a0aec0);
        display: flex;
        align-items: center;
        justify-content: center;
        margin-right: 0.75rem;
    }

    .search-container:focus-within .search-icon {
        color: var(--accent-primary, #3182ce);
    }

    .search-input {
        flex: 1;
        background: transparent;
        border: none;
        color: var(--text-main, #f8fafc);
        font-family: var(--font-mono, monospace);
        font-size: 0.85rem;
        outline: none;
        width: 100%;
    }

    .search-input::placeholder {
        color: var(--text-muted, #a0aec0);
        opacity: 0.6;
    }

    .clear-button {
        background: transparent;
        border: none;
        color: var(--text-muted, #a0aec0);
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 0.25rem;
        border-radius: 4px;
        transition: all 0.2s ease;
        margin-left: 0.5rem;
    }

    .clear-button:hover {
        background: rgba(255, 255, 255, 0.1);
        color: var(--text-main, #f8fafc);
    }

    :global(body:not(.dark-mode)) .search-container {
        background: #ffffff;
        border-color: #cbd5e0;
    }

    :global(body:not(.dark-mode)) .clear-button:hover {
        background: rgba(0, 0, 0, 0.05);
        color: #1a202c;
    }

    :global(body:not(.dark-mode)) .search-input {
        color: #1a202c;
    }
</style>
