<script>
  import { onMount, onDestroy } from "svelte";
  import { fade, slide } from "svelte/transition";

  // Import components
  import Header from "./components/Header.svelte";
  import HeadlineTicker from "./components/HeadlineTicker.svelte";
  import SkeletonCard from "./components/SkeletonCard.svelte";
  import PostCard from "./components/PostCard.svelte";
  import PostTable from "./components/PostTable.svelte";
  import ToastContainer from "./components/ToastContainer.svelte";
  import ViewToggle from "./components/ViewToggle.svelte";
  import SourceTabs from "./components/SourceTabs.svelte";
  import StatsPanel from "./components/StatsPanel.svelte";
  import MapTab from "./components/MapTab.svelte";

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

  // State variables
  let posts = [];
  let loading = true;
  let darkMode = true;
  let currentUsername = "";
  let lastToggleTime = 0;
  let postsPerPage = 15;
  let currentPage = 1;
  let loadingMore = false;
  let allPostsLoaded = false;
  let scrollContainer;
  let lastCursor = null;
  let selectedTypes = new Set();
  let selectedLocations = new Set();
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
  let historicalCurrentHourAverage = 0;

  // Data Source Management
  let activeSource = "all"; // 'all', 'CHP', 'SDPD', 'SDFD'

  function setSourceFilter(source) {
    if (activeSource === source) return;
    activeSource = source;
    currentPage = 1;
    // Reset other filters as they might not apply
    // selectedTypes = new Set();
    // selectedLocations = new Set();
    fetchIncidents();
    fetchIncidentStats();
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
    // Don't destroy chart here to prevent flashing
    // statsCache = {}; // Removed to preserve cache
    fetchIncidentStats();
  }

  function filterByType(type) {
    if (selectedTypes.has(type)) {
      selectedTypes.delete(type);
    } else {
      selectedTypes.add(type);
    }
    selectedTypes = new Set(selectedTypes); // Trigger reactivity
    currentPage = 1;
    fetchIncidents();
  }

  function filterByLocation(location) {
    if (selectedLocations.has(location)) {
      selectedLocations.delete(location);
    } else {
      selectedLocations.add(location);
    }
    selectedLocations = new Set(selectedLocations); // Trigger reactivity
    currentPage = 1;
    fetchIncidents();
  }

  function resetTypeFilters() {
    selectedTypes = new Set();
    currentPage = 1;
    fetchIncidents();
  }

  function resetLocationFilters() {
    selectedLocations = new Set();
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
      if (selectedTypes.size > 0) {
        for (const type of selectedTypes) {
          url += `&type=${encodeURIComponent(type)}`;
        }
      }
      if (selectedLocations.size > 0) {
        for (const loc of selectedLocations) {
          url += `&location=${encodeURIComponent(loc)}`;
        }
      }
      if (showActiveOnly) {
        url += `&active_only=true`;
      }
      if (activeSource && activeSource !== "all" && activeSource !== "map") {
        url += `&source=${encodeURIComponent(activeSource)}`;
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
          !incident.timestamp
          // Removed map_filename requirement to support sources without maps
          // || !incident.map_filename
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
        details: Array.isArray(incident.Details) ? incident.Details : [],
        timestamp: incident.timestamp,
        time: formatTimestamp(incident.timestamp),
        description: incident.description || "No description available",
        showFullDescription: false,
        location: incident.location || "Unknown location",
        neighborhood: incident.neighborhood || "",
        latitude: incident.latitude ?? null,
        longitude: incident.longitude ?? null,
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

    // Sort by timestamp (newest first) after merging to ensure correct order
    posts = [...posts, ...filteredPosts].sort((a, b) => {
      const timeA = new Date(a.timestamp).getTime();
      const timeB = new Date(b.timestamp).getTime();
      if (timeB !== timeA) return timeB - timeA;
      // Tie-breaker: use ID if timestamps are identical
      return b.id.localeCompare(a.id);
    });

    if (incidents.length > 0) {
      const lastIncident = incidents[incidents.length - 1];
      lastCursor = `${lastIncident.timestamp}|${lastIncident.incident_no}`;
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
      if (activeSource && activeSource !== "all" && activeSource !== "map") {
        url += `&source=${encodeURIComponent(activeSource)}`;
      }

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

        incidentsByType = Object.fromEntries(
          Object.entries(cachedStats.incidentsByType).sort(
            ([, a], [, b]) => b - a,
          ),
        );
        topLocations = Object.fromEntries(
          Object.entries(cachedStats.topLocations).sort(
            ([, a], [, b]) => b - a,
          ),
        );
        // Important: Create new array reference for caching to trigger Svelte reactivity
        hourlyData = [...(cachedStats.hourlyData || [])];
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
      hourlyData = (stats.hourlyData || []).map(Number);
      historicalCurrentHourAverage = stats.historicalCurrentHourAverage || 0;

      incidentsByType = Object.fromEntries(
        Object.entries(stats.incidentsByType).sort(([, a], [, b]) => b - a),
      );
      topLocations = Object.fromEntries(
        Object.entries(stats.topLocations).sort(([, a], [, b]) => b - a),
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

  async function submitComment(postId, commentContent = null) {
    const post = posts.find((p) => p.id === postId);
    const commentText =
      commentContent !== null ? commentContent : post?.newComment;

    if (!post || !commentText || commentText.trim() === "") return;

    const userComments = post.comments.filter(
      (c) => c.username === currentUsername,
    );
    if (userComments.length >= 2) {
      addToast("You can only leave 2 comments per post.", "warning");
      return;
    }

    const newCommentObj = {
      username: currentUsername,
      comment: commentText.trim(),
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
    if (activeSource === "map") return;
    touchStartX = e.touches[0].clientX;
    touchStartY = e.touches[0].clientY;
    pullStartY = e.touches[0].clientY;
    swipeInProgress = true;
    isPulling = false;
  }

  function handleTouchMove(e) {
    if (activeSource === "map") return;
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
    if (activeSource === "map") return;
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
    if (showEventCounters) {
      showEventCounters = false;
    }
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
    submitComment(event.detail.postId, event.detail.comment);
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

    const updateInterval = setInterval(() => {
      if (isOnline && !loading && !loadingMore) {
        checkForUpdates();
        fetchIncidentStats();
      }
    }, 30000);

    return () => {
      clearInterval(refreshInterval);
      window.removeEventListener("online", updateOnlineStatus);
      window.removeEventListener("offline", updateOnlineStatus);
      window.removeEventListener("scroll", debouncedHandleScroll);
      if (scrollContainer) {
        scrollContainer.removeEventListener("touchstart", handleTouchStart);
        scrollContainer.removeEventListener("touchmove", handleTouchMove);
        scrollContainer.removeEventListener("touchend", handleTouchEnd);
      }
    };
  });

  async function checkForUpdates() {
    try {
      let url = `/api/incidents?limit=${postsPerPage}`;
      if (selectedTypes.size > 0) {
        for (const type of selectedTypes) {
          url += `&type=${encodeURIComponent(type)}`;
        }
      }
      if (selectedLocations.size > 0) {
        for (const loc of selectedLocations) {
          url += `&location=${encodeURIComponent(loc)}`;
        }
      }
      if (showActiveOnly) {
        url += `&active_only=true`;
      }
      if (activeSource && activeSource !== "all" && activeSource !== "map") {
        url += `&source=${encodeURIComponent(activeSource)}`;
      }

      const res = await fetch(url);
      if (!res.ok) return;
      const newIncidents = await res.json();

      if (!Array.isArray(newIncidents)) return;

      const newProcessedPosts = newIncidents
        .filter((incident) => {
          if (!incident || typeof incident !== "object") return false;
          if (
            !incident.incident_no ||
            !incident.timestamp
            // Removed map_filename requirement to support sources without maps
            // || !incident.map_filename
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
          // If we haven't seen it, it's new.
          if (seenCompositeKeys.has(duplicateKey)) {
            return false;
          }
          return true;
        })
        .map((incident) => {
          // Add to seen keys so we don't re-add it later
          const key = `${incident.incident_no}-${incident.timestamp}-${incident.location}`;
          seenCompositeKeys.add(key);

          return {
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
          };
        });

      if (newProcessedPosts.length > 0) {
        posts = [...newProcessedPosts, ...posts];
        addToast(`${newProcessedPosts.length} new incident(s) found`, "info");
      }
    } catch (err) {
      console.error("Error checking for updates:", err);
    }
  }
</script>

<div class="container" bind:this={scrollContainer}>
  <HeadlineTicker events={posts.slice(0, 5)} />
  <Header
    {showEventCounters}
    {darkMode}
    {activeSource}
    on:toggleEventCounters={toggleEventCounters}
    on:toggleDarkMode={toggleDarkMode}
  />

  <SourceTabs
    {activeSource}
    on:changeSource={(e) => setSourceFilter(e.detail)}
  />

  <!-- Keep MapTab alive, just hide/show with CSS -->
  <div style={activeSource === "map" ? "" : "display:none"}>
    <MapTab />
  </div>

  {#if activeSource !== "map"}
    {#if showEventCounters}
      <StatsPanel
        {eventsToday}
        {eventsLastHour}
        {eventsActive}
        {totalIncidents}
        {timeFilter}
        {hourlyData}
        {historicalCurrentHourAverage}
        {incidentsByType}
        {topLocations}
        {selectedTypes}
        {selectedLocations}
        on:filterTime={(e) => setTimeFilter(e.detail)}
        on:filterType={(e) => filterByType(e.detail)}
        on:filterLocation={(e) => filterByLocation(e.detail)}
        on:resetTypeFilters={resetTypeFilters}
        on:resetLocationFilters={resetLocationFilters}
      />
    {/if}

    <ViewToggle
      {condensedView}
      {swipeIndicator}
      {swipeDirection}
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
        {expandedPostId}
        on:toggleExpand={handleTableToggleExpand}
        on:closeComments={handleTableCloseComments}
        on:like={handlePostLike}
        on:toggleComments={handlePostToggleComments}
        on:share={handlePostShare}
        on:toggleDescription={handlePostToggleDescription}
        on:submitComment={handlePostSubmitComment}
        on:goToMap={() => setSourceFilter("map")}
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
            on:goToMap={() => setSourceFilter("map")}
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
  {/if}

  <ToastContainer />

  <footer class="app-footer" in:fade={{ delay: 400, duration: 200 }}>
    <div class="footer-content">
      <span class="footer-decorator">[</span>
      <p>
        Created and Developed by <a
          href="https://github.com/DuffyAdams"
          target="_blank"
          rel="noopener noreferrer">Duffy Adams</a
        >
      </p>
      <span class="footer-decorator">]</span>
    </div>
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
    --bg-color: #eaeff5;
    --bg-base: #eaeff5;
    --bg-surface: #ffffff;
    --bg-surface-elevated: #f8fafc;
    --text-color: #1a202c;
    --text-main: #1a202c;
    --text-inverse: #ffffff;
    --card-bg: #ffffff;
    --shadow-color: rgba(0, 0, 0, 0.1);
    --border-color: #cbd5e0;
    --secondary-bg: #f1f5f9;
    --comment-bg: #e2e8f0;
    --text-muted: #4a5568;
    --text-dark: #2d3748;
    --text-darker: #1a202c;
    --hover-bg: #e2e8f0;
    --button-bg: #3182ce;
    --button-hover: #2c5282;
    --avatar-bg: #cbd5e0;
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
    --bg-base: #000000;
    --bg-surface: #0a0f18;
    --bg-surface-elevated: #111824;
    --text-color: #edf2f7;
    --text-main: #f8fafc;
    --text-inverse: #000000;
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
    padding: 2rem 0 1rem 0;
    color: var(--text-muted);
    font-size: 0.8rem;
    font-family: var(--font-mono);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    border-top: 1px dashed var(--border-color);
    display: flex;
    justify-content: center;
  }

  .footer-content {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    background: var(--bg-surface-elevated);
    border: 1px solid var(--border-color);
    padding: 0.5rem 1.5rem;
    border-radius: 2px;
    box-shadow: inset 0 0 0 1px rgba(51, 102, 255, 0.05);
  }

  :global(body.dark-mode) .footer-content {
    background: rgba(0, 0, 0, 0.5);
    border-color: rgba(51, 102, 255, 0.3);
  }

  .footer-decorator {
    color: var(--accent-primary, var(--primary-color));
    font-weight: bold;
    opacity: 0.7;
  }

  .app-footer p {
    margin: 0;
    display: flex;
    align-items: center;
    gap: 0.4rem;
  }

  .app-footer a {
    color: var(--accent-primary, var(--primary-color));
    text-decoration: none;
    font-weight: bold;
    position: relative;
    transition: all 0.2s ease;
  }

  .app-footer a::after {
    content: "";
    position: absolute;
    bottom: -2px;
    left: 0;
    width: 100%;
    height: 1px;
    background-color: var(--accent-primary, var(--primary-color));
    transform: scaleX(0);
    transform-origin: right;
    transition: transform 0.3s ease;
  }

  .app-footer a:hover {
    color: #fff;
    text-shadow: 0 0 8px rgba(51, 102, 255, 0.6);
  }

  .app-footer a:hover::after {
    transform: scaleX(1);
    transform-origin: left;
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
  }

  @media (max-width: 480px) {
    .container {
      padding: 0.25rem;
    }

    .feed,
    .loading-container {
      gap: 0.5rem;
    }

    .container {
      padding: 0.75rem;
    }

    @media (max-width: 360px) {
      .container {
        padding: 0.5rem;
      }
    }
  }
</style>
