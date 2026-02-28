<script>
    import { fly } from "svelte/transition";
    import { toasts, removeToast } from "../stores/appStore.js";
</script>

{#if $toasts.length > 0}
    <div class="toast-container">
        {#each $toasts as toast (toast.id)}
            <div
                class="toast toast-{toast.type}"
                in:fly={{ y: -50, duration: 300 }}
                out:fly={{ y: -50, duration: 200 }}
            >
                <span class="toast-message">{toast.message}</span>
                <button
                    class="toast-close"
                    on:click={() => removeToast(toast.id)}>×</button
                >
            </div>
        {/each}
    </div>
{/if}

<style>
    .toast-container {
        position: fixed;
        top: 20px;
        right: 20px;
        z-index: 1000;
        display: flex;
        flex-direction: column;
        gap: 0.5rem;
        max-width: 400px;
    }

    .toast {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 1rem 1.25rem;
        border-radius: 6px;
        font-size: 0.9rem;
        font-family: var(--font-mono);
        text-transform: uppercase;
        font-weight: bold;
        background: var(--bg-surface-elevated);
        border: 1px solid var(--border-color);
        min-width: 300px;
    }

    .toast-info {
        border-color: var(--accent-primary);
        color: var(--accent-primary);
        box-shadow: inset 0 0 0 1px rgba(51, 102, 255, 0.3);
    }

    :global(body.dark-mode) .toast-info {
        border-color: var(--accent-primary);
        color: var(--accent-primary);
    }

    .toast-success {
        border-color: var(--success-color, #00cc66);
        color: var(--success-color, #00cc66);
        box-shadow: inset 0 0 0 1px rgba(0, 204, 102, 0.3);
    }

    :global(body.dark-mode) .toast-success {
        border-color: var(--success-color, #00cc66);
        color: var(--success-color, #00cc66);
    }

    .toast-warning {
        border-color: var(--accent-warning, #ffcc00);
        color: var(--accent-warning, #ffcc00);
        box-shadow: inset 0 0 0 1px rgba(255, 204, 0, 0.3);
    }

    :global(body.dark-mode) .toast-warning {
        border-color: var(--accent-warning, #ffcc00);
        color: var(--accent-warning, #ffcc00);
    }

    .toast-error {
        border-color: var(--accent-secondary, #ff3333);
        color: var(--accent-secondary, #ff3333);
        box-shadow: inset 0 0 0 1px rgba(255, 51, 51, 0.3);
    }

    :global(body.dark-mode) .toast-error {
        border-color: var(--accent-secondary, #ff3333);
        color: var(--accent-secondary, #ff3333);
    }

    .toast-message {
        flex: 1;
        line-height: 1.4;
    }

    .toast-close {
        background: none;
        border: none;
        color: inherit;
        font-size: 1.2rem;
        cursor: pointer;
        padding: 0;
        margin-left: 0.5rem;
        opacity: 0.8;
        transition: opacity 0.2s;
        line-height: 1;
    }

    .toast-close:hover {
        opacity: 1;
    }

    @media (max-width: 480px) {
        .toast-container {
            left: 20px;
            right: 20px;
            top: 20px;
            max-width: none;
        }

        .toast {
            min-width: auto;
            max-width: 100%;
            font-size: 0.85rem;
            padding: 0.75rem 1rem;
        }
    }
</style>
