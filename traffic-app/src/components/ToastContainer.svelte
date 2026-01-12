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
        background-color: var(--primary-lightest, #ebf8ff);
        color: var(--primary-dark, #2c5282);
        border-color: var(--primary-light, #4299e1);
    }

    :global(body.dark-mode) .toast-info {
        background-color: rgba(66, 153, 225, 0.15);
        color: var(--primary-light, #63b3ed);
        border-color: rgba(66, 153, 225, 0.3);
    }

    .toast-success {
        background-color: #f0fff4;
        color: #276749;
        border-color: var(--success-color, #38a169);
    }

    :global(body.dark-mode) .toast-success {
        background-color: rgba(72, 187, 120, 0.15);
        color: #68d391;
        border-color: rgba(72, 187, 120, 0.3);
    }

    .toast-warning {
        background-color: #fffaf0;
        color: #9c4221;
        border-color: var(--accent-color, #ed8936);
    }

    :global(body.dark-mode) .toast-warning {
        background-color: rgba(237, 137, 54, 0.15);
        color: #fbd38d;
        border-color: rgba(237, 137, 54, 0.3);
    }

    .toast-error {
        background-color: var(--error-bg, #fff5f5);
        color: #9b2c2c;
        border-color: var(--error-color, #e53e3e);
    }

    :global(body.dark-mode) .toast-error {
        background-color: rgba(245, 101, 101, 0.15);
        color: #fc8181;
        border-color: rgba(245, 101, 101, 0.3);
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
