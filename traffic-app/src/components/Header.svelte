<script>
    import { createEventDispatcher } from "svelte";
    import { Sun, Moon, ChevronDown, ChevronUp } from "lucide-svelte";

    export let darkMode = false;
    export let showEventCounters = false;

    const dispatch = createEventDispatcher();

    function handleToggleDarkMode() {
        dispatch("toggleDarkMode");
    }

    function handleToggleEventCounters() {
        dispatch("toggleEventCounters");
    }
</script>

<header class="header">
    <button
        class="dark-mode-toggle"
        class:is-dark={darkMode}
        on:click={handleToggleDarkMode}
        aria-label="Toggle dark mode"
    >
        <Sun size={18} class="sun-icon" />
        <Moon size={18} class="moon-icon" />
    </button>

    <button class="header-content" on:click={handleToggleEventCounters}>
        <h1>San Diego Watch</h1>
        <p>Real-time emergency and traffic incidents across San Diego</p>
        <div class="stats-toggle">
            Incident Stats
            {#if showEventCounters}
                <ChevronUp size={16} />
            {:else}
                <ChevronDown size={16} />
            {/if}
        </div>
    </button>
</header>

<style>
    .header {
        text-align: center;
        margin-bottom: 1.5rem;
        padding: 2rem 1.5rem;
        background: linear-gradient(135deg, #ffffff 0%, #f0f7ff 100%);
        color: #1a365d; /* Deep navy blue for better aesthetics */
        border-radius: 20px;
        box-shadow:
            0 10px 30px rgba(0, 0, 0, 0.04),
            inset 0 1px 0 rgba(255, 255, 255, 0.6);
        position: relative;
        overflow: hidden;
        transition: all 0.3s ease;
        border: 1px solid #e2e8f0;
    }

    :global(body.dark-mode) .header {
        background: linear-gradient(135deg, #1e3a5f 0%, #0d2137 100%);
        color: white;
        box-shadow:
            0 10px 40px rgba(0, 0, 0, 0.3),
            inset 0 1px 0 rgba(255, 255, 255, 0.1);
        border: none;
    }

    .header::before {
        content: "";
        position: absolute;
        top: -50%;
        left: -50%;
        width: 200%;
        height: 200%;
        background: radial-gradient(
            circle,
            rgba(66, 153, 225, 0.08) 0%,
            rgba(255, 255, 255, 0) 60%
        );
        opacity: 1;
        transform: rotate(30deg);
        pointer-events: none;
        transition: opacity 0.3s ease;
    }

    :global(body.dark-mode) .header::before {
        background: radial-gradient(
            circle,
            rgba(255, 255, 255, 0.1) 0%,
            rgba(255, 255, 255, 0) 60%
        );
        opacity: 0.6;
    }

    .dark-mode-toggle {
        position: absolute;
        top: 1rem;
        right: 1.5rem;
        background: rgba(255, 255, 255, 0.9);
        border: 1px solid #e2e8f0;
        border-radius: 50%;
        width: 36px;
        height: 36px;
        cursor: pointer;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        z-index: 10;
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 0;
        box-shadow:
            0 4px 6px -1px rgba(0, 0, 0, 0.1),
            0 2px 4px -1px rgba(0, 0, 0, 0.06);
        color: #4a5568;
    }

    .dark-mode-toggle.is-dark {
        background: rgba(30, 41, 59, 0.8);
        border: 1px solid rgba(255, 255, 255, 0.1);
        color: #f7fafc;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3);
    }

    .dark-mode-toggle:hover {
        transform: scale(1.1);
        background: #ffffff;
        color: #2b6cb0;
        border-color: #cbd5e0;
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
    }

    .dark-mode-toggle.is-dark:hover {
        background: #1e293b;
        color: #63b3ed;
        border-color: rgba(255, 255, 255, 0.2);
    }

    :global(.sun-icon),
    :global(.moon-icon) {
        position: absolute;
        transition: all 0.5s cubic-bezier(0.4, 0, 0.2, 1);
    }

    /* Icons in Light Mode (Default) */
    :global(.sun-icon) {
        transform: scale(1) rotate(0deg);
        opacity: 1;
    }
    :global(.moon-icon) {
        transform: scale(0) rotate(90deg);
        opacity: 0;
    }

    /* Icons in Dark Mode */
    .is-dark :global(.sun-icon) {
        transform: scale(0) rotate(-90deg);
        opacity: 0;
    }
    .is-dark :global(.moon-icon) {
        transform: scale(1) rotate(0deg);
        opacity: 1;
    }

    .header-content {
        text-align: center;
        cursor: pointer;
        user-select: none;
        transition: transform 0.2s;
        padding: 0.5rem;
        position: relative;
        z-index: 1;
        background: none;
        border: none;
        color: inherit;
        width: 100%;
    }

    .header-content:active {
        transform: scale(0.98);
    }

    .header h1 {
        margin: 0 0 0.5rem 0;
        font-size: 2.4rem;
        font-weight: 800;
        letter-spacing: -0.025em;
        text-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
    }

    .header p {
        margin: 0 0 0.5rem 0;
        font-size: 0.95rem;
        opacity: 0.9;
        font-weight: 500;
    }

    .stats-toggle {
        display: inline-flex;
        align-items: center;
        gap: 0.5rem;
        padding: 0.4rem 1rem;
        background: rgba(0, 0, 0, 0.05);
        border-radius: 20px;
        font-size: 0.9rem;
        font-weight: 600;
        transition: background 0.2s;
        border: 1px solid rgba(0, 0, 0, 0.05);
    }

    :global(body.dark-mode) .stats-toggle {
        background: rgba(255, 255, 255, 0.15);
        border: none;
    }

    .header-content:hover .stats-toggle {
        background: rgba(0, 0, 0, 0.1);
    }

    :global(body.dark-mode) .header-content:hover .stats-toggle {
        background: rgba(255, 255, 255, 0.25);
    }

    @media (max-width: 768px) {
        .header {
            padding: 1.25rem 3rem;
            margin-bottom: 0.8rem;
            border-radius: 12px;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2);
            overflow: hidden; /* Ensure 200% width pseudo-element doesn't cause page overflow */
        }
        .header h1 {
            font-size: 1.4rem;
            margin-bottom: 0.3rem;
        }
        .header p {
            font-size: 0.9rem;
        }
        .dark-mode-toggle {
            top: 0.8rem;
            right: 0.8rem;
            width: 32px;
            height: 32px;
        }
    }

    @media (max-width: 480px) {
        .header {
            padding: 0.8rem 3rem 0.8rem 3rem;
            margin-bottom: 0.7rem;
            border-radius: 10px;
        }
        .header h1 {
            font-size: 1.25rem;
        }
    }
</style>
