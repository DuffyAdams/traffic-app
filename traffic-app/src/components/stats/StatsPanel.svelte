<script>
    import { onMount, createEventDispatcher } from "svelte";
    import { slide } from "svelte/transition";

    import Calendar from "lucide-svelte/icons/calendar";
    import Clock from "lucide-svelte/icons/clock";
    import Zap from "lucide-svelte/icons/zap";
    import BarChart3 from "lucide-svelte/icons/bar-chart-3";
    import MapPin from "lucide-svelte/icons/map-pin";
    import X from "lucide-svelte/icons/x";
    import IncidentIcon from "../shared/IncidentIcon.svelte";
    import { formatDateTime, formatNumber, t } from "../../utils/i18n.js";

    const dispatch = createEventDispatcher();
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
    export let historicalCurrentHourAverage = 0;
    export let referenceTime = "";

    function parseReferenceTime(value) {
        const fallback = new Date();
        if (!value) return fallback;

        const parsed = new Date(value);
        return Number.isNaN(parsed.getTime()) ? fallback : parsed;
    }

    let currentTime = parseReferenceTime(referenceTime);
    let hoveredIndex = null;

    $: expectedBucketCount =
        timeFilter === "day"
            ? 24
            : timeFilter === "week"
              ? 7
              : timeFilter === "month"
                ? 30
                : 12;
    $: chartData = normalizeChartData(hourlyData, expectedBucketCount);
    $: typeEntries = Object.entries(incidentsByType);
    $: locationEntries = Object.entries(topLocations);
    $: maxTypeCount = Math.max(...typeEntries.map(([, count]) => count), 1);
    $: maxLocationCount = Math.max(...locationEntries.map(([, count]) => count), 1);

    // Div-based chart computations
    $: maxValue = chartData && chartData.length ? Math.max(...chartData) : 0;
    $: yMax = Math.max(maxValue * 1.15, 10);

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

        if (!chartData || chartData.length === 0)
            return {
                text: t("status.noData"),
                color: "var(--text-muted)",
                isLive: false,
                hidden: false,
            };
        const currentValue = chartData[chartData.length - 1];

        if (
            currentValue >= spikeThreshold &&
            currentValue === maxValue &&
            currentValue > 0
        ) {
            return {
                text: t("status.criticalLevel"),
                color: "#ef4444",
                isLive: true,
                hidden: false,
            };
        } else if (currentValue > historicalCurrentHourAverage * 1.2) {
            return {
                text: t("status.elevatedIncidents"),
                color: "#f59e0b",
                isLive: false,
                hidden: false,
            };
        } else if (currentValue < historicalCurrentHourAverage * 0.8) {
            return {
                text: t("status.lightIncidents"),
                color: "#64748b",
                isLive: false,
                hidden: false,
            };
        } else {
            return {
                text: t("status.nominal"),
                color: "#10b981",
                isLive: false,
                hidden: false,
            };
        }
    })();

    // Update currentTime every minute
    onMount(() => {
        const interval = setInterval(() => {
            currentTime = new Date(currentTime.getTime() + 60000);
        }, 60000);

        return () => {
            clearInterval(interval);
        };
    });

    $: if (referenceTime) {
        currentTime = parseReferenceTime(referenceTime);
    }

    $: sectionTitle =
        timeFilter === "day"
            ? t("diagnostics.activity24Hours")
            : timeFilter === "week"
              ? t("diagnostics.activity7Days")
              : timeFilter === "month"
                ? t("diagnostics.activity30Days")
                : t("diagnostics.yearlyActivity");

    $: chartLabels =
        timeFilter === "day"
            ? Array.from({ length: 24 }, (_, i) => {
                  const time = new Date(
                      currentTime.getTime() - (23 - i) * 60 * 60 * 1000,
                  );
                  return formatDateTime(time, {
                      hour: "numeric",
                  });
              })
            : timeFilter === "week"
              ? Array.from({ length: 7 }, (_, i) => {
                    const date = new Date();
                    date.setDate(date.getDate() - (6 - i));
                    return formatDateTime(date, {
                        weekday: "short",
                    });
                })
              : timeFilter === "month"
                ? Array.from({ length: 30 }, (_, i) => {
                      const date = new Date();
                      date.setDate(date.getDate() - (29 - i));
                      return formatDateTime(date, {
                          day: "numeric",
                      });
                  })
                : Array.from({ length: 12 }, (_, i) => {
                      const date = new Date();
                      date.setDate(1);
                      date.setMonth(currentTime.getMonth() - (11 - i));
                      return formatDateTime(date, {
                          month: "short",
                      });
                  });

    function normalizeChartData(values, expectedLength) {
        const data = Array.isArray(values) ? values.map(Number) : [];
        if (data.length === expectedLength) return data;
        if (data.length > expectedLength) return data.slice(data.length - expectedLength);
        return [...Array(expectedLength - data.length).fill(0), ...data];
    }

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

<div class="event-counters">
    <div class="top-row">
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-icon"><Calendar size={24} /></div>
                <div class="stat-value">{formatNumber(eventsToday)}</div>
                <div class="stat-label">{t("diagnostics.today")}</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon"><Clock size={24} /></div>
                <div class="stat-value">{formatNumber(eventsLastHour)}</div>
                <div class="stat-label">{t("diagnostics.lastHour")}</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon"><Zap size={24} /></div>
                <div class="stat-value">{formatNumber(eventsActive)}</div>
                <div class="stat-label">{t("diagnostics.active")}</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon"><BarChart3 size={24} /></div>
                <div class="stat-value">{formatNumber(totalIncidents)}</div>
                <div class="stat-label">{t("diagnostics.total")}</div>
            </div>
        </div>
        <div class="time-period-section">
            <span class="section-label">{t("diagnostics.timePeriod")}</span>
            <div class="time-buttons">
                <button
                    class="time-button"
                    class:active={timeFilter === "day"}
                    on:click={() => setTimeFilter("day")}>{t("diagnostics.oneDay")}</button
                >
                <button
                    class="time-button"
                    class:active={timeFilter === "week"}
                    on:click={() => setTimeFilter("week")}>{t("diagnostics.week")}</button
                >
                <button
                    class="time-button"
                    class:active={timeFilter === "month"}
                    on:click={() => setTimeFilter("month")}>{t("diagnostics.month")}</button
                >
                <button
                    class="time-button"
                    class:active={timeFilter === "year"}
                    on:click={() => setTimeFilter("year")}>{t("diagnostics.year")}</button
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
                        <span class="live-badge" transition:slide>{t("status.live")}</span>
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
            {#if chartData && chartData.length > 0}
                <div class="chart-bars">
                    {#each chartData as value, i (`${timeFilter}-${i}`)}
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
                                        <span class="x-label">{chartLabels[i]}</span>
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
                                        {t("diagnostics.incidentsCount", { count: value })}
                                    </div>
                                </div>
                            {/if}
                        </div>
                    {/each}
                </div>
            {:else}
                <div class="no-data-msg">{t("diagnostics.noActivityData")}</div>
            {/if}
        </div>
    </div>

    <!-- Breakdowns -->
    <div class="incident-breakdown-grid">
        <div class="breakdown-card">
            <div class="breakdown-header">
                <div class="breakdown-title-section">
                    <span class="breakdown-icon"><BarChart3 size={18} /></span>
                    <span class="breakdown-title">{t("diagnostics.byType")}</span>
                </div>
                {#if selectedTypes.size > 0}
                    <button
                        class="reset-button"
                        on:click={resetTypeFilters}
                        title={t("actions.resetTypeFilters")}
                    >
                        <X size={14} />
                    </button>
                {/if}
            </div>
            <div class="breakdown-list">
                {#each typeEntries as [type, count]}
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
                            style="width: {(count / maxTypeCount) * 100}%"
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
                    <span class="breakdown-title">{t("diagnostics.topLocations")}</span>
                </div>
                {#if selectedLocations.size > 0}
                    <button
                        class="reset-button"
                        on:click={resetLocationFilters}
                        title={t("actions.resetLocationFilters")}
                    >
                        <X size={14} />
                    </button>
                {/if}
            </div>
            <div class="breakdown-list">
                {#each locationEntries as [location, count]}
                    <button
                        class="breakdown-item"
                        class:selected={selectedLocations.has(location)}
                        on:click={() => filterByLocation(location)}
                    >
                        <div
                            class="breakdown-count-bar"
                            style="width: {(count / maxLocationCount) * 100}%"
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
        gap: 0.8rem;
        margin-bottom: 1rem;
        padding: 0.9rem;
        background: var(--bg-surface);
        border: 1px solid var(--border-color);
        border-top: 0;
        border-radius: 0 0 var(--radius-xl) var(--radius-xl);
        color: var(--text-main);
        overflow: visible;
        box-shadow: var(--shadow-md);
    }

    .top-row {
        display: flex;
        gap: 0.8rem;
        align-items: stretch;
    }

    .stats-grid {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 0.55rem;
        flex: 1;
    }

    .stat-card {
        background: var(--bg-surface-elevated);
        border: 1px solid var(--border-color);
        border-radius: 15px;
        text-align: left;
        padding: 0.6rem 0.7rem;
        display: grid;
        grid-template-columns: 28px minmax(0, 1fr);
        grid-template-rows: auto auto;
        column-gap: 0.55rem;
        align-content: center;
        align-items: center;
        min-height: 56px;
        transition: transform .3s var(--ease-out), border-color .2s, background .2s;
    }

    .stat-card:hover {
        border-color: color-mix(in srgb, var(--accent-primary) 35%, var(--border-color));
        background: var(--primary-lightest);
        transform: translateY(-2px);
    }

    .stat-icon {
        grid-row: 1 / 3;
        color: var(--accent-primary);
        filter: drop-shadow(0 2px 4px rgba(0, 0, 0, 0.2));
    }

    .stat-icon :global(svg) {
        width: 20px;
        height: 20px;
    }

    .stat-value {
        font-size: 1.45rem;
        font-weight: 760;
        letter-spacing: -.04em;
        line-height: 1;
        color: var(--text-main);
    }

    .stat-label {
        font-size: 0.75rem;
        font-weight: 500;
        opacity: 0.7;
        letter-spacing: -0.01em;
        line-height: 1.1;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }

    .time-period-section {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 0.55rem 0.65rem;
        background: var(--bg-surface-elevated);
        border: 1px solid var(--border-color);
        border-radius: 15px;
        min-width: 270px;
        gap: 0.35rem;
    }

    .section-label {
        font-size: 0.72rem;
        font-weight: 600;
        opacity: 0.8;
        letter-spacing: -0.01em;
    }

    .time-buttons {
        display: flex;
        gap: 0.25rem;
        background: var(--bg-surface-elevated);
        padding: 0.2rem;
        border-radius: 11px;
        border: 1px solid var(--border-color);
    }

    .time-button {
        padding: 0.35rem 0.65rem;
        background: transparent;
        border: 1px solid transparent;
        border-radius: 8px;
        color: var(--text-muted);
        font-size: 0.75rem;
        font-weight: 650;
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
        background: var(--primary-lightest);
        color: var(--accent-primary);
        border-color: color-mix(in srgb, var(--accent-primary) 38%, var(--border-color));
    }

    .activity-chart-section {
        padding: 0.75rem 0.9rem;
        background: var(--bg-surface);
        border: 1px solid var(--border-color);
        border-radius: 16px;
        display: flex;
        flex-direction: column;
        gap: 0.5rem;
    }

    .activity-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        border-bottom: 1px solid var(--border-color);
        padding-bottom: 0.4rem;
    }

    .section-title {
        font-size: 0.95rem;
        font-weight: 720;
        color: var(--text-main);
    }

    .status-indicator {
        display: flex;
        align-items: center;
        gap: 0.35rem;
        background: var(--bg-surface-elevated);
        border: 1px solid var(--border-color);
        padding: 0.25rem 0.5rem;
        border-radius: 999px;
    }

    .status-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        display: inline-block;
        box-shadow: 0 0 5px currentColor;
    }

    .status-text {
        font-size: 0.68rem;
        font-weight: bold;
        letter-spacing: 0.05em;
        text-transform: uppercase;
    }

    .live-badge {
        background-color: #ef4444;
        color: white;
        display: inline-flex;
        align-items: center;
        font-weight: bold;
        font-size: 0.7rem;
        padding: 0.15rem 0.4rem;
        border-radius: 999px;
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
        height: 105px;
        margin-top: 2px;
        margin-bottom: 22px;
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
        border-radius: 6px 6px 2px 2px;
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
        box-shadow:
            0 -4px 12px rgba(239, 68, 68, 0.16),
            0 0 7px rgba(239, 68, 68, 0.12);
        z-index: 2;
    }

    .spike-glow {
        position: absolute;
        top: -7px;
        left: -3px;
        right: -3px;
        bottom: 0;
        background: linear-gradient(
            180deg,
            rgba(239, 68, 68, 0.3) 0%,
            rgba(239, 68, 68, 0.08) 48%,
            transparent 82%
        );
        border-radius: 10px 10px 4px 4px;
        filter: blur(7px);
        pointer-events: none;
        animation: glowPulse 2.8s ease-in-out infinite alternate;
    }

    .spike-halo {
        position: absolute;
        top: -19px;
        left: -85%;
        right: -85%;
        height: 34px;
        background: radial-gradient(
            ellipse at center,
            rgba(239, 68, 68, 0.16) 0%,
            rgba(239, 68, 68, 0.05) 42%,
            transparent 72%
        );
        filter: blur(5px);
        pointer-events: none;
        animation: haloPulse 2.8s ease-in-out infinite alternate;
    }

    @keyframes glowPulse {
        0% {
            opacity: 0.32;
        }
        100% {
            opacity: 0.58;
        }
    }

    @keyframes haloPulse {
        0% {
            transform: scale(0.94);
            opacity: 0.28;
        }
        100% {
            transform: scale(1.04);
            opacity: 0.48;
        }
    }

    .x-label-container {
        height: 20px;
        margin-top: 8px;
        display: flex;
        align-items: center;
        justify-content: center;
        position: absolute;
        bottom: -21px;
    }

    .x-label {
        font-size: 0.6rem;
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
        background: var(--bg-surface-elevated);
        border: 1px solid rgba(51, 102, 255, 0.3);
        padding: 6px 10px;
        border-radius: 12px;
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
        color: var(--text-main);
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
        gap: 0.65rem;
    }

    .breakdown-card {
        background: var(--bg-surface);
        border: 1px solid var(--border-color);
        border-radius: 16px;
        padding: 0.7rem;
        min-width: 0;
    }

    .breakdown-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 0.45rem;
        margin-bottom: 0.45rem;
        padding-bottom: 0.4rem;
        border-bottom: 1px solid var(--border-color);
    }

    .breakdown-title-section {
        display: flex;
        align-items: center;
        gap: 0.4rem;
    }

    .reset-button {
        background: var(--bg-surface-elevated);
        border: 1px solid var(--border-color);
        color: var(--text-muted);
        border-radius: 8px;
        padding: 5px;
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
        font-size: 1rem;
        z-index: 2;
        width: 20px;
        height: 20px;
        display: flex;
        align-items: center;
        justify-content: center;
    }

    .breakdown-title {
        font-size: 0.82rem;
        font-weight: 700;
        letter-spacing: -0.01em;
    }

    .breakdown-list {
        display: flex;
        flex-direction: column;
        gap: 0.35rem;
        max-height: 184px;
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
        padding: 0.4rem 0.55rem;
        background: var(--hover-bg);
        border: none;
        border-radius: 10px;
        cursor: pointer;
        transition: all 0.2s ease;
        min-height: 34px;
        overflow: hidden;
        color: var(--text-color);
        text-align: left;
        gap: 0.5rem;
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
        height: 3px;
        background: var(--accent-primary);
        border-radius: 0 999px 999px 0;
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
        font-size: 0.82rem;
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
        padding: 0.08rem 0.4rem;
        border-radius: 999px;
        font-size: 0.72rem;
        z-index: 2;
    }

    :global(body.dark-mode) .breakdown-count {
        background: rgba(255, 255, 255, 0.15);
    }

    @media (min-width: 1120px) {
        .event-counters {
            display: grid;
            grid-template-columns: minmax(0, 1.45fr) minmax(520px, 1fr);
            grid-template-areas:
                "summary summary"
                "activity breakdown";
            align-items: stretch;
        }

        .top-row {
            grid-area: summary;
        }

        .activity-chart-section {
            grid-area: activity;
        }

        .incident-breakdown-grid {
            grid-area: breakdown;
        }
    }

    @media (max-width: 768px) {
        .top-row {
            flex-direction: column;
            gap: 0.55rem;
        }
        .stats-grid {
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 0.4rem;
        }
        .stat-card {
            padding: 0.5rem 0.55rem;
            grid-template-columns: 22px minmax(0, 1fr);
            column-gap: 0.35rem;
            min-height: 52px;
        }
        .event-counters {
            padding: 0.75rem;
            border-radius: 0 0 16px 16px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.2);
        }
        .time-period-section {
            flex-direction: row;
            justify-content: space-between;
            padding: 0.5rem;
            align-items: center;
            border-radius: 14px;
        }
        .time-buttons {
            display: flex;
            flex-wrap: wrap;
            justify-content: center;
            width: auto;
            gap: 0.25rem;
        }
        .time-button {
            padding: 0.35rem 0.6rem;
            font-size: 0.72rem;
        }
        .incident-breakdown-grid {
            grid-template-columns: 1fr;
        }
        .breakdown-list {
            max-height: 190px;
        }
        .breakdown-item {
            min-height: 34px;
            padding: 0.4rem 0.55rem;
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
            padding: 0.65rem;
            gap: 0.6rem;
            border-radius: 0 0 14px 14px;
            margin-bottom: 0.75rem;
        }
        .stats-grid {
            grid-template-columns: repeat(2, 1fr);
            gap: 0.4rem;
        }
        .stat-card {
            padding: 0.5rem 0.6rem;
            min-height: 52px;
            border-radius: 11px;
        }
        .stat-value {
            font-size: 1.2rem;
        }
        .stat-icon {
            font-size: 1rem;
        }
        .stat-label {
            font-size: 0.62rem;
        }
        .time-period-section {
            flex-direction: column;
            padding: 0.5rem;
            border-radius: 12px;
        }
        .section-label {
            font-size: 0.7rem;
        }
        .time-button {
            flex: 1 1 0;
            min-width: 0;
            padding: 0.35rem 0.25rem;
            font-size: 0.68rem;
        }
        .time-buttons {
            flex-wrap: nowrap;
            width: 100%;
        }
        .activity-chart-section {
            padding: 0.65rem;
            border-radius: 12px;
        }
        .section-title {
            font-size: 0.9rem;
        }
        .breakdown-card {
            padding: 0.65rem;
            border-radius: 12px;
            overflow: hidden;
        }
        .breakdown-list {
            max-height: 180px;
        }
        .breakdown-item {
            padding: 0.4rem 0.5rem;
            min-height: 34px;
        }

        @media (max-width: 360px) {
            .event-counters {
                padding: 0.55rem;
                gap: 0.5rem;
                border-radius: 0 0 12px 12px;
            }
            .stats-grid {
                gap: 0.3rem;
            }
            .stat-card {
                padding: 0.45rem 0.5rem;
                min-height: 48px;
            }
            .stat-value {
                font-size: 1.1rem;
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
            .breakdown-list {
                max-height: 165px;
            }
            .breakdown-item {
                padding: 0.35rem 0.45rem;
                min-height: 32px;
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
