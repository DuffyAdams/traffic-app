<script>
    export let events = [];

    // Format text to remove newlines and truncate if necessary
    function formatText(str, length = 80) {
        if (!str) return "";
        let cleanStr = str
            .replace(/[\r\n]+/g, " ")
            .replace(/\s+/g, " ")
            .trim();
        return cleanStr.length > length
            ? cleanStr.substring(0, length) + "..."
            : cleanStr;
    }
</script>

{#if events.length > 0}
    <div class="ticker-wrapper">
        <div class="ticker-label">
            <span class="blinking-dot"></span>
            LATEST
        </div>
        <div class="ticker-content">
            <div class="ticker-track">
                <div class="ticker-group">
                    {#each events as event}
                        <div class="ticker-item">
                            <span class="ticker-time">[{event.time}]</span>
                            <span class="ticker-type"
                                >{formatText(
                                    event.type,
                                    30,
                                ).toUpperCase()}</span
                            >
                            <span class="ticker-desc">
                                {event.location
                                    ? formatText(
                                          event.location,
                                          40,
                                      ).toUpperCase()
                                    : "UNKNOWN"} :: {formatText(
                                    event.description,
                                    80,
                                ).toUpperCase()}
                            </span>
                        </div>
                    {/each}
                </div>
                <!-- Duplicate for infinite scroll -->
                <div class="ticker-group" aria-hidden="true">
                    {#each events as event}
                        <div class="ticker-item">
                            <span class="ticker-time">[{event.time}]</span>
                            <span class="ticker-type"
                                >{formatText(
                                    event.type,
                                    30,
                                ).toUpperCase()}</span
                            >
                            <span class="ticker-desc">
                                {event.location
                                    ? formatText(
                                          event.location,
                                          40,
                                      ).toUpperCase()
                                    : "UNKNOWN"} :: {formatText(
                                    event.description,
                                    80,
                                ).toUpperCase()}
                            </span>
                        </div>
                    {/each}
                </div>
            </div>
        </div>
    </div>
{/if}

<style>
    .ticker-wrapper {
        display: flex;
        align-items: center;
        background: var(--bg-surface-elevated, #111824);
        border: 1px solid var(--accent-primary, #4299e1);
        border-radius: 4px;
        margin-bottom: 0.5rem;
        overflow: hidden;
        height: 36px;
        box-shadow: inset 0 0 0 1px rgba(51, 102, 255, 0.2);
        font-family: var(--font-mono, monospace);
    }

    .ticker-label {
        background: var(--accent-primary, #4299e1);
        color: var(--bg-base, #000);
        padding: 0 1rem;
        height: 100%;
        display: flex;
        align-items: center;
        gap: 0.5rem;
        font-weight: bold;
        font-size: 0.8rem;
        letter-spacing: 0.1em;
        white-space: nowrap;
        z-index: 2;
        position: relative;
        box-shadow: 2px 0 5px rgba(0, 0, 0, 0.5);
    }

    .blinking-dot {
        width: 6px;
        height: 6px;
        background-color: var(--bg-base, #000);
        border-radius: 50%;
        animation: blink 1s infinite alternate;
    }

    @keyframes blink {
        0% {
            opacity: 0.3;
        }
        100% {
            opacity: 1;
        }
    }

    .ticker-content {
        flex: 1;
        overflow: hidden;
        position: relative;
        height: 100%;
        display: flex;
        align-items: center;
        mask-image: linear-gradient(
            to right,
            transparent,
            black 2%,
            black 98%,
            transparent
        );
        -webkit-mask-image: linear-gradient(
            to right,
            transparent,
            black 2%,
            black 98%,
            transparent
        );
    }

    .ticker-track {
        display: flex;
        width: max-content;
        animation: scroll 45s linear infinite;
    }

    .ticker-track:hover {
        animation-play-state: paused;
    }

    .ticker-group {
        display: flex;
        gap: 3rem;
        padding-right: 3rem;
    }

    .ticker-item {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        font-size: 0.8rem;
        letter-spacing: 0.05em;
        white-space: nowrap;
        flex-shrink: 0;
    }

    .ticker-time {
        color: var(--text-muted, #a0aec0);
    }

    .ticker-type {
        color: var(--accent-color, #ed8936);
        font-weight: bold;
    }

    :global(.dark-mode) .ticker-type {
        color: #ff9900;
    }

    .ticker-desc {
        color: var(--text-main, #f8fafc);
    }

    @keyframes scroll {
        0% {
            transform: translateX(0);
        }
        100% {
            transform: translateX(-50%);
        }
    }

    @media (max-width: 768px) {
        .ticker-label {
            padding: 0 0.5rem;
            font-size: 0.7rem;
        }
        .ticker-item {
            font-size: 0.75rem;
        }
        .ticker-group {
            gap: 2rem;
            padding-right: 2rem;
        }
        .ticker-wrapper {
            margin-bottom: 0.75rem;
        }
    }
</style>
