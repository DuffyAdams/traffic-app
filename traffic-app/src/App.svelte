<script>
  import { onMount, onDestroy } from "svelte";
  import { fade, slide } from "svelte/transition";
  import {
    Chart as ChartJS,
    CategoryScale,
    TimeScale,
    LinearScale,
    PointElement,
    LineElement,
    Title,
    Tooltip,
    Legend,
    Filler,
    LineController,
  } from "chart.js";
  import "chartjs-adapter-date-fns";

  // Import components
  import Header from "./components/Header.svelte";
  import SkeletonCard from "./components/SkeletonCard.svelte";
  import PostCard from "./components/PostCard.svelte";
  import PostTable from "./components/PostTable.svelte";
  import ToastContainer from "./components/ToastContainer.svelte";
  import ViewToggle from "./components/ViewToggle.svelte";

  // Import utilities
  import {
    generateRandomUsername,
    debounce,
    retryWithBackoff,
    formatTimestamp,
    getIconForIncidentType,
    calculateNiceStepSize,
  } from "./utils/helpers.js";

  // Import stores
  import { addToast } from "./stores/appStore.js";

  // Register Chart.js components
  ChartJS.register(
    CategoryScale,
    TimeScale,
    LinearScale,
    PointElement,
    LineElement,
    Title,
    Tooltip,
    Legend,
    Filler,
    LineController,
  );

  // State variables
  let posts = [];
  let loading = true;
  let darkMode = false;
  let currentUsername = "";
  let lastToggleTime = 0;
  let postsPerPage = 30;
  let currentPage = 1;
  let loadingMore = false;
  let allPostsLoaded = false;
  let scrollContainer;
  let lastCursor = null;
  let selectedType = null;
  let condensedView = false;
  let expandedPostId = null;
  let eventsToday = 0;
  let eventsLastHour = 0;
  let eventsActive = 0;
  let totalIncidents = 0;
  let incidentsByType = {};
  let topLocations = {};
  let showEventCounters = false;
  let showActiveOnly = false;
  let timeFilter = "day";
  let seenCompositeKeys = new Set();
  let hourlyData = [];
  let chartCanvas;
  let chartInstance;

  const VW = 288,
    VH = 120;
  const PADX = 8,
    PADY = 8;

  $: xStep =
    hourlyData.length > 1 ? (VW - PADX * 2) / (hourlyData.length - 1) : 0;
  $: yMax = Math.max(1, ...hourlyData);
  $: y = (v) => PADY + (VH - PADY * 2) - (v / yMax) * (VH - PADY * 2);
  $: chartPath = hourlyData.length
    ? `M ${PADX} ${VH - PADY} ${hourlyData.map((v, i) => `L ${PADX + i * xStep} ${y(v)}`).join(" ")} L ${VW - PADX} ${VH - PADY} Z`
    : "";
  $: linePath = hourlyData.length
    ? hourlyData
        .map((v, i) => `${i ? "L" : "M"} ${PADX + i * xStep} ${y(v)}`)
        .join(" ")
    : "";

  $: currentTime = new Date();
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
              return date.toLocaleDateString("en-US", { month: "short" });
            });

  // Initialize Chart.js chart
  function initializeChart() {
    if (!chartCanvas || !hourlyData || hourlyData.length === 0) return;

    // Destroy existing chart if it exists
    if (chartInstance) {
      chartInstance.destroy();
    }

    const ctx = chartCanvas.getContext("2d");

    // Create gradient fill
    const gradient = ctx.createLinearGradient(0, 0, 0, 180);
    gradient.addColorStop(0, "rgba(99, 179, 237, 0.4)");
    gradient.addColorStop(1, "rgba(99, 179, 237, 0.02)");

    chartInstance = new ChartJS(ctx, {
      type: "line",
      data: {
        labels: chartLabels,
        datasets: [
          {
            data: hourlyData,
            fill: true,
            backgroundColor: gradient,
            borderColor: "#63b3ed",
            borderWidth: 2.5,
            tension: 0.4,
            pointRadius: 0,
            pointHoverRadius: 4,
            pointHoverBackgroundColor: "#63b3ed",
            pointHoverBorderColor: "#ffffff",
            pointHoverBorderWidth: 1.5,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        layout: {
          padding: {
            top: 15,
            bottom: 10,
            left: 5,
            right: 5,
          },
        },
        interaction: {
          intersect: false,
          mode: "index",
        },
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: "rgba(30, 58, 95, 0.95)",
            titleColor: "#ffffff",
            bodyColor: "#ffffff",
            titleFont: { size: 12, weight: "bold" },
            bodyFont: { size: 14, weight: "bold" },
            padding: 12,
            cornerRadius: 8,
            displayColors: false,
            callbacks: {
              title: (items) => items[0].label,
              label: (item) => `${item.raw} incidents`,
            },
          },
        },
        scales: {
          x: {
            display: true,
            grid: { display: false },
            border: { display: false },
            ticks: {
              color: "rgba(255, 255, 255, 0.5)",
              font: { size: 10, weight: "normal" },
              maxRotation: 0,
              autoSkip: true,
              maxTicksLimit:
                timeFilter === "day"
                  ? 8
                  : timeFilter === "week"
                    ? 7
                    : timeFilter === "month"
                      ? 10
                      : 12,
            },
          },
          y: {
            display: true,
            position: "right",
            grid: {
              color: "rgba(255, 255, 255, 0.06)",
            },
            border: { display: false },
            ticks: {
              color: "rgba(255, 255, 255, 0.5)",
              font: { size: 10, weight: "normal" },
              padding: 8,
              callback: function (value) {
                // Round by 10 for month/year, otherwise round normally
                if (timeFilter === "month" || timeFilter === "year") {
                  return Math.round(value / 10) * 10;
                }
                return Math.round(value);
              },
              stepSize:
                timeFilter === "month" || timeFilter === "year"
                  ? Math.max(
                      10,
                      Math.ceil(Math.max(...hourlyData) / 5 / 10) * 10,
                    )
                  : Math.max(1, Math.ceil(Math.max(...hourlyData) / 5)),
            },
            beginAtZero: true,
            suggestedMax: Math.max(...hourlyData) * 1.15 || 10,
          },
        },
        animation: {
          duration: 300,
          easing: "easeOutCubic",
        },
        transitions: {
          active: {
            animation: {
              duration: 200,
            },
          },
        },
      },
    });
  }

  // Update chart data
  function updateChart() {
    if (!chartInstance) {
      initializeChart();
      return;
    }

    if (!hourlyData || hourlyData.length === 0) return;

    chartInstance.data.labels = chartLabels;
    chartInstance.data.datasets[0].data = hourlyData;
    chartInstance.options.scales.y.ticks.stepSize =
      Math.ceil(Math.max(...hourlyData) / 5) || 1;
    chartInstance.options.scales.x.ticks.maxTicksLimit =
      timeFilter === "day"
        ? 8
        : timeFilter === "week"
          ? 7
          : timeFilter === "month"
            ? 10
            : 12;
    chartInstance.options.scales.y.suggestedMax =
      Math.max(...hourlyData) * 1.15 || 10;
    // Update stepSize based on time filter (round by 10 for month/year)
    chartInstance.options.scales.y.ticks.stepSize =
      timeFilter === "month" || timeFilter === "year"
        ? Math.max(10, Math.ceil(Math.max(...hourlyData) / 5 / 10) * 10)
        : Math.max(1, Math.ceil(Math.max(...hourlyData) / 5));
    // Use default update mode to keep animation
    chartInstance.update();
  }

  // Reactive statement to update chart when data changes
  $: if (
    hourlyData &&
    hourlyData.length > 0 &&
    chartCanvas &&
    showEventCounters
  ) {
    // Use setTimeout to ensure canvas is mounted
    setTimeout(() => updateChart(), 50);
  }

  // Cleanup chart when stats panel is closed
  $: if (!showEventCounters && chartInstance) {
    chartInstance.destroy();
    chartInstance = null;
  }

  // Network status
  let isOnline = true;
  let isFirstCheck = true;

  function updateOnlineStatus() {
    const previouslyOnline = isOnline;
    isOnline = navigator.onLine;
    if (!isOnline) {
      if (!isFirstCheck) {
        addToast("You are offline. Some features may not work.", "warning", 0);
      }
    } else {
      if (!isFirstCheck && !previouslyOnline) {
        addToast("Connection restored.", "success");
      }
      if (posts.length === 0) fetchIncidents();
      fetchIncidentStats();
    }
    isFirstCheck = false;
  }

  // Caching and cancellation
  let apiCache = new Map();
  let currentController = null;
  let statsCache = {};
  let statsController = null;
  let currentRequestId = 0;

  // Touch/swipe handling
  let touchStartX = 0;
  let touchEndX = 0;
  let touchStartY = 0;
  let touchEndY = 0;
  let swipeInProgress = false;
  let swipeIndicator = false;
  let swipeDirection = "";
  let swipeThreshold = 80;
  let verticalThreshold = 50;

  // Pull-to-refresh
  let pullStartY = 0;
  let pullDistance = 0;
  let isPulling = false;
  let pullThreshold = 100;
  let refreshing = false;

  function toggleDarkMode() {
    darkMode = !darkMode;
    document.body.classList.toggle("dark-mode", darkMode);
    localStorage.setItem("darkMode", darkMode.toString());
  }

  function toggleEventCounters() {
    showEventCounters = !showEventCounters;
  }

  function toggleActiveOnly() {
    showActiveOnly = !showActiveOnly;
    currentPage = 1;
    fetchIncidents();
  }

  function setTimeFilter(newFilter) {
    timeFilter = newFilter;
    statsCache = {};
    fetchIncidentStats();
  }

  function filterByType(type) {
    selectedType = selectedType === type ? null : type;
    currentPage = 1;
    fetchIncidents();
  }

  async function fetchIncidents() {
    const requestId = ++currentRequestId;

    if (currentController) {
      currentController.abort();
    }
    currentController = new AbortController();
    const signal = currentController.signal;

    try {
      if (currentPage === 1) {
        loading = true;
        posts = [];
        seenCompositeKeys.clear();
        lastCursor = null;
      } else {
        loadingMore = true;
      }

      let url = `/api/incidents?limit=${postsPerPage}`;
      if (currentPage > 1 && lastCursor) {
        url += `&cursor=${encodeURIComponent(lastCursor)}`;
      }
      if (selectedType) {
        url += `&type=${encodeURIComponent(selectedType)}`;
      }
      if (showActiveOnly) {
        url += `&active_only=true`;
      }

      const cacheKey = url;
      if (apiCache.has(cacheKey)) {
        const cachedData = apiCache.get(cacheKey);
        if (requestId === currentRequestId) {
          processIncidents(cachedData);
        }
        return;
      }

      const fetchFn = async () => {
        const res = await fetch(url, { signal });
        if (!res.ok) {
          throw new Error(
            `Failed to fetch incidents: ${res.status} ${res.statusText}`,
          );
        }
        return await res.json();
      };

      const incidents = await retryWithBackoff(fetchFn, 3, 1000);

      if (requestId !== currentRequestId) {
        return;
      }

      apiCache.set(cacheKey, incidents);
      processIncidents(incidents);
    } catch (err) {
      if (err.name !== "AbortError") {
        console.error("Error fetching incidents:", err);
        addToast(
          "Failed to load incidents. Please check your connection and try again.",
          "error",
        );
        if (currentPage === 1 && posts.length === 0) {
          posts = [
            {
              id: "error-fallback",
              compositeId: "error-fallback",
              timestamp: new Date().toISOString(),
              time: "Error",
              description: "Unable to load incidents at this time.",
              location: "N/A",
              image: "",
              likes: 0,
              comments: [],
              newComment: "",
              showComments: false,
              type: "Error",
              likeError: "",
              commentError: "",
              likeErrorAnimation: false,
              active: false,
            },
          ];
        }
      }
    } finally {
      if (requestId === currentRequestId) {
        if (currentPage === 1) {
          loading = false;
        } else {
          loadingMore = false;
        }
      }
      currentController = null;
    }
  }

  function processIncidents(incidents) {
    if (!Array.isArray(incidents)) {
      console.error("Invalid incidents data: expected array");
      addToast("Received invalid data from server", "error");
      return;
    }

    const newProcessedPosts = incidents
      .filter((incident) => {
        if (!incident || typeof incident !== "object") return false;
        if (
          !incident.incident_no ||
          !incident.timestamp ||
          !incident.map_filename
        ) {
          return false;
        }
        return true;
      })
      .map((incident) => {
        const date = incident.timestamp
          ? new Date(incident.timestamp).toLocaleDateString()
          : "";
        incident.compositeId = `${incident.incident_no}-${date}`;
        return incident;
      })
      .filter((incident) => {
        const duplicateKey = `${incident.incident_no}-${incident.timestamp}-${incident.location}`;
        if (seenCompositeKeys.has(duplicateKey)) {
          return false;
        }
        seenCompositeKeys.add(duplicateKey);
        return true;
      })
      .map((incident) => ({
        id: incident.incident_no,
        compositeId: incident.compositeId,
        timestamp: incident.timestamp,
        time: formatTimestamp(incident.timestamp),
        description: incident.description || "No description available",
        showFullDescription: false,
        location: incident.location || "Unknown location",
        image: `/maps/${incident.map_filename}`,
        likes: typeof incident.likes === "number" ? incident.likes : 0,
        comments: Array.isArray(incident.comments) ? incident.comments : [],
        newComment: "",
        showComments: false,
        type: incident.type || "Traffic Incident",
        likeError: "",
        commentError: "",
        likeErrorAnimation: false,
        active: Boolean(incident.active),
        liking: false,
      }));

    const filteredPosts = showActiveOnly
      ? newProcessedPosts.filter((p) => p.active)
      : newProcessedPosts;
    posts = [...posts, ...filteredPosts];

    if (incidents.length > 0) {
      lastCursor = incidents[incidents.length - 1].timestamp;
    }

    allPostsLoaded = incidents.length < postsPerPage;
  }

  function loadMorePosts() {
    if (loadingMore || allPostsLoaded) return;
    loadingMore = true;
    currentPage++;
    fetchIncidents();
  }

  const debouncedHandleScroll = debounce(() => {
    const scrollTop = window.scrollY || document.documentElement.scrollTop;
    const scrollHeight = document.documentElement.scrollHeight;
    const clientHeight = window.innerHeight;
    const scrollBottom = scrollHeight - scrollTop - clientHeight;

    if (scrollBottom < 600 && !loadingMore && !allPostsLoaded) {
      loadMorePosts();
    }
  }, 100);

  function forceLoadMore() {
    if (allPostsLoaded || loadingMore) return;
    currentPage++;
    fetchIncidents();
  }

  async function fetchIncidentStats() {
    if (statsController) {
      statsController.abort();
    }
    statsController = new AbortController();
    const signal = statsController.signal;

    try {
      let url = "/api/incident_stats?date_filter=" + timeFilter;

      const cacheKey = url;
      if (
        statsCache[cacheKey] &&
        Date.now() - statsCache[cacheKey].timestamp < 30000
      ) {
        const cachedStats = statsCache[cacheKey].data;
        eventsToday = cachedStats.eventsToday;
        eventsLastHour = cachedStats.eventsLastHour;
        eventsActive = cachedStats.eventsActive;
        totalIncidents = cachedStats.totalIncidents;

        const limit = 6;
        incidentsByType = Object.fromEntries(
          Object.entries(cachedStats.incidentsByType)
            .sort(([, a], [, b]) => b - a)
            .slice(0, limit),
        );
        topLocations = Object.fromEntries(
          Object.entries(cachedStats.topLocations)
            .sort(([, a], [, b]) => b - a)
            .slice(0, limit),
        );
        return;
      }

      const fetchFn = async () => {
        const res = await fetch(url, { signal });
        if (!res.ok) {
          throw new Error(
            `Failed to fetch incident stats: ${res.status} ${res.statusText}`,
          );
        }
        return await res.json();
      };

      const stats = await retryWithBackoff(fetchFn, 3, 1000);

      statsCache[cacheKey] = { data: stats, timestamp: Date.now() };

      eventsToday = stats.eventsToday;
      eventsLastHour = stats.eventsLastHour;
      eventsActive = stats.eventsActive;
      totalIncidents = stats.totalIncidents;
      hourlyData = stats.hourlyData || [];

      const limit = 6;
      incidentsByType = Object.fromEntries(
        Object.entries(stats.incidentsByType)
          .sort(([, a], [, b]) => b - a)
          .slice(0, limit),
      );
      topLocations = Object.fromEntries(
        Object.entries(stats.topLocations)
          .sort(([, a], [, b]) => b - a)
          .slice(0, limit),
      );
    } catch (err) {
      if (err.name !== "AbortError") {
        console.error("Error fetching incident stats:", err);
        addToast("Failed to load incident statistics.", "error");
      }
    } finally {
      statsController = null;
    }
  }

  async function likePost(postId) {
    const post = posts.find((p) => p.id === postId);
    if (!post || post.liking) return;

    posts = posts.map((p) => (p.id === postId ? { ...p, liking: true } : p));

    const originalLikes = post.likes;
    const wasLiked = post.likes > 0;

    posts = posts.map((p) =>
      p.id === postId
        ? {
            ...p,
            likes: wasLiked ? 0 : 1,
            likeError: "",
            likeErrorAnimation: false,
          }
        : p,
    );

    try {
      const method = wasLiked ? "DELETE" : "POST";
      const fetchFn = async () => {
        const res = await fetch(`/api/incidents/${postId}/like`, { method });
        if (!res.ok) {
          throw new Error(`Failed to ${wasLiked ? "unlike" : "like"} post`);
        }
        return await res.json();
      };

      const data = await retryWithBackoff(fetchFn, 2, 500);
      posts = posts.map((p) =>
        p.id === postId
          ? { ...p, likes: data.likes, likeError: "", liking: false }
          : p,
      );
    } catch (err) {
      console.error("Error updating like:", err);
      if (wasLiked) {
        posts = posts.map((p) =>
          p.id === postId ? { ...p, liking: false } : p,
        );
      } else {
        addToast("Failed to like post. Please try again.", "error");
        posts = posts.map((p) =>
          p.id === postId ? { ...p, likes: originalLikes, liking: false } : p,
        );
      }
    }
  }

  function toggleComments(postId) {
    const now = Date.now();
    if (now - lastToggleTime < 200) return;
    lastToggleTime = now;
    posts = posts.map((post) =>
      post.id === postId ? { ...post, showComments: !post.showComments } : post,
    );
  }

  function sharePost(post) {
    const text = `${post.description} - Location: ${post.location}. Check out more traffic incidents at San Diego Traffic Watch!`;
    const url = window.location.origin;

    if (navigator.share) {
      navigator.share({ title: "San Diego Traffic Watch", text, url });
    } else {
      const twitterUrl = `https://twitter.com/intent/tweet?text=${encodeURIComponent(text)}&url=${encodeURIComponent(url)}`;
      window.open(twitterUrl, "_blank");
    }
  }

  async function submitComment(postId) {
    const post = posts.find((p) => p.id === postId);
    if (!post || post.newComment.trim() === "") return;

    const userComments = post.comments.filter(
      (c) => c.username === currentUsername,
    );
    if (userComments.length >= 2) {
      addToast("You can only leave 2 comments per post.", "warning");
      return;
    }

    const newCommentObj = {
      username: currentUsername,
      comment: post.newComment.trim(),
      timestamp: new Date().toISOString(),
    };

    const originalComments = [...post.comments];
    const originalNewComment = post.newComment;

    const optimisticComment = { ...newCommentObj, id: `temp-${Date.now()}` };
    posts = posts.map((p) =>
      p.id === postId
        ? {
            ...p,
            comments: [...p.comments, optimisticComment],
            newComment: "",
            commentError: "",
          }
        : p,
    );

    try {
      const fetchFn = async () => {
        const res = await fetch(`/api/incidents/${postId}/comment`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(newCommentObj),
        });
        if (!res.ok) {
          throw new Error(`Failed to submit comment`);
        }
        return await res.json();
      };

      const data = await retryWithBackoff(fetchFn, 2, 500);
      posts = posts.map((p) =>
        p.id === postId
          ? { ...p, comments: data.comments, newComment: "", commentError: "" }
          : p,
      );
      addToast("Comment added successfully!", "success");
    } catch (err) {
      console.error("Error submitting comment:", err);
      addToast("Failed to submit comment. Please try again.", "error");
      posts = posts.map((p) =>
        p.id === postId
          ? {
              ...p,
              comments: originalComments,
              newComment: originalNewComment,
              commentError: "Failed to submit comment",
            }
          : p,
      );
    }
  }

  function toggleDescription(postId) {
    posts = posts.map((post) =>
      post.id === postId
        ? { ...post, showFullDescription: !post.showFullDescription }
        : post,
    );
  }

  function toggleExpand(postId) {
    expandedPostId = expandedPostId === postId ? null : postId;
  }

  function handleTouchStart(e) {
    touchStartX = e.touches[0].clientX;
    touchStartY = e.touches[0].clientY;
    pullStartY = e.touches[0].clientY;
    swipeInProgress = true;
    isPulling = false;
  }

  function handleTouchMove(e) {
    if (!swipeInProgress) return;

    touchEndX = e.touches[0].clientX;
    touchEndY = e.touches[0].clientY;

    const diffX = touchStartX - touchEndX;
    const diffY = touchEndY - touchStartY;

    if (diffY > 0 && window.scrollY === 0 && !isPulling) {
      isPulling = true;
      pullDistance = Math.min(diffY * 0.5, 120);
      e.preventDefault();
      return;
    }

    if (isPulling) {
      pullDistance = Math.min(diffY * 0.5, 120);
      e.preventDefault();
      return;
    }

    if (Math.abs(diffX) > 20 && Math.abs(diffY) < verticalThreshold) {
      swipeIndicator = true;
      swipeDirection = diffX > 0 ? "left" : "right";
      if (Math.abs(diffX) > 40) {
        e.preventDefault();
      }
    } else {
      swipeIndicator = false;
    }
  }

  function handleTouchEnd(e) {
    if (!swipeInProgress) return;

    if (isPulling && pullDistance >= pullThreshold && !refreshing) {
      refreshing = true;
      addToast("Refreshing...", "info");
      fetchIncidents();
      fetchIncidentStats();
      setTimeout(() => {
        refreshing = false;
        addToast("Refreshed!", "success");
      }, 1000);
    }

    const diffX = touchStartX - touchEndX;
    const diffY = Math.abs(touchStartY - touchEndY);

    if (Math.abs(diffX) > swipeThreshold && diffY < verticalThreshold) {
      if (diffX > 0) {
        if (!condensedView) condensedView = true;
        if (navigator.vibrate) navigator.vibrate(50);
      } else {
        if (condensedView) condensedView = false;
        if (navigator.vibrate) navigator.vibrate(50);
      }
    }

    swipeInProgress = false;
    swipeIndicator = false;
    isPulling = false;
    pullDistance = 0;
  }

  function toggleView() {
    condensedView = !condensedView;
  }

  // Event handlers for components
  function handlePostLike(event) {
    likePost(event.detail.postId);
  }

  function handlePostToggleComments(event) {
    toggleComments(event.detail.postId);
  }

  function handlePostShare(event) {
    sharePost(event.detail.post);
  }

  function handlePostToggleDescription(event) {
    toggleDescription(event.detail.postId);
  }

  function handlePostSubmitComment(event) {
    submitComment(event.detail.postId);
  }

  function handleTableToggleExpand(event) {
    toggleExpand(event.detail.postId);
  }

  function handleTableCloseComments(event) {
    const post = posts.find((p) => p.id === event.detail.postId);
    if (post && post.showComments) {
      posts = posts.map((p) =>
        p.id === event.detail.postId ? { ...p, showComments: false } : p,
      );
    }
  }

  onMount(() => {
    const prefersDark = window.matchMedia(
      "(prefers-color-scheme: dark)",
    ).matches;
    const storedMode = localStorage.getItem("darkMode");
    darkMode = storedMode ? storedMode === "true" : prefersDark;
    document.body.classList.toggle("dark-mode", darkMode);

    currentUsername =
      localStorage.getItem("username") || generateRandomUsername();
    if (!localStorage.getItem("username")) {
      localStorage.setItem("username", currentUsername);
    }

    window.addEventListener("online", updateOnlineStatus);
    window.addEventListener("offline", updateOnlineStatus);
    updateOnlineStatus();

    fetchIncidents();
    fetchIncidentStats();

    const refreshInterval = setInterval(() => {
      if (isOnline) {
        fetchIncidentStats();
        fetchIncidents();
      }
    }, 60000);

    window.addEventListener("scroll", debouncedHandleScroll);

    if (scrollContainer) {
      scrollContainer.addEventListener("touchstart", handleTouchStart, {
        passive: true,
      });
      scrollContainer.addEventListener("touchmove", handleTouchMove, {
        passive: false,
      });
      scrollContainer.addEventListener("touchend", handleTouchEnd, {
        passive: true,
      });
    }

    onDestroy(() => {
      clearInterval(refreshInterval);
      window.removeEventListener("online", updateOnlineStatus);
      window.removeEventListener("offline", updateOnlineStatus);
      window.removeEventListener("scroll", debouncedHandleScroll);
      if (scrollContainer) {
        scrollContainer.removeEventListener("touchstart", handleTouchStart);
        scrollContainer.removeEventListener("touchmove", handleTouchMove);
        scrollContainer.removeEventListener("touchend", handleTouchEnd);
      }
      if (chartInstance) {
        chartInstance.destroy();
      }
    });
  });
</script>

<div class="container" bind:this={scrollContainer}>
  <Header
    {darkMode}
    {showEventCounters}
    on:toggleDarkMode={toggleDarkMode}
    on:toggleEventCounters={toggleEventCounters}
  />

  <!-- Stats Panel (inline due to complexity) -->
  {#if showEventCounters}
    <div class="event-counters" transition:slide>
      <div class="top-row">
        <div class="stats-grid">
          <div class="stat-card">
            <div class="stat-icon">📅</div>
            <div class="stat-value">{eventsToday}</div>
            <div class="stat-label">Today</div>
          </div>
          <div class="stat-card">
            <div class="stat-icon">⏰</div>
            <div class="stat-value">{eventsLastHour}</div>
            <div class="stat-label">Last Hour</div>
          </div>
          <div class="stat-card">
            <div class="stat-icon">⚡</div>
            <div class="stat-value">{eventsActive}</div>
            <div class="stat-label">Active</div>
          </div>
          <div class="stat-card">
            <div class="stat-icon">📊</div>
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
        </div>
        <div class="chart-container">
          <canvas bind:this={chartCanvas}></canvas>
        </div>
      </div>

      <!-- Breakdowns -->
      <div class="incident-breakdown-grid">
        <div class="breakdown-card">
          <div class="breakdown-header">
            <span class="breakdown-icon">📋</span>
            <span class="breakdown-title">By Type</span>
          </div>
          <div class="breakdown-list">
            {#each Object.entries(incidentsByType) as [type, count]}
              <button
                class="breakdown-item"
                on:click={() => filterByType(type)}
              >
                <div
                  class="breakdown-item-bar"
                  style="width: {(count /
                    Math.max(...Object.values(incidentsByType))) *
                    100}%"
                ></div>
                <span class="breakdown-item-icon"
                  >{getIconForIncidentType(type)}</span
                >
                <span
                  class="breakdown-item-label"
                  class:filter-active={selectedType === type}>{type}</span
                >
                <span class="breakdown-item-count">{count}</span>
              </button>
            {/each}
          </div>
        </div>
        <div class="breakdown-card">
          <div class="breakdown-header">
            <span class="breakdown-icon">📍</span>
            <span class="breakdown-title">Top Locations</span>
          </div>
          <div class="breakdown-list">
            {#each Object.entries(topLocations) as [location, count]}
              <div class="breakdown-item">
                <div
                  class="breakdown-item-bar"
                  style="width: {(count /
                    Math.max(...Object.values(topLocations))) *
                    100}%"
                ></div>
                <span class="breakdown-item-label">{location}</span>
                <span class="breakdown-item-count">{count}</span>
              </div>
            {/each}
          </div>
        </div>
      </div>

      <button
        class="filter-toggle"
        class:filter-active={showActiveOnly}
        on:click={toggleActiveOnly}
      >
        {showActiveOnly ? "⚡ Active Only" : "📋 Show All"}
      </button>
    </div>
  {/if}

  <ViewToggle
    {condensedView}
    {swipeIndicator}
    {swipeDirection}
    {isPulling}
    {pullDistance}
    {refreshing}
    on:toggle={toggleView}
  />

  {#if loading && posts.length === 0}
    <div class="loading-container" in:fade={{ duration: 150 }}>
      {#each Array(6) as _}
        <SkeletonCard />
      {/each}
    </div>
  {:else if posts.length === 0}
    <div class="empty-state" in:fade={{ duration: 150 }}>
      <div class="empty-icon">🔍</div>
      <p>No incidents to display at the moment.</p>
      <p>Check back soon for updates.</p>
    </div>
  {:else if condensedView}
    <PostTable
      {posts}
      {postsPerPage}
      {expandedPostId}
      on:toggleExpand={handleTableToggleExpand}
      on:closeComments={handleTableCloseComments}
      on:like={handlePostLike}
      on:toggleComments={handlePostToggleComments}
      on:share={handlePostShare}
      on:toggleDescription={handlePostToggleDescription}
      on:submitComment={handlePostSubmitComment}
    />
  {:else}
    <div class="feed" in:fade={{ duration: 200 }}>
      {#each posts as post, i (post.compositeId)}
        <PostCard
          {post}
          index={i}
          {postsPerPage}
          on:like={handlePostLike}
          on:toggleComments={handlePostToggleComments}
          on:share={handlePostShare}
          on:toggleDescription={handlePostToggleDescription}
          on:submitComment={handlePostSubmitComment}
        />
      {/each}
    </div>

    {#if !allPostsLoaded && posts.length > 0 && posts.length >= postsPerPage}
      <div
        class="scroll-indicator"
        in:fade={{ duration: 150 }}
        on:click={forceLoadMore}
        role="button"
        tabindex="0"
        on:keydown={(e) => e.key === "Enter" && forceLoadMore()}
      >
        <div class="scroll-dots">
          <span class="dot"></span>
          <span class="dot"></span>
          <span class="dot"></span>
        </div>
        <p>More incidents available</p>
      </div>
    {/if}
  {/if}

  <ToastContainer />

  <footer class="app-footer" in:fade={{ delay: 400, duration: 200 }}>
    <p>
      Created and Developed by <a
        href="https://github.com/DuffyAdams"
        target="_blank"
        rel="noopener noreferrer">Duffy Adams</a
      >
    </p>
  </footer>
</div>

<style>
  :global(html),
  :global(body) {
    margin: 0;
    padding: 0;
    width: 100%;
    max-width: 100%;
    position: relative;
  }

  :global(body) {
    font-family:
      "Inter",
      "Segoe UI",
      system-ui,
      -apple-system,
      sans-serif;
    transition:
      background-color 0.3s,
      color 0.3s;
    background-color: var(--bg-color);
    color: var(--text-color);
  }

  :global(body:not(.dark-mode)) {
    --primary-color: #3182ce;
    --primary-dark: #2c5282;
    --primary-light: #4299e1;
    --primary-lightest: #ebf8ff;
    --accent-color: #f6ad55;
    --accent-dark: #dd6b20;
    --bg-color: #f9fafb;
    --text-color: #1a202c;
    --card-bg: white;
    --shadow-color: rgba(0, 0, 0, 0.06);
    --border-color: #e2e8f0;
    --secondary-bg: #f8fafc;
    --comment-bg: #f1f5f9;
    --text-muted: #718096;
    --text-dark: #4a5568;
    --text-darker: #2d3748;
    --hover-bg: #f7fafc;
    --button-bg: #3182ce;
    --button-hover: #2c5282;
    --avatar-bg: #e2e8f0;
    --error-bg: #fff5f5;
    --error-color: #e53e3e;
    --success-color: #38a169;
  }

  :global(body.dark-mode) {
    --primary-color: #4299e1;
    --primary-dark: #3182ce;
    --primary-light: #63b3ed;
    --primary-lightest: #1a365d;
    --accent-color: #ed8936;
    --accent-dark: #c05621;
    --bg-color: #171923;
    --text-color: #edf2f7;
    --card-bg: #2d3748;
    --shadow-color: rgba(0, 0, 0, 0.3);
    --border-color: #4a5568;
    --secondary-bg: #2d3748;
    --comment-bg: #1e2634;
    --text-muted: #a0aec0;
    --text-dark: #cbd5e0;
    --text-darker: #e2e8f0;
    --hover-bg: #4a5568;
    --button-bg: #4299e1;
    --button-hover: #3182ce;
    --avatar-bg: #4a5568;
    --error-bg: #2d1515;
    --error-color: #fc8181;
    --success-color: #48bb78;
  }

  .container {
    max-width: 1280px;
    margin: 0 auto;
    padding: 1rem;
    box-sizing: border-box;
    width: 100%;
    position: relative;
  }

  .loading-container {
    display: flex;
    flex-wrap: wrap;
    gap: 1.5rem;
    justify-content: center;
    width: 100%;
    box-sizing: border-box;
  }

  .feed {
    display: flex;
    flex-wrap: wrap;
    gap: 1.5rem;
    justify-content: center;
    width: 100%;
    box-sizing: border-box;
  }

  .empty-state {
    text-align: center;
    padding: 3rem 0;
    color: var(--text-muted);
  }

  .empty-icon {
    font-size: 3.5rem;
    margin-bottom: 1.5rem;
    opacity: 0.8;
  }

  /* Stats Panel Styles - Professional Redesign */
  .event-counters {
    display: flex;
    flex-direction: column;
    gap: 1.25rem;
    margin-bottom: 1.5rem;
    padding: 1.5rem;
    background: linear-gradient(135deg, #1e3a5f 0%, #0d2137 100%);
    border-radius: 20px;
    color: white;
    box-shadow:
      0 10px 40px rgba(0, 0, 0, 0.3),
      inset 0 1px 0 rgba(255, 255, 255, 0.1);
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
    background: linear-gradient(
      135deg,
      rgba(255, 255, 255, 0.12) 0%,
      rgba(255, 255, 255, 0.05) 100%
    );
    backdrop-filter: blur(10px);
    border: 1px solid rgba(255, 255, 255, 0.15);
    border-radius: 16px;
    text-align: center;
    padding: 1rem 0.75rem;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    min-height: 90px;
    transition: all 0.3s ease;
  }

  .stat-card:hover {
    background: linear-gradient(
      135deg,
      rgba(255, 255, 255, 0.18) 0%,
      rgba(255, 255, 255, 0.08) 100%
    );
    transform: translateY(-2px);
    box-shadow: 0 8px 25px rgba(0, 0, 0, 0.2);
  }

  .stat-icon {
    font-size: 1.5rem;
    margin-bottom: 0.5rem;
    filter: drop-shadow(0 2px 4px rgba(0, 0, 0, 0.2));
  }

  .stat-value {
    font-size: 1.75rem;
    font-weight: 800;
    letter-spacing: -0.02em;
    background: linear-gradient(180deg, #ffffff 0%, #b8d4f0 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
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
    padding: 1rem 1.25rem;
    background: linear-gradient(
      135deg,
      rgba(255, 255, 255, 0.12) 0%,
      rgba(255, 255, 255, 0.05) 100%
    );
    backdrop-filter: blur(10px);
    border: 1px solid rgba(255, 255, 255, 0.15);
    border-radius: 16px;
    min-width: 180px;
    gap: 0.75rem;
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
    background: rgba(0, 0, 0, 0.2);
    padding: 0.3rem;
    border-radius: 24px;
  }

  .time-button {
    padding: 0.5rem 1rem;
    background: transparent;
    border: none;
    border-radius: 20px;
    color: rgba(255, 255, 255, 0.7);
    font-size: 0.8rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.25s ease;
  }

  .time-button:hover {
    color: white;
    background: rgba(255, 255, 255, 0.1);
  }

  .time-button.active {
    background: white;
    color: #1e3a5f;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
  }

  .activity-chart-section {
    padding: 1rem 1.25rem;
    background: linear-gradient(
      135deg,
      rgba(255, 255, 255, 0.08) 0%,
      rgba(255, 255, 255, 0.02) 100%
    );
    backdrop-filter: blur(10px);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 16px;
  }

  .activity-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.75rem;
  }

  .section-title {
    font-size: 1rem;
    font-weight: 700;
    letter-spacing: -0.01em;
  }

  .chart-container {
    position: relative;
    width: 100%;
    height: 180px;
  }

  .chart-container canvas {
    width: 100% !important;
    height: 100% !important;
  }

  .incident-breakdown-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 1rem;
  }

  .breakdown-card {
    background: linear-gradient(
      135deg,
      rgba(255, 255, 255, 0.1) 0%,
      rgba(255, 255, 255, 0.03) 100%
    );
    backdrop-filter: blur(10px);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 16px;
    padding: 1rem;
  }

  .breakdown-header {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    margin-bottom: 0.75rem;
    padding-bottom: 0.6rem;
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  }

  .breakdown-icon {
    font-size: 1.1rem;
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
  }

  .breakdown-item {
    display: flex;
    align-items: center;
    position: relative;
    padding: 0.6rem 0.75rem;
    background: rgba(255, 255, 255, 0.04);
    border: none;
    border-radius: 10px;
    cursor: pointer;
    transition: all 0.2s ease;
    min-height: 40px;
    overflow: hidden;
    color: white;
    text-align: left;
  }

  .breakdown-item:hover {
    background: rgba(255, 255, 255, 0.1);
    transform: translateX(2px);
  }

  .breakdown-item-bar {
    position: absolute;
    left: 0;
    top: 0;
    height: 100%;
    background: linear-gradient(
      90deg,
      rgba(99, 179, 237, 0.3) 0%,
      rgba(99, 179, 237, 0.05) 100%
    );
    border-radius: inherit;
    z-index: 0;
    transition: width 0.5s ease;
  }

  .breakdown-item-icon {
    z-index: 1;
    font-size: 1rem;
    flex-shrink: 0;
  }

  .breakdown-item-label {
    flex: 1;
    z-index: 1;
    font-size: 0.8rem;
    font-weight: 500;
    margin-left: 0.6rem;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .breakdown-item-count {
    z-index: 1;
    font-size: 0.75rem;
    font-weight: 700;
    background: rgba(255, 255, 255, 0.15);
    padding: 0.25rem 0.6rem;
    border-radius: 8px;
    margin-left: 0.5rem;
    flex-shrink: 0;
  }

  .filter-toggle {
    margin-top: 0.5rem;
    padding: 0.6rem 1.25rem;
    background: rgba(255, 255, 255, 0.1);
    border: 1px solid rgba(255, 255, 255, 0.15);
    border-radius: 24px;
    color: white;
    font-size: 0.85rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.25s ease;
    align-self: center;
  }

  .filter-toggle:hover {
    background: rgba(255, 255, 255, 0.2);
    transform: translateY(-1px);
  }

  .filter-toggle.filter-active {
    background: #e53e3e;
    border-color: #e53e3e;
    box-shadow: 0 4px 15px rgba(229, 62, 62, 0.4);
  }

  .filter-active {
    color: #fbd38d !important;
    font-weight: 700;
  }

  /* Scroll indicator */
  .scroll-indicator {
    width: 100%;
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 1rem 0;
    color: var(--text-muted);
    font-size: 0.9rem;
    opacity: 0.8;
    cursor: pointer;
    transition: all 0.2s ease;
    margin: 1rem 0;
  }

  .scroll-indicator:hover {
    opacity: 1;
    transform: translateY(-2px);
  }

  .scroll-dots {
    display: flex;
    gap: 3px;
    margin-bottom: 6px;
  }

  .dot {
    width: 6px;
    height: 6px;
    background-color: var(--text-muted);
    border-radius: 50%;
    animation: bounce 1.4s infinite ease-in-out both;
  }

  .dot:nth-child(1) {
    animation-delay: -0.32s;
  }
  .dot:nth-child(2) {
    animation-delay: -0.16s;
  }

  @keyframes bounce {
    0%,
    80%,
    100% {
      transform: translateY(0);
    }
    40% {
      transform: translateY(-8px);
    }
  }

  /* Footer */
  .app-footer {
    text-align: center;
    margin-top: 2rem;
    padding: 1rem 0;
    color: var(--text-muted);
    font-size: 0.9rem;
    border-top: 1px solid var(--border-color);
  }

  .app-footer a {
    color: var(--primary-color);
    text-decoration: none;
    font-weight: 600;
  }

  .app-footer a:hover {
    text-decoration: underline;
  }

  /* Mobile responsive */
  @media (max-width: 768px) {
    .container {
      padding: 0.5rem;
    }
    .feed,
    .loading-container {
      gap: 1rem;
      padding: 0;
    }
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
      border-radius: 16px;
      box-shadow: 0 4px 20px rgba(0, 0, 0, 0.2);
    }
    .time-period-section {
      padding: 0.75rem;
      align-items: center;
    }
    .time-buttons {
      display: flex;
      flex-wrap: nowrap;
      justify-content: center;
      width: auto;
    }
    .time-button {
      padding: 0.45rem 0.7rem;
      font-size: 0.75rem;
    }
    .incident-breakdown-grid {
      grid-template-columns: 1fr;
    }
  }

  @media (max-width: 480px) {
    .container {
      padding: 0.25rem;
    }
    .event-counters {
      padding: 1rem;
      gap: 0.75rem;
      border-radius: 16px;
      margin-bottom: 0.75rem;
    }
    .feed,
    .loading-container {
      gap: 0.5rem;
    }
    .stats-grid {
      grid-template-columns: repeat(2, 1fr);
      gap: 0.4rem;
    }
    .container {
      padding: 0.75rem;
    }
    .stat-card {
      padding: 0.6rem 0.4rem;
      min-height: 70px;
      border-radius: 12px;
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
      border-radius: 12px;
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
      border-radius: 12px;
    }
    .chart-container {
      height: 150px;
    }
    .section-title {
      font-size: 0.9rem;
    }
    .breakdown-card {
      padding: 0.75rem;
      border-radius: 12px;
    }
    .breakdown-title {
      font-size: 0.8rem;
    }
    .breakdown-item {
      padding: 0.5rem 0.6rem;
      min-height: 36px;
    }
    .breakdown-item-name {
      font-size: 0.75rem;
    }
    .breakdown-item-count {
      font-size: 0.7rem;
    }
  }

  @media (max-width: 360px) {
    .container {
      padding: 0.5rem;
    }
    .event-counters {
      padding: 0.75rem;
      gap: 0.5rem;
      border-radius: 12px;
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
  }
</style>
