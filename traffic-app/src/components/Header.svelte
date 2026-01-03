<script>
    import { createEventDispatcher } from "svelte";

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
        on:click={handleToggleDarkMode}
        aria-label="Toggle dark mode"
    >
        {darkMode ? "☀️" : "🌙"}
    </button>

    <button class="header-content" on:click={handleToggleEventCounters}>
        <h1>San Diego Traffic Watch</h1>
        <p>Real-time incidents from CHP scanner data</p>
        <span class="stats-toggle"
            >Incident Stats {showEventCounters ? "▲" : "▼"}</span
        >
    </button>
</header>

<style>
    .header {
        text-align: center;
        margin-bottom: 1.5rem;
        padding: 1.5rem;
        background: linear-gradient(135deg, #1e3a5f 0%, #0d2137 100%);
        color: white;
        border-radius: 20px;
        box-shadow:
            0 10px 40px rgba(0, 0, 0, 0.3),
            inset 0 1px 0 rgba(255, 255, 255, 0.1);
        position: relative;
        overflow: hidden;
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
            rgba(255, 255, 255, 0.1) 0%,
            rgba(255, 255, 255, 0) 60%
        );
        opacity: 0.6;
        transform: rotate(30deg);
        pointer-events: none;
    }

    .dark-mode-toggle {
        position: absolute;
        top: 1rem;
        right: 1rem;
        background: linear-gradient(
            135deg,
            rgba(255, 255, 255, 0.25) 0%,
            rgba(255, 255, 255, 0.1) 100%
        );
        border: 1px solid rgba(255, 255, 255, 0.2);
        border-radius: 24px;
        width: 52px;
        height: 28px;
        font-size: 0.9rem;
        cursor: pointer;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        z-index: 2;
        display: flex;
        align-items: center;
        justify-content: flex-start;
        padding: 3px;
        box-shadow:
            inset 0 1px 0 rgba(255, 255, 255, 0.2),
            0 2px 8px rgba(0, 0, 0, 0.15);
        overflow: hidden;
    }

    .dark-mode-toggle::before {
        content: "";
        position: absolute;
        width: 22px;
        height: 22px;
        background: white;
        border-radius: 50%;
        left: 3px;
        transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        box-shadow: 0 2px 6px rgba(0, 0, 0, 0.2);
    }

    :global(body.dark-mode) .dark-mode-toggle::before {
        transform: translateX(24px);
    }

    .dark-mode-toggle:hover {
        background: linear-gradient(
            135deg,
            rgba(255, 255, 255, 0.35) 0%,
            rgba(255, 255, 255, 0.15) 100%
        );
        transform: scale(1.05);
        box-shadow:
            inset 0 1px 0 rgba(255, 255, 255, 0.3),
            0 4px 12px rgba(0, 0, 0, 0.2);
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
        color: white;
        width: 100%;
    }

    .header-content:active {
        transform: scale(0.98);
    }

    .header h1 {
        margin: 0 0 0.5rem 0;
        font-size: 2rem;
        font-weight: 800;
        letter-spacing: -0.025em;
        text-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
    }

    .header p {
        margin: 0 0 0.5rem 0;
        font-size: 1.1rem;
        opacity: 0.9;
        font-weight: 500;
    }

    .stats-toggle {
        display: inline-block;
        padding: 0.4rem 1rem;
        background: rgba(255, 255, 255, 0.15);
        border-radius: 20px;
        font-size: 0.9rem;
        font-weight: 600;
        transition: background 0.2s;
    }

    .header-content:hover .stats-toggle {
        background: rgba(255, 255, 255, 0.25);
    }

    @media (max-width: 768px) {
        .header {
            padding: 0.8rem;
            margin-bottom: 0.8rem;
            border-radius: 12px;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2);
            overflow: visible;
        }
        .header h1 {
            font-size: 1.5rem;
            margin-bottom: 0.3rem;
        }
        .header p {
            font-size: 0.9rem;
        }
        .dark-mode-toggle {
            top: 0.6rem;
            right: 0.6rem;
            width: 44px;
            height: 24px;
            border-radius: 20px;
            padding: 2px;
        }
        .dark-mode-toggle::before {
            width: 18px;
            height: 18px;
            left: 3px;
        }
    }
    @media (max-width: 768px) {
        :global(body.dark-mode) .dark-mode-toggle::before {
            transform: translateX(18px);
        }
    }

    @media (max-width: 480px) {
        .header {
            padding: 0.7rem;
            margin-bottom: 0.7rem;
            border-radius: 10px;
        }
    }
</style>
