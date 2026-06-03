<script>
  import { onMount } from "svelte";
  import { fade, slide } from "svelte/transition";

  // Import components
  import Header from "./components/Header.svelte";
  import HeadlineTicker from "./components/HeadlineTicker.svelte";
  import SkeletonCard from "./components/SkeletonCard.svelte";
  import PostCard from "./components/PostCard.svelte";
  import ToastContainer from "./components/ToastContainer.svelte";
  import ViewToggle from "./components/ViewToggle.svelte";
  import SourceTabs from "./components/SourceTabs.svelte";
  import SearchBar from "./components/SearchBar.svelte";

  // Import utilities
  import {
    generateRandomUsername,
    debounce,
    retryWithBackoff,
    formatTimestamp,
    buildIncidentImagePath,
  } from "./utils/helpers.js";

  // Import stores
  import { addToast } from "./stores/appStore.js";
  import { compareText, formatDateKey, t } from "./utils/i18n.js";

  /**
   * @typedef {Object} PostComment
   * @property {string} [id]
   * @property {string} username
   * @property {string} comment
   * @property {string} timestamp
   */

  /**
   * @typedef {Object} Incident
   * @property {string} [incident_no]
   * @property {string} [timestamp]
   * @property {string[]} [Details]
   * @property {string} [description]
   * @property {string} [location]
   * @property {string} [neighborhood]
   * @property {number | null} [latitude]
   * @property {number | null} [longitude]
   * @property {string} [map_filename]
   * @property {number} [likes]
   * @property {PostComment[]} [comments]
   * @property {string} [type]
   * @property {boolean} [active]
   * @property {number | null} [severity]
   * @property {boolean} [liked_by_user]
   * @property {string} [compositeId]
   */

  /**
   * @typedef {Object} Post
   * @property {string} id
   * @property {string} compositeId
   * @property {string[]} details
   * @property {string} timestamp
   * @property {string} time
   * @property {string} description
   * @property {boolean} showFullDescription
   * @property {string} location
   * @property {string} neighborhood
   * @property {number | null} latitude
   * @property {number | null} longitude
   * @property {string} image
   * @property {number} likes
   * @property {PostComment[]} comments
   * @property {string} newComment
   * @property {boolean} showComments
   * @property {string} type
   * @property {string} likeError
   * @property {string} commentError
   * @property {boolean} likeErrorAnimation
   * @property {boolean} active
   * @property {boolean} liking
   * @property {number | null} severity
   * @property {boolean} likedByUser
   */

  /**
   * @typedef {Object} IncidentStatsResponse
   * @property {number} eventsToday
   * @property {number} eventsLastHour
   * @property {number} eventsActive
   * @property {number} totalIncidents
   * @property {Record<string, number>} incidentsByType
   * @property {Record<string, number>} topLocations
   * @property {number[]} [hourlyData]
   * @property {number} [historicalCurrentHourAverage]
   * @property {string} [generatedAt]
   */

  /**
   * @typedef {Object} StatsCacheEntry
   * @property {IncidentStatsResponse} data
   * @property {number} timestamp
   */

  /**
   * @typedef {Object} ApiCacheEntry
   * @property {Incident[]} data
   * @property {number} timestamp
   */

  /**
   * @typedef {Object} LikeResponse
   * @property {number} likes
   * @property {boolean} liked_by_user
   */

  /**
   * @typedef {Object} CommentResponse
   * @property {PostComment[]} comments
   */

  /** @typedef {CustomEvent<{ postId: string }>} PostIdEvent */
  /** @typedef {CustomEvent<{ post: Post }>} PostShareEvent */
  /** @typedef {CustomEvent<{ postId: string, comment: string }>} PostCommentEvent */
  /** @typedef {CustomEvent<string>} StringDetailEvent */

  // State variables
  /** @type {Post[]} */
  let posts = [];
  let loading = true;
  let darkMode = true;
  let accessibilityMode = false;
  let currentUsername = "";
  let lastToggleTime = 0;
  let postsPerPage = 15;
  let currentPage = 1;
  let loadingMore = false;
  let allPostsLoaded = false;
  /** @type {HTMLDivElement | null} */
  let scrollContainer = null;
  /** @type {string | null} */
  let lastCursor = null;
  /** @type {Set<string>} */
  let selectedTypes = new Set();
  /** @type {Set<string>} */
  let selectedLocations = new Set();
  let condensedView = false;
  /** @type {string | null} */
  let expandedPostId = null;
  let eventsToday = 0;
  let eventsLastHour = 0;
  let eventsActive = 0;
  let totalIncidents = 0;
  /** @type {Record<string, number>} */
  let incidentsByType = {};
  /** @type {Record<string, number>} */
  let topLocations = {};
  let showEventCounters = false;
  let showActiveOnly = false;
  let timeFilter = "day";
  let searchQuery = "";
  let suspendFeedMiniMaps = false;
  let miniMapSuspendScrollTop = 0;
  /** @type {Set<string>} */
  let seenCompositeKeys = new Set();
  /** @type {typeof import("./components/MapTab.svelte").default | null} */
  let MapTabComponent = null;
  /** @type {Promise<typeof import("./components/MapTab.svelte").default> | null} */
  let mapTabLoadPromise = null;
  /** @type {typeof import("./components/StatsPanel.svelte").default | null} */
  let StatsPanelComponent = null;
  /** @type {Promise<typeof import("./components/StatsPanel.svelte").default> | null} */
  let statsPanelLoadPromise = null;
  /** @type {typeof import("./components/PostTable.svelte").default | null} */
  let PostTableComponent = null;
  /** @type {Promise<typeof import("./components/PostTable.svelte").default> | null} */
  let postTableLoadPromise = null;
  const ACCESSIBILITY_MODE_STORAGE_KEY = "accessibilityMode";

  /**
   * @param {string} query
   * @param {string} text
   */
  function fuzzyMatch(query, text) {
      if (!query) return true;
      if (!text) return false;
      const q = query.toLowerCase();
      const t = text.toLowerCase();
      if (t.includes(q)) return true;
      
      const words = q.split(/\s+/).filter(Boolean);
      return words.every((word) => t.includes(word));
  }

  /**
   * @param {Incident} incident
   * @param {Partial<Post>} [existingPost={}]
   * @returns {Post}
   */
  function buildPostFromIncident(incident, existingPost = {}) {
    const timestamp = incident.timestamp || existingPost.timestamp || "";
    const date = formatDateKey(timestamp);

    return {
      id: incident.incident_no ?? existingPost.id,
      compositeId: `${incident.incident_no}-${date}`,
      details: Array.isArray(incident.Details) ? incident.Details : [],
      timestamp,
      time: formatTimestamp(timestamp),
      description: incident.description || t("fallback.descriptionUnavailable"),
      showFullDescription: existingPost.showFullDescription ?? false,
      location: incident.location || t("fallback.unknownLocation"),
      neighborhood: incident.neighborhood || "",
      latitude: incident.latitude ?? null,
      longitude: incident.longitude ?? null,
      image: buildIncidentImagePath(incident.map_filename),
      likes:
        typeof incident.likes === "number"
          ? incident.likes
          : existingPost.likes ?? 0,
      comments: Array.isArray(incident.comments)
        ? incident.comments
        : existingPost.comments ?? [],
      newComment: existingPost.newComment ?? "",
      showComments: existingPost.showComments ?? false,
      type: incident.type || t("fallback.trafficIncident"),
      likeError: existingPost.likeError ?? "",
      commentError: existingPost.commentError ?? "",
      likeErrorAnimation: existingPost.likeErrorAnimation ?? false,
      active: Boolean(incident.active),
      liking: existingPost.liking ?? false,
      severity: incident.severity ?? null,
      likedByUser:
        typeof incident.liked_by_user === "boolean"
          ? incident.liked_by_user
          : existingPost.likedByUser ?? false,
    };
  }

  /** @type {Post[]} */
  let displayPosts = [];
  $: displayPosts = searchQuery
      ? posts.filter((p) => {
          const searchSpace = `${p.description} ${p.location} ${p.type || ""} ${p.neighborhood || ""} ${p.id}`;
          return fuzzyMatch(searchQuery, searchSpace);
      })
      : posts;

  /** @type {number[]} */
  let hourlyData = [];
  let historicalCurrentHourAverage = 0;
  let statsReferenceTime = "";

  // Data Source Management
  let activeSource = "all"; // 'all', 'CHP', 'SDPD', 'SDFD'

  /**
   * @param {string} source
   */
  function setSourceFilter(source) {
    if (activeSource === source) return;
    activeSource = source;
    if (source === "map") {
      stopStatsRequest();
      void ensureMapTabLoaded();
      return;
    }
    currentPage = 1;
    // Reset other filters as they might not apply
    // selectedTypes = new Set();
    // selectedLocations = new Set();
    fetchIncidents();
    if (shouldFetchStats()) fetchIncidentStats();
  }

  async function ensureMapTabLoaded() {
    if (MapTabComponent) return MapTabComponent;
    if (!mapTabLoadPromise) {
      mapTabLoadPromise = import("./components/MapTab.svelte").then(
        (module) => {
          MapTabComponent = module.default;
          return MapTabComponent;
        },
      );
    }
    return mapTabLoadPromise;
  }

  async function ensureStatsPanelLoaded() {
    if (StatsPanelComponent) return StatsPanelComponent;
    if (!statsPanelLoadPromise) {
      statsPanelLoadPromise = import("./components/StatsPanel.svelte").then(
        (module) => {
          StatsPanelComponent = module.default;
          return StatsPanelComponent;
        },
      );
    }
    return statsPanelLoadPromise;
  }

  async function ensurePostTableLoaded() {
    if (PostTableComponent) return PostTableComponent;
    if (!postTableLoadPromise) {
      postTableLoadPromise = import("./components/PostTable.svelte").then(
        (module) => {
          PostTableComponent = module.default;
          return PostTableComponent;
        },
      );
    }
    return postTableLoadPromise;
  }

  // Network status
  let isOnline = true;
  let isFirstCheck = true;

  function updateOnlineStatus() {
    const previouslyOnline = isOnline;
    isOnline = navigator.onLine;
    if (!isOnline) {
      if (!isFirstCheck) {
        addToast(t("toast.offline"), "warning", 0);
      }
    } else {
      if (!isFirstCheck && !previouslyOnline) {
        addToast(t("toast.connectionRestored"), "success");
      }
      if (posts.length === 0) fetchIncidents();
      if (shouldFetchStats()) fetchIncidentStats();
    }
    isFirstCheck = false;
  }

  // Caching and cancellation
  const API_CACHE_TTL_MS = 15000;
  const STATS_CACHE_TTL_MS = 30000;
  const MAX_API_CACHE_ENTRIES = 30;
  const MAX_STATS_CACHE_ENTRIES = 12;

  /** @type {Map<string, ApiCacheEntry>} */
  let apiCache = new Map();
  /** @type {AbortController | null} */
  let currentController = null;
  /** @type {Map<string, StatsCacheEntry>} */
  let statsCache = new Map();
  /** @type {AbortController | null} */
  let statsController = null;
  let currentRequestId = 0;
  let currentStatsRequestId = 0;

  /**
   * @template T
   * @param {Map<string, { data: T, timestamp: number }>} cache
   * @param {string} key
   * @param {number} ttl
   * @returns {T | null}
   */
  function getCachedEntry(cache, key, ttl) {
    const entry = cache.get(key);
    if (!entry) return null;
    if (Date.now() - entry.timestamp > ttl) {
      cache.delete(key);
      return null;
    }
    cache.delete(key);
    cache.set(key, entry);
    return entry.data;
  }

  /**
   * @template T
   * @param {Map<string, { data: T, timestamp: number }>} cache
   * @param {string} key
   * @param {T} data
   * @param {number} maxEntries
   */
  function setCachedEntry(cache, key, data, maxEntries) {
    cache.delete(key);
    cache.set(key, { data, timestamp: Date.now() });
    while (cache.size > maxEntries) {
      const oldestKey = cache.keys().next().value;
      if (oldestKey === undefined) break;
      cache.delete(oldestKey);
    }
  }

  function clearIncidentCaches() {
    apiCache.clear();
  }

  function clearAllClientCaches() {
    apiCache.clear();
    statsCache.clear();
  }

  function shouldFetchStats() {
    return showEventCounters && activeSource !== "map";
  }

  function stopStatsRequest() {
    if (!statsController) return;
    statsController.abort();
    statsController = null;
  }

  function suspendMiniMapsUntilScroll() {
    suspendFeedMiniMaps = true;
    miniMapSuspendScrollTop =
      window.scrollY || document.documentElement.scrollTop || 0;
  }

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
  let suppressAutoLoadUntilScroll = false;
  let autoLoadUnlockScrollTop = 0;

  function pauseAutoLoadUntilUserScroll() {
    suppressAutoLoadUntilScroll = true;
    autoLoadUnlockScrollTop =
      window.scrollY || document.documentElement.scrollTop || 0;
  }

  function setCondensedView(nextView) {
    if (condensedView === nextView) return;
    condensedView = nextView;
    if (nextView) void ensurePostTableLoaded();
    pauseAutoLoadUntilUserScroll();
    if (showEventCounters) {
      showEventCounters = false;
      stopStatsRequest();
      suspendMiniMapsUntilScroll();
    }
  }

  function applyUserPreferences() {
    document.body.classList.toggle("dark-mode", darkMode);
    document.body.classList.toggle("accessibility-mode", accessibilityMode);
  }

  function toggleDarkMode() {
    darkMode = !darkMode;
    applyUserPreferences();
    localStorage.setItem("darkMode", darkMode.toString());
  }

  function toggleAccessibilityMode() {
    accessibilityMode = !accessibilityMode;
    applyUserPreferences();
    localStorage.setItem(ACCESSIBILITY_MODE_STORAGE_KEY, accessibilityMode.toString());
  }

  function toggleEventCounters() {
    showEventCounters = !showEventCounters;
    if (shouldFetchStats()) {
      void ensureStatsPanelLoaded();
      fetchIncidentStats();
    } else {
      stopStatsRequest();
    }
  }

  function toggleActiveOnly() {
    showActiveOnly = !showActiveOnly;
    currentPage = 1;
    fetchIncidents();
  }

  /**
   * @param {string} newFilter
   */
  function setTimeFilter(newFilter) {
    timeFilter = newFilter;
    // Don't destroy chart here to prevent flashing
    // statsCache = {}; // Removed to preserve cache
    fetchIncidentStats();
  }

  /**
   * @param {string} type
   */
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

  /**
   * @param {string} location
   */
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
    const controller = new AbortController();
    currentController = controller;
    const signal = controller.signal;

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
      const cachedData = getCachedEntry(apiCache, cacheKey, API_CACHE_TTL_MS);
      if (cachedData) {
        if (requestId === currentRequestId) processIncidents(cachedData);
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

      /** @type {Incident[]} */
      const incidents = await retryWithBackoff(fetchFn, 3, 1000);

      if (requestId !== currentRequestId) {
        return;
      }

      setCachedEntry(apiCache, cacheKey, incidents, MAX_API_CACHE_ENTRIES);
      processIncidents(incidents);
    } catch (err) {
      if (!(err instanceof Error) || err.name !== "AbortError") {
        console.error("Error fetching incidents:", err);
        addToast(
          t("toast.failedLoadIncidents"),
          "error",
        );
        if (currentPage === 1 && posts.length === 0) {
          posts = [
            {
              id: "error-fallback",
              compositeId: "error-fallback",
              timestamp: new Date().toISOString(),
              time: t("fallback.error"),
              description: t("state.loadIncidentsUnavailable"),
              showFullDescription: false,
              location: t("fallback.notAvailable"),
              neighborhood: "",
              latitude: null,
              longitude: null,
              image: "",
              likes: 0,
              comments: [],
              newComment: "",
              showComments: false,
              type: t("fallback.error"),
              likeError: "",
              commentError: "",
              likeErrorAnimation: false,
              active: false,
              liking: false,
              severity: null,
              likedByUser: false,
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
      if (currentController === controller) {
        currentController = null;
      }
    }
  }

  /**
   * @param {Incident[]} incidents
   */
  function processIncidents(incidents) {
    if (!Array.isArray(incidents)) {
      console.error("Invalid incidents data: expected array");
      addToast(t("toast.invalidIncidentData"), "error");
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
          ? formatDateKey(incident.timestamp)
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
        ...buildPostFromIncident(incident),
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
      return compareText(b.id, a.id);
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

    if (suppressAutoLoadUntilScroll) {
      if (Math.abs(scrollTop - autoLoadUnlockScrollTop) <= 24) {
        return;
      }
      suppressAutoLoadUntilScroll = false;
    }

    if (
      suspendFeedMiniMaps &&
      Math.abs(scrollTop - miniMapSuspendScrollTop) > 24
    ) {
      suspendFeedMiniMaps = false;
    }

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
    const requestId = ++currentStatsRequestId;

    if (statsController) {
      statsController.abort();
    }
    const controller = new AbortController();
    statsController = controller;
    const signal = controller.signal;

    try {
      let url = "/api/incident_stats?date_filter=" + timeFilter;
      if (activeSource && activeSource !== "all" && activeSource !== "map") {
        url += `&source=${encodeURIComponent(activeSource)}`;
      }

      const cacheKey = url;
      const cachedStats = getCachedEntry(
        statsCache,
        cacheKey,
        STATS_CACHE_TTL_MS,
      );
      if (cachedStats) {
        if (requestId !== currentStatsRequestId) return;
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
        hourlyData = (cachedStats.hourlyData || []).map(Number);
        historicalCurrentHourAverage =
          cachedStats.historicalCurrentHourAverage || 0;
        statsReferenceTime = cachedStats.generatedAt || "";
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

      /** @type {IncidentStatsResponse} */
      const stats = await retryWithBackoff(fetchFn, 3, 1000);

      if (requestId !== currentStatsRequestId) {
        return;
      }

      setCachedEntry(statsCache, cacheKey, stats, MAX_STATS_CACHE_ENTRIES);

      eventsToday = stats.eventsToday;
      eventsLastHour = stats.eventsLastHour;
      eventsActive = stats.eventsActive;
      totalIncidents = stats.totalIncidents;
      hourlyData = (stats.hourlyData || []).map(Number);
      historicalCurrentHourAverage = stats.historicalCurrentHourAverage || 0;
      statsReferenceTime = stats.generatedAt || "";

      incidentsByType = Object.fromEntries(
        Object.entries(stats.incidentsByType).sort(([, a], [, b]) => b - a),
      );
      topLocations = Object.fromEntries(
        Object.entries(stats.topLocations).sort(([, a], [, b]) => b - a),
      );
    } catch (err) {
      if (!(err instanceof Error) || err.name !== "AbortError") {
        console.error("Error fetching incident stats:", err);
        addToast(t("toast.failedLoadIncidentStats"), "error");
      }
    } finally {
      if (requestId === currentStatsRequestId) {
        statsController = null;
      }
    }
  }

  /**
   * @param {string} postId
   */
  async function likePost(postId) {
    const post = posts.find((p) => p.id === postId);
    if (!post || post.liking) return;

    posts = posts.map((p) => (p.id === postId ? { ...p, liking: true } : p));

    const originalLikes = post.likes;
    const wasLiked = Boolean(post.likedByUser);
    const nextLikes = Math.max(0, originalLikes + (wasLiked ? -1 : 1));

    posts = posts.map((p) =>
      p.id === postId
        ? {
            ...p,
            likes: nextLikes,
            likedByUser: !wasLiked,
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

      /** @type {LikeResponse} */
      const data = await retryWithBackoff(fetchFn, 2, 500);
      clearIncidentCaches();
      posts = posts.map((p) =>
        p.id === postId
          ? {
              ...p,
              likes: data.likes,
              likedByUser: Boolean(data.liked_by_user),
              likeError: "",
              liking: false,
            }
          : p,
      );
    } catch (err) {
      console.error("Error updating like:", err);
      addToast(
        wasLiked ? t("toast.failedUnlikePost") : t("toast.failedLikePost"),
        "error",
      );
      posts = posts.map((p) =>
        p.id === postId
          ? {
              ...p,
              likes: originalLikes,
              likedByUser: wasLiked,
              liking: false,
            }
          : p,
      );
    }
  }

  /**
   * @param {string} postId
   */
  function toggleComments(postId) {
    const now = Date.now();
    if (now - lastToggleTime < 200) return;
    lastToggleTime = now;
    posts = posts.map((post) =>
      post.id === postId ? { ...post, showComments: !post.showComments } : post,
    );
  }

  /**
   * @param {Post} post
   */
  function sharePost(post) {
    const text = t("share.incidentSummary", {
      description: post.description,
      location: post.location,
    });
    const url = window.location.origin;

    if (navigator.share) {
      navigator.share({ title: t("app.name"), text, url });
    } else {
      const twitterUrl = `https://twitter.com/intent/tweet?text=${encodeURIComponent(text)}&url=${encodeURIComponent(url)}`;
      window.open(twitterUrl, "_blank");
    }
  }


  /**
   * @param {string} postId
   * @param {string | null} [commentContent=null]
   */
  async function submitComment(postId, commentContent = null) {
    const post = posts.find((p) => p.id === postId);
    const commentText =
      commentContent !== null ? commentContent : post?.newComment;

    if (!post || !commentText || commentText.trim() === "") return;

    const userComments = post.comments.filter(
      (c) => c.username === currentUsername,
    );
    if (userComments.length >= 2) {
      addToast(t("toast.commentLimitReached"), "warning");
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

      /** @type {CommentResponse} */
      const data = await retryWithBackoff(fetchFn, 2, 500);
      clearIncidentCaches();
      posts = posts.map((p) =>
        p.id === postId
          ? { ...p, comments: data.comments, newComment: "", commentError: "" }
          : p,
      );
      addToast(t("toast.commentAdded"), "success");
    } catch (err) {
      console.error("Error submitting comment:", err);
      addToast(t("toast.failedSubmitComment"), "error");
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

  /**
   * @param {string} postId
   */
  function toggleDescription(postId) {
    posts = posts.map((post) =>
      post.id === postId
        ? { ...post, showFullDescription: !post.showFullDescription }
        : post,
    );
  }

  /**
   * @param {string} postId
   */
  function toggleExpand(postId) {
    expandedPostId = expandedPostId === postId ? null : postId;
  }

  /**
   * @param {TouchEvent} e
   */
  function handleTouchStart(e) {
    if (activeSource === "map") return;
    touchStartX = e.touches[0].clientX;
    touchStartY = e.touches[0].clientY;
    touchEndX = touchStartX;
    touchEndY = touchStartY;
    swipeInProgress = true;
  }

  /**
   * @param {TouchEvent} e
   */
  function handleTouchMove(e) {
    if (activeSource === "map") return;
    if (!swipeInProgress) return;

    touchEndX = e.touches[0].clientX;
    touchEndY = e.touches[0].clientY;

    const diffX = touchStartX - touchEndX;
    const diffY = touchEndY - touchStartY;

    if (Math.abs(diffX) > 20 && Math.abs(diffY) < verticalThreshold) {
      const nextDirection = diffX > 0 ? "left" : "right";
      if (!swipeIndicator) swipeIndicator = true;
      if (swipeDirection !== nextDirection) swipeDirection = nextDirection;
    } else {
      if (swipeIndicator) swipeIndicator = false;
    }
  }

  /**
   * @param {TouchEvent} e
   */
  function handleTouchEnd(e) {
    if (activeSource === "map") return;
    if (!swipeInProgress) return;

    const diffX = touchStartX - touchEndX;
    const diffY = Math.abs(touchStartY - touchEndY);

    if (Math.abs(diffX) > swipeThreshold && diffY < verticalThreshold) {
      if (diffX > 0) {
        setCondensedView(true);
        if (navigator.vibrate) navigator.vibrate(50);
      } else {
        setCondensedView(false);
        if (navigator.vibrate) navigator.vibrate(50);
      }
    }

    swipeInProgress = false;
    swipeIndicator = false;
  }

  function toggleView() {
    setCondensedView(!condensedView);
  }

  $: if (showEventCounters && !StatsPanelComponent) void ensureStatsPanelLoaded();
  $: if (condensedView && !PostTableComponent) void ensurePostTableLoaded();

  // Event handlers for components
  /**
   * @param {PostIdEvent} event
   */
  function handlePostLike(event) {
    likePost(event.detail.postId);
  }

  /**
   * @param {PostIdEvent} event
   */
  function handlePostToggleComments(event) {
    toggleComments(event.detail.postId);
  }

  /**
   * @param {PostShareEvent} event
   */
  function handlePostShare(event) {
    sharePost(event.detail.post);
  }

  /**
   * @param {PostIdEvent} event
   */
  function handlePostToggleDescription(event) {
    toggleDescription(event.detail.postId);
  }

  /**
   * @param {PostCommentEvent} event
   */
  function handlePostSubmitComment(event) {
    submitComment(event.detail.postId, event.detail.comment);
  }

  /**
   * @param {PostIdEvent} event
   */
  function handleTableToggleExpand(event) {
    toggleExpand(event.detail.postId);
  }

  /**
   * @param {PostIdEvent} event
   */
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
    const storedAccessibilityMode = localStorage.getItem(ACCESSIBILITY_MODE_STORAGE_KEY);
    darkMode = storedMode ? storedMode === "true" : prefersDark;
    accessibilityMode = storedAccessibilityMode === "true";
    applyUserPreferences();

    currentUsername =
      localStorage.getItem("username") || generateRandomUsername();
    if (!localStorage.getItem("username")) {
      localStorage.setItem("username", currentUsername);
    }

    window.addEventListener("online", updateOnlineStatus);
    window.addEventListener("offline", updateOnlineStatus);
    updateOnlineStatus();

    // Removed 60s fetchIncidents interval to prevent screen wiping

    window.addEventListener("scroll", debouncedHandleScroll, { passive: true });

    if (scrollContainer) {
      scrollContainer.addEventListener("touchstart", handleTouchStart, {
        passive: true,
      });
      scrollContainer.addEventListener("touchmove", handleTouchMove, {
        passive: true,
      });
      scrollContainer.addEventListener("touchend", handleTouchEnd, {
        passive: true,
      });
    }

    const updateInterval = setInterval(() => {
      if (isOnline && !loading && !loadingMore) {
        checkForUpdates();
        if (shouldFetchStats()) fetchIncidentStats();
      }
    }, 20000);

    return () => {
      clearInterval(updateInterval);
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

  /**
   * @param {StringDetailEvent} event
   */
  function handleSourceChange(event) {
    setSourceFilter(event.detail);
  }

  /**
   * @param {StringDetailEvent} event
   */
  function handleStatsTimeFilter(event) {
    setTimeFilter(event.detail);
  }

  /**
   * @param {StringDetailEvent} event
   */
  function handleStatsTypeFilter(event) {
    filterByType(event.detail);
  }

  /**
   * @param {StringDetailEvent} event
   */
  function handleStatsLocationFilter(event) {
    filterByLocation(event.detail);
  }

  /**
   * @param {KeyboardEvent} event
   */
  function handleLoadMoreKeydown(event) {
    if (event.key === "Enter") {
      forceLoadMore();
    }
  }

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
      /** @type {Incident[]} */
      const newIncidents = await res.json();

      if (!Array.isArray(newIncidents)) return;

      let updatedPosts = [...posts];
      let newPostsCount = 0;

      newIncidents.forEach((incident) => {
        if (!incident || !incident.incident_no || !incident.timestamp) return;

        const existingIndex = updatedPosts.findIndex(
          (p) => p.id === incident.incident_no,
        );

        if (existingIndex !== -1) {
          // Update the existing post's properties without treating it as new
          updatedPosts[existingIndex] = {
            ...updatedPosts[existingIndex],
            ...buildPostFromIncident(incident, updatedPosts[existingIndex]),
          };
        } else {
          // It's a genuinely new post
          newPostsCount++;
          const duplicateKey = `${incident.incident_no}-${incident.timestamp}-${incident.location}`;
          seenCompositeKeys.add(duplicateKey);

          updatedPosts.unshift(buildPostFromIncident(incident));
        }
      });

      // Update posts optimally
      if (newPostsCount > 0) {
        clearAllClientCaches();
        posts = updatedPosts;
        addToast(t("toast.newIncidents", { count: newPostsCount }), "info");
      } else {
        posts = updatedPosts; // Triggers reactivity for updated properties
      }
    } catch (err) {
      console.error("Error checking for updates:", err);
    }
  }
</script>

<div class="container" bind:this={scrollContainer}>
  {#if !accessibilityMode}
    <HeadlineTicker
      events={[
        ...posts.slice(0, 5),
        ...posts.filter(
          (p) =>
            p.active &&
            p.type &&
            p.type.toLowerCase().includes("sig") &&
            !posts.slice(0, 5).some((bp) => bp.id === p.id),
        ),
      ]}
    />
  {/if}
  <Header
    {showEventCounters}
    {darkMode}
    accessibilityMode={accessibilityMode}
    {activeSource}
    on:toggleEventCounters={toggleEventCounters}
    on:toggleDarkMode={toggleDarkMode}
    on:toggleAccessibilityMode={toggleAccessibilityMode}
  />

  <div class="toolbar">
    <div class="tabs-container">
      <SourceTabs
        {activeSource}
        on:changeSource={handleSourceChange}
      />
    </div>
    {#if activeSource !== "map"}
      <div class="search-wrapper">
        <SearchBar bind:value={searchQuery} />
      </div>
    {/if}
  </div>

  {#if activeSource === "map" && !MapTabComponent}
    <div class="map-loading">{t("state.loadingMap")}</div>
  {/if}

  <!-- Load the map tab lazily, then keep it mounted after the first open -->
  {#if MapTabComponent}
    <div style={activeSource === "map" ? "" : "display:none"}>
      <svelte:component this={MapTabComponent} isVisible={activeSource === "map"} />
    </div>
  {/if}

  {#if activeSource !== "map"}
    {#if showEventCounters}
      {#if StatsPanelComponent}
        <svelte:component
          this={StatsPanelComponent}
          {eventsToday}
          {eventsLastHour}
          {eventsActive}
          {totalIncidents}
          {timeFilter}
          {hourlyData}
          {historicalCurrentHourAverage}
          referenceTime={statsReferenceTime}
          {incidentsByType}
          {topLocations}
          {selectedTypes}
          {selectedLocations}
          on:filterTime={handleStatsTimeFilter}
          on:filterType={handleStatsTypeFilter}
          on:filterLocation={handleStatsLocationFilter}
          on:resetTypeFilters={resetTypeFilters}
          on:resetLocationFilters={resetLocationFilters}
        />
      {/if}
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
        <div class="empty-icon">📂</div>
        <p>{t("state.noIncidentsTitle")}</p>
        <p>{t("state.noIncidentsSubtitle")}</p>
      </div>
    {:else if displayPosts.length === 0}
      <div class="empty-state" in:fade={{ duration: 150 }}>
        <div class="empty-icon">🔍</div>
        <p>{t("state.noSearchTitle")}</p>
        <p>{t("state.noSearchSubtitle")}</p>
      </div>
    {:else if condensedView}
      {#if PostTableComponent}
        <svelte:component
          this={PostTableComponent}
          posts={displayPosts}
          {searchQuery}
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
      {/if}
    {:else}
      <div class="feed" in:fade={{ duration: 200 }}>
        {#each displayPosts as post, i (post.compositeId)}
          <PostCard
            {post}
            index={i}
            {postsPerPage}
            {searchQuery}
            suspendMiniMaps={suspendFeedMiniMaps}
            on:like={handlePostLike}
            on:toggleComments={handlePostToggleComments}
            on:share={handlePostShare}
            on:toggleDescription={handlePostToggleDescription}
            on:submitComment={handlePostSubmitComment}
            on:goToMap={() => setSourceFilter("map")}
          />
        {/each}
      </div>
    {/if}

    {#if !allPostsLoaded && posts.length > 0 && posts.length >= postsPerPage}
      <div
        class="scroll-indicator"
        in:fade={{ duration: 150 }}
        on:click={forceLoadMore}
        role="button"
        tabindex="0"
        on:keydown={handleLoadMoreKeydown}
      >
        <div class="scroll-dots">
          <span class="dot"></span>
          <span class="dot"></span>
          <span class="dot"></span>
        </div>
        <p>{t("state.moreIncidentsAvailable")}</p>
      </div>
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

  :global(body:not(.dark-mode) .control-toggle:hover),
  :global(body:not(.dark-mode) .control-toggle.is-active),
  :global(body:not(.dark-mode) .source-tab.active),
  :global(body:not(.dark-mode) .action-button:hover),
  :global(body:not(.dark-mode) .clickable-location:hover) {
    color: #0f172a;
  }

  :global(body:not(.dark-mode) .control-toggle:hover),
  :global(body:not(.dark-mode) .control-toggle.is-active) {
    background: rgba(49, 130, 206, 0.18);
    border-color: #1e40af;
    box-shadow: 0 0 0 2px rgba(30, 64, 175, 0.12);
  }

  :global(body:not(.dark-mode) .action-button:hover),
  :global(body:not(.dark-mode) .source-tab.active) {
    background: rgba(49, 130, 206, 0.16);
    border-color: #1e40af;
  }

  :global(body:not(.dark-mode) .post-badge) {
    background: #ffffff;
    color: #0f172a;
    border-color: color-mix(in srgb, var(--badge-color) 70%, #0f172a);
    box-shadow:
      0 8px 20px rgba(15, 23, 42, 0.14),
      inset 4px 0 0 var(--badge-color);
  }

  :global(body:not(.dark-mode) .post-badge .incident-icon) {
    color: #0f172a;
  }

  :global(body:not(.dark-mode) .severity-inline-badge) {
    background: color-mix(in srgb, var(--sev-color) 14%, #ffffff);
    border-color: color-mix(in srgb, var(--sev-color) 42%, #cbd5e1);
    color: color-mix(in srgb, var(--sev-color) 78%, #0f172a);
    box-shadow:
      0 8px 18px rgba(15, 23, 42, 0.08),
      inset 0 1px 0 rgba(255, 255, 255, 0.75);
  }

  :global(body:not(.dark-mode) .severity-inline-badge .sev-score-box) {
    color: #ffffff;
    box-shadow:
      0 4px 10px color-mix(in srgb, var(--sev-color) 24%, transparent);
  }

  :global(body:not(.dark-mode) .severity-inline-badge .sev-label) {
    color: inherit;
  }

  :global(body:not(.dark-mode) .placeholder-content) {
    color: #1e293b;
    opacity: 1;
  }

  :global(body:not(.dark-mode) .incident-icon-small) {
    color: #0f172a !important;
    filter: none;
  }

  :global(body:not(.dark-mode) .stat-value) {
    color: #0f172a;
    text-shadow: none;
  }

  :global(body:not(.dark-mode) .stat-icon) {
    color: #1e40af;
    filter: none;
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
    touch-action: pan-y;
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
  
  /* Toolbar layout */
  .toolbar {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    margin-bottom: 0.8rem;
    align-items: center;
    position: relative;
  }
  
  .tabs-container {
    width: 100%;
    display: flex;
    justify-content: center;
  }

  .search-wrapper {
    width: 100%;
    max-width: 400px;
  }

  @media (min-width: 768px) {
    .toolbar {
      flex-direction: row;
      justify-content: center;
      align-items: center;
    }
    .tabs-container {
      width: auto;
      flex: 0 1 auto;
    }
    .search-wrapper {
      width: 250px;
      flex-shrink: 0;
      position: absolute;
      right: 0;
      top: 50%;
      transform: translateY(-50%);
      margin: 0;
    }
  }
</style>
