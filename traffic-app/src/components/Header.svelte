<script>
    import { createEventDispatcher, onMount, onDestroy } from "svelte";
    import Radio from "lucide-svelte/icons/radio";
    import Shield from "lucide-svelte/icons/shield";
    import Fingerprint from "lucide-svelte/icons/fingerprint";
    import Sun from "lucide-svelte/icons/sun";
    import Moon from "lucide-svelte/icons/moon";

    export let showEventCounters = false;
    export let darkMode = true;

    const dispatch = createEventDispatcher();

    function handleToggleEventCounters() {
        dispatch("toggleEventCounters");
    }

    function handleToggleDarkMode() {
        dispatch("toggleDarkMode");
    }

    let currentTime = "";
    let timeInterval;

    function updateTime() {
        const now = new Date();
        currentTime = now.toLocaleTimeString("en-US", {
            hour12: false,
            hour: "2-digit",
            minute: "2-digit",
            second: "2-digit",
            timeZoneName: "short",
        });
    }

    onMount(() => {
        updateTime();
        timeInterval = setInterval(updateTime, 1000);
    });

    onDestroy(() => {
        if (timeInterval) clearInterval(timeInterval);
    });
</script>

<header class="header">
    <div class="header-top">
        <div class="header-brand">
            <div class="brand-icon">
                <Shield size={40} color="var(--accent-warning)" />
            </div>
            <div class="brand-titles">
                <h1>SAN DIEGO WATCH</h1>
                <p>TACTICAL DISPATCH OVERVIEW</p>
            </div>
        </div>
        <div class="header-controls">
            <div class="header-metrics">
                <div class="metric-row">
                    <Radio
                        size={12}
                        color="var(--accent-primary)"
                        class="pulse-fast"
                    />
                    <span class="metric-label"
                        >DISPATCH FEED • {currentTime}</span
                    >
                </div>
                <div class="metric-row subtext">MONITORING INCIDENTS</div>
            </div>
            <button
                class="theme-toggle"
                on:click={handleToggleDarkMode}
                title={darkMode
                    ? "Switch to Light Mode"
                    : "Switch to Dark Mode"}
            >
                {#if darkMode}
                    <Sun size={18} />
                {:else}
                    <Moon size={18} />
                {/if}
            </button>
        </div>
    </div>

    <button class="header-action-banner" on:click={handleToggleEventCounters}>
        <div class="banner-icon"><Fingerprint size={18} /></div>
        <div class="banner-text">
            SYSTEM DIAGNOSTICS
            <span class="banner-subtext">STATISTICS</span>
        </div>
        <div class="banner-status" class:active={showEventCounters}>
            {showEventCounters ? "[-]" : "[+]"}
        </div>
    </button>
</header>

<style>
    .header {
        margin-bottom: 0.5rem;
        display: flex;
        flex-direction: column;
        gap: 1rem;
        font-family: var(--font-mono);
    }

    .header-top {
        display: flex;
        justify-content: space-between;
        align-items: flex-end;
        padding: 0 0.5rem;
    }

    .header-brand {
        display: flex;
        align-items: center;
        gap: 1rem;
    }

    .brand-icon {
        image-rendering: pixelated;
    }

    .brand-titles h1 {
        margin: 0;
        font-size: 3rem;
        font-family: var(--font-pixel);
        color: var(--accent-primary);
        text-transform: uppercase;
        letter-spacing: 0.05em;
        line-height: 0.9;
        text-shadow: 2px 2px 0px rgba(0, 0, 0, 0.2);
    }

    :global(.dark-mode) .brand-titles h1 {
        color: #ffffff;
        text-shadow: 2px 2px 0px rgba(51, 102, 255, 0.4);
    }

    .brand-titles p {
        margin: 0.5rem 0 0 0;
        font-size: 0.75rem;
        color: var(--text-muted);
        text-transform: uppercase;
        letter-spacing: 0.1em;
    }

    .header-metrics {
        display: flex;
        flex-direction: column;
        align-items: flex-start;
        font-size: 0.8rem;
        gap: 0.3rem;
        padding-bottom: 0.2rem;
    }

    .header-controls {
        display: flex;
        align-items: center;
        gap: 1.5rem;
    }

    .theme-toggle {
        background: rgba(51, 102, 255, 0.1);
        border: 1px solid var(--accent-primary);
        color: var(--accent-primary);
        width: 40px;
        height: 40px;
        display: flex;
        align-items: center;
        justify-content: center;
        cursor: pointer;
        transition: all 0.2s ease;
        border-radius: 2px;
        box-shadow: 0 0 10px rgba(51, 102, 255, 0.15);
        position: relative;
        overflow: hidden;
    }

    .theme-toggle::after {
        content: "";
        position: absolute;
        top: -50%;
        left: -50%;
        width: 200%;
        height: 200%;
        background: radial-gradient(
            circle,
            rgba(51, 102, 255, 0.1) 0%,
            transparent 70%
        );
        opacity: 0;
        transition: opacity 0.3s ease;
    }

    .theme-toggle:hover::after {
        opacity: 1;
    }

    .theme-toggle:hover {
        background: rgba(51, 102, 255, 0.2);
        color: #fff;
        box-shadow: 0 0 20px rgba(51, 102, 255, 0.4);
        border-color: #6688ff;
    }

    .theme-toggle:active {
        transform: translateY(1px);
    }

    .metric-row {
        display: flex;
        align-items: center;
        gap: 0.4rem;
        color: var(--accent-primary);
        font-weight: bold;
        letter-spacing: 0.05em;
    }

    .metric-row.subtext {
        color: var(--accent-primary);
        font-size: 0.7rem;
        opacity: 0.8;
    }

    .header-action-banner {
        display: flex;
        align-items: center;
        gap: 1rem;
        width: 100%;
        background: var(--bg-surface-elevated);
        border: 1px solid var(--accent-primary);
        border-radius: 2px;
        padding: 1.25rem 1.75rem;
        color: var(--text-main);
        cursor: pointer;
        text-align: left;
        transition: all 0.15s ease;
        box-shadow: inset 0 0 0 1px rgba(51, 102, 255, 0.2);
    }

    .header-action-banner:hover {
        background: var(--hover-bg, #111a30);
        border-color: #4d7dff;
    }

    .header-action-banner:active {
        transform: translateY(1px);
    }

    .banner-icon {
        color: var(--accent-primary);
        display: flex;
        align-items: center;
        justify-content: center;
    }

    .banner-text {
        flex: 1;
        display: flex;
        flex-direction: column;
        font-size: 1.5rem;
        font-weight: normal;
        letter-spacing: 0.08em;
        font-family: var(--font-pixel);
        color: var(--accent-primary);
    }

    .banner-subtext {
        font-size: 0.75rem;
        font-family: var(--font-mono);
        color: var(--text-muted);
        letter-spacing: 0.05em;
        margin-top: 0.4rem;
        text-transform: uppercase;
    }

    .banner-status {
        color: var(--text-muted);
        font-family: var(--font-mono);
        font-size: 1.25rem;
        font-weight: bold;
    }

    .banner-status.active {
        color: var(--accent-primary);
    }

    :global(.pulse-fast) {
        animation: pulseHeart 1s infinite alternate step-end;
    }

    @keyframes pulseHeart {
        from {
            opacity: 0.2;
        }
        to {
            opacity: 1;
        }
    }

    @media (max-width: 768px) {
        .header-top {
            flex-direction: column;
            align-items: flex-start;
            gap: 1.5rem;
            text-align: left;
        }
        .header-brand {
            flex-direction: row;
            align-items: center;
            gap: 0.75rem;
        }
        .header-controls {
            width: 100%;
            justify-content: space-between;
            gap: 1rem;
        }
        .header-metrics {
            align-items: flex-start;
        }
        .brand-titles h1 {
            font-size: 2.2rem;
        }
        .theme-toggle {
            width: 44px;
            height: 44px;
        }
        .header-action-banner {
            padding: 0.75rem 1rem;
        }
        .banner-text {
            font-size: 1.25rem;
        }
    }
</style>
