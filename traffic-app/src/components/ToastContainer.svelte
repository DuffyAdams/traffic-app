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
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
        font-size: 0.9rem;
        font-weight: 500;
        backdrop-filter: blur(8px);
        border: 1px solid rgba(255, 255, 255, 0.1);
        min-width: 300px;
    }

    .toast-info {
        background-color: var(--primary-color);
        color: white;
    }

    .toast-success {
        background-color: var(--success-color);
        color: white;
    }

    .toast-warning {
        background-color: var(--accent-color);
        color: white;
    }

    .toast-error {
        background-color: var(--error-color);
        color: white;
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
