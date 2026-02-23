<script>
    import { onMount, createEventDispatcher } from "svelte";
    import { slide } from "svelte/transition";

    import Calendar from "lucide-svelte/icons/calendar";
    import Clock from "lucide-svelte/icons/clock";
    import Zap from "lucide-svelte/icons/zap";
    import BarChart3 from "lucide-svelte/icons/bar-chart-3";
    import MapPin from "lucide-svelte/icons/map-pin";
    import X from "lucide-svelte/icons/x";
    import IncidentIcon from "./IncidentIcon.svelte";

    const dispatch = createEventDispatcher();

    export let showEventCounters = false;
    export let eventsToday = 0;
    export let eventsLastHour = 0;
    export let eventsActive = 0;
    export let totalIncidents = 0;
    export let timeFilter = "day";
    export let hourlyData = [];
    export let incidentsByType = {};
    export let topLocations = {};
    export let selectedTypes = new Set();
    export let selectedLocations = new Set();
    export let darkMode = true;
    export let historicalCurrentHourAverage = 0;

    let currentTime = new Date();
    let hoveredIndex = null;

    // Div-based chart computations
    $: maxValue = hourlyData && hourlyData.length ? Math.max(...hourlyData) : 0;
    $: yMax = Math.max(maxValue * 1.15, 10);

    $: average =
        hourlyData && hourlyData.length
            ? hourlyData.reduce((a, b) => a + b, 0) / hourlyData.length
            : 0;
    // Define spike relative to historical average for THIS exact hour/day-of-week
    // Using a floor of 2 to avoid dividing zeroes into infinity
    $: spikeThreshold = Math.max(historicalCurrentHourAverage * 1.5, 2);

    // Determine the current traffic status relative to historical average
    $: currentTrafficStatus = (() => {
        // Disable status alerts for long-term historical views
        if (timeFilter === "month" || timeFilter === "year") {
            return {
                text: "",
                color: "transparent",
                isLive: false,
                hidden: true,
            };
        }

        if (!hourlyData || hourlyData.length === 0)
            return {
                text: "NO DATA",
                color: "var(--text-muted)",
                isLive: false,
                hidden: false,
            };
        const currentValue = hourlyData[hourlyData.length - 1];

        if (
            currentValue >= spikeThreshold &&
            currentValue === maxValue &&
            currentValue > 0
        ) {
            return {
                text: "CRITICAL LEVEL",
                color: "#ef4444",
                isLive: true,
                hidden: false,
            };
        } else if (currentValue > historicalCurrentHourAverage * 1.2) {
            return {
                text: "ELEVATED INCIDENTS",
                color: "#f59e0b",
                isLive: false,
                hidden: false,
            };
        } else if (currentValue < historicalCurrentHourAverage * 0.8) {
            return {
                text: "LIGHT INCIDENTS",
                color: "#64748b",
                isLive: false,
                hidden: false,
            };
        } else {
            return {
                text: "NOMINAL",
                color: "#10b981",
                isLive: false,
                hidden: false,
            };
        }
    })();

    // Update currentTime every minute
    onMount(() => {
        const interval = setInterval(() => {
            currentTime = new Date();
        }, 60000);

        return () => {
            clearInterval(interval);
        };
    });

    $: sectionTitle =
        timeFilter === "day"
            ? "24-Hour Activity"
            : timeFilter === "week"
              ? "7-Day Activity"
              : timeFilter === "month"
                ? "30-Day Activity"
                : "Yearly Activity";

    $: chartLabels =
        timeFilter === "day"
            ? Array.from({ length: 24 }, (_, i) => {
                  const time = new Date(
                      currentTime.getTime() - (23 - i) * 60 * 60 * 1000,
                  );
                  return time.toLocaleTimeString("en-US", {
                      hour: "numeric",
                      hour12: true,
                  });
              })
            : timeFilter === "week"
              ? Array.from({ length: 7 }, (_, i) => {
                    const date = new Date();
                    date.setDate(date.getDate() - (6 - i));
                    return date.toLocaleDateString("en-US", {
                        weekday: "short",
                        day: "numeric",
                    });
                })
              : timeFilter === "month"
                ? Array.from({ length: 30 }, (_, i) => {
                      const date = new Date();
                      date.setDate(date.getDate() - (29 - i));
                      return date.toLocaleDateString("en-US", {
                          month: "short",
                          day: "numeric",
                      });
                  })
                : Array.from({ length: 12 }, (_, i) => {
                      const date = new Date();
                      date.setDate(1);
                      date.setMonth(currentTime.getMonth() - (11 - i));
                      return date.toLocaleDateString("en-US", {
                          month: "short",
                      });
                  });

    function setTimeFilter(newFilter) {
        dispatch("filterTime", newFilter);
    }

    function filterByType(type) {
        dispatch("filterType", type);
    }

    function filterByLocation(location) {
        dispatch("filterLocation", location);
    }

    function resetTypeFilters() {
        dispatch("resetTypeFilters");
    }

    function resetLocationFilters() {
        dispatch("resetLocationFilters");
    }
</script>

<div class="event-counters" transition:slide>
    <div class="top-row">
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-icon"><Calendar size={24} /></div>
                <div class="stat-value">{eventsToday}</div>
                <div class="stat-label">Today</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon"><Clock size={24} /></div>
                <div class="stat-value">{eventsLastHour}</div>
                <div class="stat-label">Last Hour</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon"><Zap size={24} /></div>
                <div class="stat-value">{eventsActive}</div>
                <div class="stat-label">Active</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon"><BarChart3 size={24} /></div>
                <div class="stat-value">{totalIncidents}</div>
                <div class="stat-label">Total</div>
            </div>
        </div>
        <div class="time-period-section">
            <span class="section-label">Time Period</span>
            <div class="time-buttons">
                <button
                    class="time-button"
                    class:active={timeFilter === "day"}
                    on:click={() => setTimeFilter("day")}>1 Day</button
                >
                <button
                    class="time-button"
                    class:active={timeFilter === "week"}
                    on:click={() => setTimeFilter("week")}>Week</button
                >
                <button
                    class="time-button"
                    class:active={timeFilter === "month"}
                    on:click={() => setTimeFilter("month")}>Month</button
                >
                <button
                    class="time-button"
                    class:active={timeFilter === "year"}
                    on:click={() => setTimeFilter("year")}>Year</button
                >
            </div>
        </div>
    </div>

    <!-- Activity Chart -->
    <div class="activity-chart-section">
        <div class="activity-header">
            <span class="section-title">{sectionTitle}</span>
            {#if !currentTrafficStatus.hidden}
                <div class="status-indicator">
                    {#if currentTrafficStatus.isLive}
                        <span class="live-badge" transition:slide>LIVE</span>
                    {:else}
                        <span
                            class="status-dot"
                            style="background-color: {currentTrafficStatus.color};"
                        ></span>
                    {/if}
                    <span
                        class="status-text"
                        style="color: {currentTrafficStatus.color};"
                        >{currentTrafficStatus.text}</span
                    >
                </div>
            {/if}
        </div>

        <div class="custom-chart-container">
            {#if hourlyData && hourlyData.length > 0}
                <div class="chart-bars">
                    {#each hourlyData as value, i}
                        <!-- svelte-ignore a11y-no-static-element-interactions -->
                        <div
                            class="bar-wrapper"
                            on:mouseenter={() => (hoveredIndex = i)}
                            on:mouseleave={() => (hoveredIndex = null)}
                        >
                            <div class="bar-container">
                                <div
                                    class="bar"
                                    class:spike={timeFilter !== "month" &&
                                        timeFilter !== "year" &&
                                        value >= spikeThreshold &&
                                        value === maxValue &&
                                        value > 0 &&
                                        i === hourlyData.length - 1}
                                    style="height: {(value / yMax) * 100}%"
                                >
                                    {#if timeFilter !== "month" && timeFilter !== "year" && value >= spikeThreshold && value === maxValue && value > 0 && i === hourlyData.length - 1}
                                        <div class="spike-glow"></div>
                                        <div class="spike-halo"></div>
                                    {/if}
                                </div>
                            </div>
                            <!-- X-axis labels (render a subset depending on timeFilter) -->
                            <div class="x-label-container">
                                {#if timeFilter === "day"}
                                    {#if i % 3 === 0 || i === chartLabels.length - 1}
                                        <span class="x-label"
                                            >{chartLabels[i]
                                                .replace(" AM", "a")
                                                .replace(" PM", "p")}</span
                                        >
                                    {/if}
                                {:else if timeFilter === "week"}
                                    <span class="x-label"
                                        >{chartLabels[i].split(" ")[0]}</span
                                    >
                                {:else if timeFilter === "month"}
                                    {#if i % 5 === 0 || i === chartLabels.length - 1}
                                        <span class="x-label"
                                            >{chartLabels[i].split(
                                                " ",
                                            )[1]}</span
                                        >
                                    {/if}
                                {:else}
                                    <span class="x-label">{chartLabels[i]}</span
                                    >
                                {/if}
                            </div>

                            {#if hoveredIndex === i}
                                <div
                                    class="chart-tooltip"
                                    transition:slide={{ duration: 150 }}
                                >
                                    <div class="tooltip-title">
                                        {chartLabels[i]}
                                    </div>
                                    <div class="tooltip-value">
                                        {value} incidents
                                    </div>
                                </div>
                            {/if}
                        </div>
                    {/each}
                </div>
            {:else}
                <div class="no-data-msg">No activity data available.</div>
            {/if}
        </div>
    </div>

    <!-- Breakdowns -->
    <div class="incident-breakdown-grid">
        <div class="breakdown-card">
            <div class="breakdown-header">
                <div class="breakdown-title-section">
                    <span class="breakdown-icon"><BarChart3 size={18} /></span>
                    <span class="breakdown-title">By Type</span>
                </div>
                {#if selectedTypes.size > 0}
                    <button
                        class="reset-button"
                        on:click={resetTypeFilters}
                        title="Reset type filters"
                    >
                        <X size={14} />
                    </button>
                {/if}
            </div>
            <div class="breakdown-list">
                {#each Object.entries(incidentsByType) as [type, count]}
                    <button
                        class="breakdown-item"
                        class:selected={selectedTypes.has(type)}
                        on:click={() => filterByType(type)}
                    >
                        <span class="breakdown-icon">
                            <IncidentIcon {type} />
                        </span>
                        <span
                            class="breakdown-count-bar"
                            style="width: {(count /
                                Math.max(
                                    ...Object.values(incidentsByType),
                                    1,
                                )) *
                                100}%"
                        ></span>
                        <div class="breakdown-text">
                            <span class="breakdown-name">{type}</span>
                            <span class="breakdown-count">{count}</span>
                        </div>
                    </button>
                {/each}
            </div>
        </div>
        <div class="breakdown-card">
            <div class="breakdown-header">
                <div class="breakdown-title-section">
                    <span class="breakdown-icon"><MapPin size={18} /></span>
                    <span class="breakdown-title">Top Locations</span>
                </div>
                {#if selectedLocations.size > 0}
                    <button
                        class="reset-button"
                        on:click={resetLocationFilters}
                        title="Reset location filters"
                    >
                        <X size={14} />
                    </button>
                {/if}
            </div>
            <div class="breakdown-list">
                {#each Object.entries(topLocations) as [location, count]}
                    <button
                        class="breakdown-item"
                        class:selected={selectedLocations.has(location)}
                        on:click={() => filterByLocation(location)}
                    >
                        <div
                            class="breakdown-count-bar"
                            style="width: {(count /
                                Math.max(...Object.values(topLocations), 1)) *
                                100}%"
                        ></div>
                        <div class="breakdown-text">
                            <span class="breakdown-name">{location}</span>
                            <span class="breakdown-count">{count}</span>
                        </div>
                    </button>
                {/each}
            </div>
        </div>
    </div>
</div>

<style>
    /* Stats Panel Styles - OSINT Redesign */
    .event-counters {
        display: flex;
        flex-direction: column;
        gap: 1.25rem;
        margin-bottom: 1.5rem;
        padding: 1.5rem;
        background: var(--bg-surface-elevated);
        border: 1px solid var(--border-color);
        border-radius: 2px;
        color: var(--text-main);
        overflow: visible;
    }

    .top-row {
        display: flex;
        gap: 1.25rem;
        align-items: stretch;
    }

    .stats-grid {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 0.75rem;
        flex: 1;
    }

    .stat-card {
        background: var(--bg-surface);
        border: 1px solid var(--border-color);
        border-radius: 2px;
        text-align: center;
        padding: 0.75rem;
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
        min-height: 70px;
        transition: all 0.15s ease;
    }

    :global(body.dark-mode) .stat-card {
        background: rgba(0, 0, 0, 0.5);
        border: 1px solid var(--border-color);
    }

    .stat-card:hover {
        border-color: var(--accent-primary);
        background: rgba(51, 102, 255, 0.05);
    }

    .stat-icon {
        font-size: 1.5rem;
        margin-bottom: 0.5rem;
        filter: drop-shadow(0 2px 4px rgba(0, 0, 0, 0.2));
    }

    .stat-value {
        font-size: 2rem;
        font-family: var(--font-pixel);
        font-weight: normal;
        color: var(--accent-secondary);
        text-shadow: 1px 1px 0 rgba(255, 51, 51, 0.3);
    }

    :global(body.dark-mode) .stat-value {
        color: var(--accent-secondary);
    }

    .stat-label {
        font-size: 0.75rem;
        font-weight: 500;
        opacity: 0.7;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-top: 0.25rem;
    }

    .time-period-section {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 0.75rem 1rem;
        background: var(--bg-surface);
        border: 1px solid var(--border-color);
        border-radius: 2px;
        min-width: 180px;
        gap: 0.5rem;
    }

    :global(body.dark-mode) .time-period-section {
        background: rgba(0, 0, 0, 0.5);
        border: 1px solid var(--border-color);
    }

    .section-label {
        font-size: 0.8rem;
        font-weight: 600;
        opacity: 0.8;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }

    .time-buttons {
        display: flex;
        gap: 0.4rem;
        background: var(--bg-surface-elevated);
        padding: 0.3rem;
        border-radius: 2px;
        border: 1px solid var(--border-color);
    }

    :global(body.dark-mode) .time-buttons {
        background: rgba(0, 0, 0, 0.5);
        border: 1px solid var(--border-color);
    }

    .time-button {
        padding: 0.4rem 0.8rem;
        background: transparent;
        border: 1px solid transparent;
        border-radius: 2px;
        color: var(--text-muted);
        font-size: 0.8rem;
        font-family: var(--font-mono);
        text-transform: uppercase;
        cursor: pointer;
        transition: all 0.15s ease;
    }

    :global(body.dark-mode) .time-button {
        color: rgba(255, 255, 255, 0.7);
    }

    .time-button:hover {
        color: var(--text-main);
        border-color: rgba(51, 102, 255, 0.3);
        background: rgba(51, 102, 255, 0.05);
    }

    :global(body.dark-mode) .time-button:hover {
        color: #fff;
        border-color: rgba(51, 102, 255, 0.3);
        background: rgba(51, 102, 255, 0.05);
    }

    .time-button.active {
        background: rgba(51, 102, 255, 0.15);
        color: #fff;
        border-color: var(--accent-primary);
    }

    :global(body.dark-mode) .time-button.active {
        background: rgba(51, 102, 255, 0.15);
        color: #fff;
        border-color: var(--accent-primary);
    }

    .activity-chart-section {
        padding: 1rem 1.25rem;
        background: var(--bg-surface);
        border: 1px solid var(--border-color);
        border-radius: 2px;
        display: flex;
        flex-direction: column;
        gap: 0.75rem;
    }

    :global(body.dark-mode) .activity-chart-section {
        background: rgba(0, 0, 0, 0.5);
        border: 1px solid var(--border-color);
    }

    .activity-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        border-bottom: 1px dashed var(--border-color);
        padding-bottom: 0.5rem;
    }

    .section-title {
        font-size: 1.1rem;
        font-weight: normal;
        font-family: var(--font-pixel);
        color: var(--accent-primary);
    }

    .status-indicator {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        background: rgba(10, 17, 34, 0.4);
        border: 1px solid var(--border-color);
        padding: 0.3rem 0.6rem;
        border-radius: 2px;
        box-shadow: inset 0 0 10px rgba(0, 0, 0, 0.5);
    }

    .status-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        display: inline-block;
        box-shadow: 0 0 5px currentColor;
    }

    .status-text {
        font-family: var(--font-mono);
        font-size: 0.75rem;
        font-weight: bold;
        letter-spacing: 0.05em;
        text-transform: uppercase;
    }

    .live-badge {
        background-color: #ef4444;
        color: white;
        font-family: var(--font-mono);
        font-weight: bold;
        font-size: 0.7rem;
        padding: 0.15rem 0.4rem;
        border-radius: 2px;
        letter-spacing: 0.05em;
        box-shadow: 0 0 8px rgba(239, 68, 68, 0.6);
        animation: subtlePulseBadge 1.5s infinite alternate;
    }

    @keyframes subtlePulseBadge {
        0% {
            box-shadow: 0 0 4px rgba(239, 68, 68, 0.4);
            opacity: 0.8;
        }
        100% {
            box-shadow: 0 0 12px rgba(239, 68, 68, 0.8);
            opacity: 1;
        }
    }

    .custom-chart-container {
        position: relative;
        width: 100%;
        height: 140px;
        margin-top: 5px;
        margin-bottom: 30px;
        display: flex;
        align-items: flex-end;
    }

    .chart-bars {
        display: flex;
        align-items: flex-end;
        justify-content: space-between;
        width: 100%;
        height: 100%;
        gap: 4px;
    }

    .bar-wrapper {
        flex: 1;
        height: 100%;
        display: flex;
        flex-direction: column;
        justify-content: flex-end;
        align-items: center;
        position: relative;
        cursor: pointer;
    }

    .bar-container {
        width: 100%;
        height: 100%;
        display: flex;
        align-items: flex-end;
        position: relative;
        border-bottom: 2px solid rgba(140, 155, 186, 0.3);
    }

    .bar {
        width: 100%;
        background-color: var(--accent-primary);
        border-radius: 2px 2px 0 0;
        transition:
            height 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275),
            background-color 0.3s;
        position: relative;
        min-height: 2px;
    }

    .bar:hover {
        filter: brightness(1.2);
    }

    /* Spike Red Glow Elements */
    .bar.spike {
        background: linear-gradient(
            180deg,
            #ef4444 0%,
            rgba(239, 68, 68, 0.4) 100%
        );
        background-color: #ef4444; /* fallback */
        z-index: 2;
    }

    .spike-glow {
        position: absolute;
        top: -4px;
        left: 0;
        right: 0;
        bottom: 0;
        background: linear-gradient(
            180deg,
            rgba(239, 68, 68, 0.8) 0%,
            transparent 100%
        );
        filter: blur(4px);
        pointer-events: none;
        animation: glowPulse 2s infinite alternate;
    }

    .spike-halo {
        position: absolute;
        top: -15px;
        left: -50%;
        right: -50%;
        height: 30px;
        background: radial-gradient(
            circle,
            rgba(239, 68, 68, 0.4) 0%,
            transparent 70%
        );
        pointer-events: none;
        animation: haloPulse 2s infinite alternate;
    }

    @keyframes glowPulse {
        0% {
            opacity: 0.6;
        }
        100% {
            opacity: 1;
        }
    }

    @keyframes haloPulse {
        0% {
            transform: scale(0.8);
            opacity: 0.4;
        }
        100% {
            transform: scale(1.1);
            opacity: 0.8;
        }
    }

    .x-label-container {
        height: 20px;
        margin-top: 8px;
        display: flex;
        align-items: center;
        justify-content: center;
        position: absolute;
        bottom: -25px;
    }

    .x-label {
        font-size: 0.65rem;
        color: rgba(140, 155, 186, 0.8);
        font-family: var(--font-mono);
        white-space: nowrap;
        position: absolute;
    }

    .chart-tooltip {
        position: absolute;
        bottom: 100%;
        left: 50%;
        transform: translateX(-50%);
        margin-bottom: 8px;
        background: rgba(10, 17, 34, 0.95);
        border: 1px solid rgba(51, 102, 255, 0.3);
        padding: 6px 10px;
        border-radius: 2px;
        z-index: 10;
        pointer-events: none;
        white-space: nowrap;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
    }

    .tooltip-title {
        font-family: var(--font-mono);
        font-size: 0.7rem;
        color: var(--accent-primary);
        margin-bottom: 2px;
    }

    .tooltip-value {
        font-family: var(--font-mono);
        font-size: 0.8rem;
        color: #f8fafc;
        font-weight: bold;
    }

    .no-data-msg {
        width: 100%;
        text-align: center;
        color: var(--text-muted);
        font-size: 0.9rem;
        font-style: italic;
        padding: 2rem 0;
    }

    .incident-breakdown-grid {
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 1rem;
    }

    .breakdown-card {
        background: var(--bg-surface);
        border: 1px solid var(--border-color);
        border-radius: 2px;
        padding: 1rem;
    }

    :global(body.dark-mode) .breakdown-card {
        background: rgba(0, 0, 0, 0.5);
        border: 1px solid var(--border-color);
    }

    .breakdown-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 0.6rem;
        margin-bottom: 0.75rem;
        padding-bottom: 0.6rem;
        border-bottom: 1px solid var(--border-color);
    }

    .breakdown-title-section {
        display: flex;
        align-items: center;
        gap: 0.6rem;
    }

    .reset-button {
        background: var(--bg-surface-elevated);
        border: 1px solid var(--border-color);
        color: var(--text-muted);
        border-radius: 4px;
        padding: 4px;
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        transition: all 0.2s ease;
    }

    .reset-button:hover {
        background: var(--hover-bg);
        color: var(--text-main);
        border-color: var(--accent-primary);
    }

    .breakdown-icon {
        font-size: 1.2rem;
        z-index: 2;
        width: 24px;
        height: 24px;
        display: flex;
        align-items: center;
        justify-content: center;
    }

    .breakdown-title {
        font-size: 0.9rem;
        font-weight: 700;
        letter-spacing: -0.01em;
    }

    .breakdown-list {
        display: flex;
        flex-direction: column;
        gap: 0.5rem;
        max-height: 300px;
        overflow-y: auto;
        padding-right: 0.25rem;
        scrollbar-width: none; /* Firefox */
    }

    .breakdown-list::-webkit-scrollbar {
        display: none; /* Chrome, Safari, Opera */
    }

    .breakdown-item {
        display: flex;
        align-items: center;
        position: relative;
        padding: 0.6rem 0.75rem;
        background: var(--hover-bg);
        border: none;
        border-radius: 2px;
        cursor: pointer;
        transition: all 0.2s ease;
        min-height: 40px;
        overflow: hidden;
        color: var(--text-color);
        text-align: left;
        gap: 0.75rem;
    }

    :global(body.dark-mode) .breakdown-item {
        background: rgba(255, 255, 255, 0.04);
        color: white;
    }

    .breakdown-item:hover {
        background: var(--hover-bg);
        transform: translateX(2px);
    }

    .breakdown-item.selected {
        background: var(--primary-lightest);
        box-shadow: inset 0 0 0 2px var(--primary-color);
    }

    :global(body.dark-mode) .breakdown-item.selected {
        background: rgba(66, 153, 225, 0.2);
        box-shadow: inset 0 0 0 2px var(--primary-light);
    }

    :global(body.dark-mode) .breakdown-item:hover {
        background: rgba(255, 255, 255, 0.1);
    }

    .breakdown-count-bar {
        position: absolute;
        left: 0;
        bottom: 0;
        height: 4px;
        background: var(--accent-primary);
        border-radius: 0;
        z-index: 0;
        transition: width 0.5s ease;
    }

    :global(body.dark-mode) .breakdown-count-bar {
        background: var(--accent-primary);
    }

    .breakdown-text {
        display: flex;
        flex: 1;
        align-items: center;
        justify-content: space-between;
        z-index: 2;
        min-width: 0; /* Enable truncation in flex child */
    }

    .breakdown-name {
        font-weight: 500;
        color: var(--text-darker);
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        margin-right: 0.5rem;
    }

    .breakdown-count {
        font-weight: 600;
        color: var(--text-muted);
        background: rgba(0, 0, 0, 0.05); /* subtle pill background */
        padding: 0.1rem 0.5rem;
        border-radius: 2px;
        font-size: 0.8rem;
        z-index: 2;
    }

    :global(body.dark-mode) .breakdown-count {
        background: rgba(255, 255, 255, 0.15);
    }

    @media (max-width: 768px) {
        .top-row {
            flex-direction: column;
            gap: 0.75rem;
        }
        .stats-grid {
            grid-template-columns: repeat(2, 1fr);
            gap: 0.5rem;
        }
        .stat-card {
            padding: 0.75rem 0.5rem;
            min-height: 75px;
        }
        .event-counters {
            padding: 1rem;
            border-radius: 2px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.2);
        }
        .time-period-section {
            padding: 0.75rem;
            align-items: center;
            border-radius: 2px;
        }
        .time-buttons {
            display: flex;
            flex-wrap: wrap;
            justify-content: center;
            width: auto;
            gap: 0.25rem;
        }
        .time-button {
            padding: 0.45rem 0.7rem;
            font-size: 0.75rem;
        }
        .incident-breakdown-grid {
            grid-template-columns: 1fr;
        }
        .breakdown-list {
            max-height: 280px;
        }
        .breakdown-item {
            min-height: 40px;
            padding: 0.6rem 0.75rem;
        }
        .event-counters {
            overflow: hidden;
        }
        .breakdown-card {
            overflow: hidden;
        }
    }

    @media (max-width: 480px) {
        .event-counters {
            padding: 1rem;
            gap: 0.75rem;
            border-radius: 2px;
            margin-bottom: 0.75rem;
        }
        .stats-grid {
            grid-template-columns: repeat(2, 1fr);
            gap: 0.4rem;
        }
        .stat-card {
            padding: 0.6rem 0.4rem;
            min-height: 70px;
            border-radius: 2px;
        }
        .stat-value {
            font-size: 1.4rem;
        }
        .stat-icon {
            font-size: 1.2rem;
            margin-bottom: 0.25rem;
        }
        .stat-label {
            font-size: 0.65rem;
        }
        .time-period-section {
            padding: 0.6rem;
            border-radius: 2px;
        }
        .section-label {
            font-size: 0.7rem;
        }
        .time-button {
            padding: 0.4rem 0.75rem;
            font-size: 0.75rem;
        }
        .activity-chart-section {
            padding: 0.75rem;
            border-radius: 2px;
        }
        .chart-container {
            height: 150px;
        }
        .section-title {
            font-size: 0.9rem;
        }
        .breakdown-card {
            padding: 0.75rem;
            border-radius: 2px;
            overflow: hidden;
        }
        .breakdown-list {
            max-height: 260px;
        }
        .breakdown-item {
            padding: 0.55rem 0.7rem;
            min-height: 38px;
        }
        .time-button {
            flex: 1 1 calc(50% - 0.125rem);
            min-width: 0;
        }

        @media (max-width: 360px) {
            .event-counters {
                padding: 0.75rem;
                gap: 0.5rem;
                border-radius: 2px;
            }
            .stats-grid {
                gap: 0.3rem;
            }
            .stat-card {
                padding: 0.5rem 0.3rem;
                min-height: 65px;
            }
            .stat-value {
                font-size: 1.25rem;
            }
            .stat-icon {
                font-size: 1rem;
            }
            .stat-label {
                font-size: 0.6rem;
            }
            .time-button {
                padding: 0.35rem 0.6rem;
                font-size: 0.7rem;
            }
            .chart-container {
                height: 130px;
            }
            .breakdown-list {
                max-height: 240px;
            }
            .breakdown-item {
                padding: 0.5rem 0.65rem;
                min-height: 36px;
            }
            .breakdown-name {
                font-size: 0.85rem;
            }
            .breakdown-count {
                font-size: 0.8rem;
            }
        }
    }
</style>
