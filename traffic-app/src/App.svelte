<script>
  import { onMount, onDestroy } from 'svelte';
  import { fade, slide, fly } from 'svelte/transition';
  import { flip } from 'svelte/animate';
  import { Chart as ChartJS, CategoryScale, TimeScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend, Filler, LineController } from 'chart.js';
  import 'chartjs-adapter-date-fns';

  // Register Chart.js components
  ChartJS.register(CategoryScale, TimeScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend, Filler, LineController);

  let posts = [];
  let loading = true;
  let darkMode = false;
  let currentUsername = '';
  let lastToggleTime = 0;
  let postsPerPage = 30;
  let currentPage = 1;
  let loadingMore = false;
  let allPostsLoaded = false;
  let scrollContainer;
  let lastCursor = null; // For cursor-based pagination
  let selectedType = null;
  let condensedView = false;
  let expandedPostId = null;
  let eventsToday = 0;
  let eventsLastHour = 0;
  let eventsActive = 0; // New state variable for active events
  let totalIncidents = 0;
  let incidentsByType = {};
  let topLocations = {};
  let showEventCounters = false; // New state variable for collapsable section
  let showActiveOnly = false; // New state variable to toggle active events filter
  let timeFilter = 'day'; // New state variable for time period filter
  let seenCompositeKeys = new Set(); // Global set to track seen composite keys
  let hourlyData = []; // Activity chart data (hourly, daily, or monthly depending on timeFilter)
  let chartCanvas; // Chart.js canvas reference
  let chartInstance; // Chart.js chart instance

  const VW = 288, VH = 120;
  const PADX = 8, PADY = 8; // room for big dots/glow

  $: xStep = hourlyData.length > 1 ? (VW - PADX*2) / (hourlyData.length - 1) : 0;
  $: yMax = Math.max(1, ...hourlyData);
  $: y = v => PADY + (VH - PADY*2) - (v / yMax) * (VH - PADY*2);

  $: chartPath = hourlyData.length ? `M ${PADX} ${VH-PADY} ${hourlyData.map((v,i)=>`L ${PADX + i*xStep} ${y(v)}`).join(' ')} L ${VW-PADX} ${VH-PADY} Z` : '';

  $: linePath = hourlyData.length ? hourlyData.map((v,i)=>`${i?'L':'M'} ${PADX + i*xStep} ${y(v)}`).join(' ') : '';

  // Generate dynamic chart labels and title based on timeFilter
  $: currentTime = new Date();
  $: currentHour = currentTime.getHours();
  $: sectionTitle = timeFilter === 'day' ? '24-Hour Activity' :
    timeFilter === 'week' ? '7-Day Activity' :
    timeFilter === 'month' ? '30-Day Activity' :
    'Yearly Activity';
  $: chartLabels = timeFilter === 'day' ?
    Array.from({ length: 24 }, (_, i) => {
      const time = new Date(currentTime.getTime() - (23 - i) * 60 * 60 * 1000);
      return time.toLocaleTimeString('en-US', { hour: 'numeric', hour12: true });
    }) :
    timeFilter === 'week' ?
    Array.from({ length: 7 }, (_, i) => {
      const date = new Date();
      date.setDate(date.getDate() - (6 - i));
      return date.toLocaleDateString('en-US', { weekday: 'short', day: 'numeric' });
    }) :
    timeFilter === 'month' ?
    Array.from({ length: 30 }, (_, i) => {
      const date = new Date();
      date.setDate(date.getDate() - (29 - i));
      return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    }) :
    Array.from({ length: 12 }, (_, i) => {
      const date = new Date();
      date.setDate(1);
      date.setMonth(currentTime.getMonth() - (11 - i));
      return date.toLocaleDateString('en-US', { month: 'short' });
    });

  // Toast notification system
  let toasts = [];
  let toastId = 0;

  function addToast(message, type = 'info', duration = 5000) {
    const id = ++toastId;
    toasts = [...toasts, { id, message, type }];
    if (duration > 0) {
      setTimeout(() => removeToast(id), duration);
    }
    return id;
  }

  function removeToast(id) {
    toasts = toasts.filter(t => t.id !== id);
  }

  // Network status
  let isOnline = true;
  let isFirstCheck = true;

  function updateOnlineStatus() {
    const previouslyOnline = isOnline;
    isOnline = navigator.onLine;
    if (!isOnline) {
      if (!isFirstCheck) {
        addToast('You are offline. Some features may not work.', 'warning', 0);
      }
    } else {
      if (!isFirstCheck && !previouslyOnline) {
        addToast('Connection restored.', 'success');
      }
      // Retry failed requests when back online
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
  let currentRequestId = 0; // For handling race conditions
  
  // Touch/swipe handling variables
  let touchStartX = 0;
  let touchEndX = 0;
  let touchStartY = 0;
  let touchEndY = 0;
  let swipeInProgress = false;
  let swipeIndicator = false;
  let swipeDirection = '';
  let swipeThreshold = 80; // minimum distance for a swipe
  let verticalThreshold = 50; // maximum vertical movement allowed for horizontal swipe

  // Pull-to-refresh variables
  let pullStartY = 0;
  let pullDistance = 0;
  let isPulling = false;
  let pullThreshold = 100; // minimum pull distance to trigger refresh
  let refreshing = false;

  const adjectives = ['Cool', 'Happy', 'Swift', 'Brave', 'Clever', 'Lucky'];
  const nouns = ['Panda', 'Tiger', 'Eagle', 'Fox', 'Wolf', 'Bear'];

  function generateRandomUsername() {
    const adj = adjectives[Math.floor(Math.random() * adjectives.length)];
    const noun = nouns[Math.floor(Math.random() * nouns.length)];
    const num = Math.floor(Math.random() * 100);
    return `${adj}${noun}${num}`;
  }

  // Debounce utility
  function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
      const later = () => {
        clearTimeout(timeout);
        func(...args);
      };
      clearTimeout(timeout);
      timeout = setTimeout(later, wait);
    };
  }

  // Retry utility with exponential backoff
  async function retryWithBackoff(fn, maxRetries = 3, baseDelay = 1000) {
    for (let attempt = 0; attempt <= maxRetries; attempt++) {
      try {
        return await fn();
      } catch (error) {
        if (attempt === maxRetries) throw error;
        const delay = baseDelay * Math.pow(2, attempt);
        await new Promise(resolve => setTimeout(resolve, delay));
      }
    }
  }


  function toggleDarkMode() {
    darkMode = !darkMode;
    document.body.classList.toggle('dark-mode', darkMode);
    localStorage.setItem('darkMode', darkMode.toString());
  }

  function toggleEventCounters() {
    showEventCounters = !showEventCounters;
  }

  function toggleActiveOnly() {
    showActiveOnly = !showActiveOnly;
    currentPage = 1; // Reset to first page when filter changes
    fetchIncidents(); // Re-fetch incidents with new filter
  }

  function setTimeFilter(newFilter) {
    timeFilter = newFilter;
    statsCache = {}; // Clear stats cache to ensure fresh data
    fetchIncidentStats(); // Re-fetch stats (including updated chart data)
  }

  // Helper function to limit stats to maximum 6 items
  function limitStatsData(stats) {
    const limit = 6;
    return {
      incidentsByType: Object.fromEntries(
        Object.entries(stats.incidentsByType || {})
          .sort(([,a], [,b]) => b - a)
          .slice(0, limit)
      ),
      topLocations: Object.fromEntries(
        Object.entries(stats.topLocations || {})
          .sort(([,a], [,b]) => b - a)
          .slice(0, limit)
      ),
      eventsToday: stats.eventsToday,
      eventsLastHour: stats.eventsLastHour,
      eventsActive: stats.eventsActive,
      totalIncidents: stats.totalIncidents
    };
  }

  // Memoized unique incident types
  let memoizedTypes = [];
  let lastPostsLength = 0;

  function getUniqueIncidentTypes() {
    if (posts.length !== lastPostsLength) {
      const types = new Set();
      posts.forEach(post => types.add(post.type));
      memoizedTypes = Array.from(types);
      lastPostsLength = posts.length;
    }
    return memoizedTypes;
  }

  function filterByType(type) {
    selectedType = selectedType === type ? null : type;
    currentPage = 1;
    // posts and seenCompositeKeys will be cleared by fetchIncidents when currentPage is 1
    fetchIncidents();
  }

  async function fetchIncidents() {
    const requestId = ++currentRequestId; // Assign unique ID to this request

    // Cancel any ongoing request
    if (currentController) {
      currentController.abort();
    }
    currentController = new AbortController();
    const signal = currentController.signal;

    try {
      // Set loading state for initial load or filter change
      if (currentPage === 1) {
        loading = true;
        posts = []; // Clear posts for initial load or filter change
        seenCompositeKeys.clear(); // ✅ Clear the set
        lastCursor = null; // Reset cursor for new queries
      } else {
        loadingMore = true; // Use loadingMore for subsequent pages
      }

      let url = `/api/incidents?limit=${postsPerPage}`;

      // Use cursor-based pagination for subsequent pages
      if (currentPage > 1 && lastCursor) {
        url += `&cursor=${encodeURIComponent(lastCursor)}`;
      }

      if (selectedType) {
        url += `&type=${encodeURIComponent(selectedType)}`;
      }
      if (showActiveOnly) {
        url += `&active_only=true`;
      }

      // Check cache first
      const cacheKey = url;
      if (apiCache.has(cacheKey)) {
        const cachedData = apiCache.get(cacheKey);
        // Only process if this is still the latest request
        if (requestId === currentRequestId) {
          processIncidents(cachedData);
        }
        return;
      }

      const fetchFn = async () => {
        const res = await fetch(url, { signal });
        if (!res.ok) {
          throw new Error(`Failed to fetch incidents: ${res.status} ${res.statusText}`);
        }
        return await res.json();
      };

      const incidents = await retryWithBackoff(fetchFn, 3, 1000);

      // Only process if this is still the latest request (prevents race conditions)
      if (requestId !== currentRequestId) {
        return; // Ignore outdated response
      }

      // Cache the response
      apiCache.set(cacheKey, incidents);

      processIncidents(incidents);

    } catch (err) {
      if (err.name !== 'AbortError') {
        console.error("Error fetching incidents:", err);
        addToast('Failed to load incidents. Please check your connection and try again.', 'error');
        // Show fallback content
        if (currentPage === 1 && posts.length === 0) {
          posts = [{
            id: 'error-fallback',
            compositeId: 'error-fallback',
            timestamp: new Date().toISOString(),
            time: 'Error',
            description: 'Unable to load incidents at this time.',
            location: 'N/A',
            image: '',
            likes: 0,
            comments: [],
            newComment: "",
            showComments: false,
            type: "Error",
            likeError: "",
            commentError: "",
            likeErrorAnimation: false,
            active: false
          }];
        }
      }
    } finally {
      // Reset loading states only if this is still the latest request
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
    // Validate API response structure
    if (!Array.isArray(incidents)) {
      console.error('Invalid incidents data: expected array');
      addToast('Received invalid data from server', 'error');
      return;
    }

    const newProcessedPosts = incidents
      .filter(incident => {
        // Validate required fields
        if (!incident || typeof incident !== 'object') return false;
        if (!incident.incident_no || !incident.timestamp || !incident.map_filename) {
          console.warn('Incident missing required fields:', incident);
          return false;
        }
        return true;
      })
      .map(incident => {
        const date = incident.timestamp ? new Date(incident.timestamp).toLocaleDateString() : '';
        incident.compositeId = `${incident.incident_no}-${date}`;
        return incident;
      })
      .filter(incident => {
        // More robust duplicate detection using multiple criteria
        const duplicateKey = `${incident.incident_no}-${incident.timestamp}-${incident.location}`;
        if (seenCompositeKeys.has(duplicateKey)) {
          return false;
        }
        seenCompositeKeys.add(duplicateKey);
        return true;
      })
      .map(incident => ({
        id: incident.incident_no,
        compositeId: incident.compositeId,
        timestamp: incident.timestamp,
        time: formatTimestamp(incident.timestamp),
        description: incident.description || 'No description available',
        showFullDescription: false,
        location: incident.location || 'Unknown location',
        image: `/maps/${incident.map_filename}`,
        likes: typeof incident.likes === 'number' ? incident.likes : 0,
        comments: Array.isArray(incident.comments) ? incident.comments : [],
        newComment: "",
        showComments: false,
        type: incident.type || "Traffic Incident",
        likeError: "",
        commentError: "",
        likeErrorAnimation: false,
        active: Boolean(incident.active),
        liking: false
      }));

    // Append new posts to the existing posts array
    const filteredPosts = showActiveOnly ? newProcessedPosts.filter(p => p.active) : newProcessedPosts;
    posts = [...posts, ...filteredPosts];

    // Update cursor for next page (use the timestamp of the last incident)
    if (incidents.length > 0) {
      lastCursor = incidents[incidents.length - 1].timestamp;
    }

    // Check if all posts are loaded (if the number of incidents fetched is less than the limit)
    allPostsLoaded = incidents.length < postsPerPage;
  }
  
  
  function loadMorePosts() {
    if (loadingMore || allPostsLoaded) return;
    
    console.log('Loading more posts...');
    loadingMore = true;
    
    currentPage++;
    
    fetchIncidents();
  }
  
  // Debounced scroll handler
  const debouncedHandleScroll = debounce(() => {
    // Use window/document scroll properties for overall page scroll
    const scrollTop = window.scrollY || document.documentElement.scrollTop;
    const scrollHeight = document.documentElement.scrollHeight;
    const clientHeight = window.innerHeight;

    const scrollBottom = scrollHeight - scrollTop - clientHeight;

    // Only load more when very close to the bottom to minimize unnecessary loads
    // Using a threshold that works with overall page scroll
    if (scrollBottom < 600 && !loadingMore && !allPostsLoaded) {
      console.log("Triggering load more posts from scroll (window scroll)");
      loadMorePosts();
    }
  }, 100);

  // Modify the forceLoadMore function to be more conservative
  function forceLoadMore() {
    if (allPostsLoaded || loadingMore) return;
    
    console.log("Force loading more posts");
    currentPage++;
    fetchIncidents();
  }

  function formatTimestamp(timestamp) {
    if (!timestamp) return "Recent";
    const date = new Date(timestamp);
    return date.toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      hour12: true
    });
  }

  function formatTimeOnly(timestamp) {
    if (!timestamp) return "Recent";
    const date = new Date(timestamp);
    return date.toLocaleString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
      hour12: true
    });
  }

  function formatCommentTimestamp(timestamp) {
    if (!timestamp) return "";
    const date = new Date(timestamp);
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    
    if (diff < 60000) return "just now";
    if (diff < 3600000) {
      const minutes = Math.floor(diff / 60000);
      return `${minutes}m ago`;
    }
    if (diff < 86400000) {
      const hours = Math.floor(diff / 3600000);
      return `${hours}h ago`;
    }
    if (diff < 604800000) {
      const days = Math.floor(diff / 86400000);
      return `${days}d ago`;
    }
    
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric'
    });
  }

  async function fetchIncidentStats() {
    // Cancel any ongoing stats request
    if (statsController) {
      statsController.abort();
    }
    statsController = new AbortController();
    const signal = statsController.signal;

    try {
      let url = '/api/incident_stats?date_filter=' + timeFilter;

      // Check cache first
      const cacheKey = url;
      if (statsCache[cacheKey] && Date.now() - statsCache[cacheKey].timestamp < 30000) { // 30 second cache
        const cachedStats = statsCache[cacheKey].data;
        eventsToday = cachedStats.eventsToday;
        eventsLastHour = cachedStats.eventsLastHour;
        eventsActive = cachedStats.eventsActive;
        totalIncidents = cachedStats.totalIncidents;

        // Apply limiting to cached data as well
        const limit = 6;
        incidentsByType = Object.fromEntries(
          Object.entries(cachedStats.incidentsByType)
            .sort(([,a], [,b]) => b - a)
            .slice(0, limit)
        );
        topLocations = Object.fromEntries(
          Object.entries(cachedStats.topLocations)
            .sort(([,a], [,b]) => b - a)
            .slice(0, limit)
        );
        return;
      }

      const fetchFn = async () => {
        const res = await fetch(url, { signal });
        if (!res.ok) {
          throw new Error(`Failed to fetch incident stats: ${res.status} ${res.statusText}`);
        }
        return await res.json();
      };

      const stats = await retryWithBackoff(fetchFn, 3, 1000);

      // Cache the stats
      statsCache[cacheKey] = {
        data: stats,
        timestamp: Date.now()
      };

      // 🐛 DEBUG: Log the hourly data
      console.log('Hourly data received:', stats.hourlyData);
      console.log('Hourly data length:', stats.hourlyData?.length);
      console.log('Sample values:', stats.hourlyData?.slice(0, 10));
      console.log('Max value:', Math.max(...(stats.hourlyData || [0])));
      console.log('Sum of all values:', (stats.hourlyData || []).reduce((a, b) => a + b, 0));

eventsToday = stats.eventsToday;
        eventsLastHour = stats.eventsLastHour;
        eventsActive = stats.eventsActive;
        totalIncidents = stats.totalIncidents;
      hourlyData = stats.hourlyData || [];

    // Always limit to 6 items for both fresh and cached data
    const limit = 6;
    incidentsByType = Object.fromEntries(
      Object.entries(stats.incidentsByType)
        .sort(([,a], [,b]) => b - a)
        .slice(0, limit)
    );
    topLocations = Object.fromEntries(
      Object.entries(stats.topLocations)
        .sort(([,a], [,b]) => b - a)
        .slice(0, limit)
    );
    } catch (err) {
      if (err.name !== 'AbortError') {
        console.error("Error fetching incident stats:", err);
        addToast('Failed to load incident statistics.', 'error');
        // Set fallback values
        eventsToday = eventsToday || 0;
        eventsLastHour = eventsLastHour || 0;
        eventsActive = eventsActive || 0;
        totalIncidents = totalIncidents || 0;
        incidentsByType = incidentsByType || {};
        topLocations = topLocations || {};
      }
    } finally {
      statsController = null;
    }
  }

  async function likePost(postId) {
    const post = posts.find(p => p.id === postId);
    if (!post || post.liking) return;

    // Set liking state to prevent multiple requests
    posts = posts.map(p =>
      p.id === postId ? { ...p, liking: true } : p
    );

    // Store original like count for rollback
    const originalLikes = post.likes;
    const wasLiked = post.likes > 0;

    // Optimistic update: increment likes immediately
    posts = posts.map(p =>
      p.id === postId ? { ...p, likes: wasLiked ? 0 : 1, likeError: "", likeErrorAnimation: false } : p
    );

    try {
      const method = wasLiked ? 'DELETE' : 'POST';
      const fetchFn = async () => {
        const res = await fetch(`/api/incidents/${postId}/like`, { method });
        if (!res.ok) {
          throw new Error(`Failed to ${wasLiked ? 'unlike' : 'like'} post: ${res.status} ${res.statusText}`);
        }
        return await res.json();
      };

      const data = await retryWithBackoff(fetchFn, 2, 500);

      // Update with server response
      posts = posts.map(p =>
        p.id === postId ? { ...p, likes: data.likes, likeError: "", liking: false } : p
      );
    } catch (err) {
      console.error("Error updating like:", err);

      // For unliking, don't rollback on failure to allow users to unlike posts
      if (wasLiked) {
        // Keep the unliked state
        posts = posts.map(p =>
          p.id === postId ? { ...p, liking: false } : p
        );
      } else {
        // For liking, rollback on failure
        addToast('Failed to like post. Please try again.', 'error');
        posts = posts.map(p =>
          p.id === postId ? { ...p, likes: originalLikes, liking: false } : p
        );
      }
    }
  }

  function toggleComments(postId) {
    const now = Date.now();
    if (now - lastToggleTime < 200) return;
    lastToggleTime = now;
    posts = posts.map(post =>
      post.id === postId ? { ...post, showComments: !post.showComments } : post
    );
  }

  function sharePost(post) {
    const text = `${post.description} - Location: ${post.location}. Check out more traffic incidents at San Diego Traffic Watch!`;
    const url = window.location.origin;
    
    if (navigator.share) {
      navigator.share({
        title: 'San Diego Traffic Watch',
        text: text,
        url: url
      })
      .then(() => console.log('Successful share'))
      .catch((error) => console.log('Error sharing:', error));
    } else {
      const twitterUrl = `https://twitter.com/intent/tweet?text=${encodeURIComponent(text)}&url=${encodeURIComponent(url)}`;
      window.open(twitterUrl, '_blank');
    }
  }

  async function submitComment(postId) {
    const post = posts.find(p => p.id === postId);
    if (!post || post.newComment.trim() === "") return;

    const userComments = post.comments.filter(c => c.username === currentUsername);
    if (userComments.length >= 2) {
      addToast('You can only leave 2 comments per post.', 'warning');
      return;
    }

    const newCommentObj = {
      username: currentUsername,
      comment: post.newComment.trim(),
      timestamp: new Date().toISOString()
    };

    // Store original state for rollback
    const originalComments = [...post.comments];
    const originalNewComment = post.newComment;

    // Optimistic update: add comment immediately
    const optimisticComment = { ...newCommentObj, id: `temp-${Date.now()}` };
    posts = posts.map(p =>
      p.id === postId ? {
        ...p,
        comments: [...p.comments, optimisticComment],
        newComment: "",
        commentError: ""
      } : p
    );

    try {
      const fetchFn = async () => {
        const res = await fetch(`/api/incidents/${postId}/comment`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(newCommentObj)
        });
        if (!res.ok) {
          throw new Error(`Failed to submit comment: ${res.status} ${res.statusText}`);
        }
        return await res.json();
      };

      const data = await retryWithBackoff(fetchFn, 2, 500);

      // Update with server response
      posts = posts.map(p =>
        p.id === postId ? {
          ...p,
          comments: data.comments,
          newComment: "",
          commentError: ""
        } : p
      );
      addToast('Comment added successfully!', 'success');
    } catch (err) {
      console.error("Error submitting comment:", err);
      addToast('Failed to submit comment. Please try again.', 'error');

      // Rollback optimistic update
      posts = posts.map(p =>
        p.id === postId ? {
          ...p,
          comments: originalComments,
          newComment: originalNewComment,
          commentError: "Failed to submit comment"
        } : p
      );
    }
  }

  function getIconForIncidentType(type) {
  const types = {
    "Aircraft Emergency": "🛩️",
    "Animal Hazard": "🐾",
    "Assist CT with Maintenance": "🔧",
    "Road Closure": "🚧",
    "Car Fire": "🔥",
    "Construction": "🏗️",
    "Defective Traffic Signals": "🚦",
    "Fatality": "☠️",
    "Hit and Run No Injuries": "🚗💨",
    "JUMPER": "🧍‍♂️",
    "Live or Dead Animal": "🦌",
    "Maintenance": "🛠️",
    "Debris From Vehicle": "📦",
    "Provide Traffic Control": "🚓",
    "Report of Fire": "🔥",
    "Request CalTrans Notify": "📞",
    "Road Conditions": "🛣️",
    "SIG Alert": "📢",
    "SPINOUT": "↩️",
    "Traffic Break": "✋",
    "Traffic Collision": "🚘",
    "Traffic Hazard": "⚠️",
    "Wrong Way Driver": "↪️"
  };
  return types[type] || "🚨";
}


  function toggleDescription(postId) {
    posts = posts.map(post =>
      post.id === postId ? { ...post, showFullDescription: !post.showFullDescription } : post
    );
  }

  function truncateDescription(text, length = 150) {
    if (!text) return '';
    if (text.length <= 200) return text;

    // Find the last space within the character limit
    const lastSpaceIndex = text.lastIndexOf(' ', length);
    if (lastSpaceIndex === -1) return text.substring(0, length);

    // Return text up to the last complete word
    return text.substring(0, lastSpaceIndex);
  }

  function calculateNiceStepSize(data) {
    if (!data || data.length === 0) return 1;
    const max = Math.max(...data.filter(n => n > 0));
    if (max === 0) return 1;

    const targetSteps = 5;
    const approxStep = max / targetSteps;

    // Nice bases to choose from
    const niceNumbers = [1, 2, 5, 10];

    // Find magnitude
    const magnitude = Math.floor(Math.log10(approxStep));
    let scaledStep = approxStep / Math.pow(10, magnitude);

    // Find the nicest base
    let bestBase = 1;
    let minDiff = Math.abs(scaledStep - 1);
    for (const base of niceNumbers) {
      const diff = Math.abs(scaledStep - base);
      if (diff < minDiff) {
        minDiff = diff;
        bestBase = base;
      }
    }

    // If we went with 10, increase magnitude
    if (bestBase === 10) {
      return 10 * Math.pow(10, magnitude);
    }
    // For 5, 2, 1, use normal magnitude
    return Math.max(1, bestBase * Math.pow(10, magnitude));
  }

  // Chart.js functions
  function initializeChart() {
    if (!chartCanvas) {
      console.log('Canvas not ready yet');
      return;
    }

    if (!hourlyData || hourlyData.length === 0) {
      console.log('No hourly data yet');
      return;
    }

    // Destroy existing chart if it exists
    if (chartInstance) {
      chartInstance.destroy();
      chartInstance = null;
    }


    console.log('Initializing chart with data:', hourlyData);

    try {
      chartInstance = new ChartJS(chartCanvas.getContext('2d'), {
        type: 'line',
        data: {
          labels: chartLabels,
          datasets: [{
            label: 'Activity',
            data: hourlyData,
            borderColor: '#4ade80',
            backgroundColor: 'rgba(74, 222, 128, 0.2)',
            borderWidth: 3,
            fill: true,
            tension: 0.4,
            pointBackgroundColor: '#4ade80',
            pointBorderColor: '#ffffff',
            pointBorderWidth: 2,
            pointRadius: 4,
            pointHoverRadius: 6,
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: {
              display: false,
            },
            tooltip: {
              backgroundColor: 'rgba(0, 0, 0, 0.8)',
              titleColor: '#ffffff',
              bodyColor: '#ffffff',
              borderColor: 'rgba(255, 255, 255, 0.2)',
              borderWidth: 1,
              callbacks: {
                title: function(context) {
                  return `Time: ${context[0].label}`;
                },
                label: function(context) {
                  return `Incidents: ${context.parsed.y}`;
                }
              }
            }
          },
          scales: {
            x: {
              type: 'category',
              display: true,
              grid: {
                color: 'rgba(255, 255, 255, 0.1)',
              },
              ticks: {
                color: '#ffffff',
                font: {
                  size: 10
                },
                maxRotation: 45,
                minRotation: 45
              }
            },
            y: {
              type: 'linear',
              display: true,
              beginAtZero: true,
              grid: {
                color: 'rgba(255, 255, 255, 0.1)',
              },
              ticks: {
                color: '#ffffff',
                font: {
                  size: 10
                },
                stepSize: calculateNiceStepSize(hourlyData)
              }
            }
          },
          animation: {
            duration: 1000,
            easing: 'easeInOutQuad'
          }
        }
      });

      console.log('Chart initialized successfully');
    } catch (error) {
      console.error('Error initializing chart:', error);
    }
  }

  function updateChart() {
    if (!chartInstance || !chartCanvas) {
      initializeChart();
      return;
    }

    if (!hourlyData || hourlyData.length === 0) {
      return;
    }

    try {
      chartInstance.data.datasets[0].data = hourlyData;
      chartInstance.data.labels = chartLabels;
      chartInstance.options.scales.y.ticks.stepSize = calculateNiceStepSize(hourlyData);
      chartInstance.update(); // Enable smooth animation for chart transitions
    } catch (error) {
      console.error('Error updating chart:', error);
      initializeChart(); // Try to reinitialize if update fails
    }
  }

  // Reactive statement to update chart when data changes
  $: if (hourlyData && hourlyData.length > 0 && chartCanvas) {
    updateChart();
  }

  // Cleanup chart instance when incident stats tab is closed
  $: if (!showEventCounters && chartInstance) {
    chartInstance.destroy();
    chartInstance = null;
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

    // Calculate horizontal and vertical distance
    const diffX = touchStartX - touchEndX;
    const diffY = touchEndY - touchStartY;

    // Check for pull-to-refresh (vertical pull at top of scroll)
    if (diffY > 0 && window.scrollY === 0 && !isPulling) {
      isPulling = true;
      pullDistance = Math.min(diffY * 0.5, 120); // Dampen the pull
      e.preventDefault();
      return;
    }

    if (isPulling) {
      pullDistance = Math.min(diffY * 0.5, 120);
      e.preventDefault();
      return;
    }

    // Only show swipe indicator for primarily horizontal movements
    if (Math.abs(diffX) > 20 && Math.abs(diffY) < verticalThreshold) {
      swipeIndicator = true;
      swipeDirection = diffX > 0 ? 'left' : 'right';

      // Prevent scrolling when a valid swipe is detected
      if (Math.abs(diffX) > 40) {
        e.preventDefault();
      }
    } else {
      swipeIndicator = false;
    }
  }
  
  function handleTouchEnd(e) {
    if (!swipeInProgress) return;

    // Handle pull-to-refresh
    if (isPulling && pullDistance >= pullThreshold && !refreshing) {
      refreshing = true;
      addToast('Refreshing...', 'info');
      // Trigger refresh
      fetchIncidents();
      fetchIncidentStats();
      setTimeout(() => {
        refreshing = false;
        addToast('Refreshed!', 'success');
      }, 1000);
    }

    // Calculate horizontal and vertical distance
    const diffX = touchStartX - touchEndX;
    const diffY = Math.abs(touchStartY - touchEndY);

    // Only process as swipe if movement was primarily horizontal
    if (Math.abs(diffX) > swipeThreshold && diffY < verticalThreshold) {
      if (diffX > 0) {
        // Swipe left - go to table view
        if (!condensedView) condensedView = true;
        // Haptic feedback
        if (navigator.vibrate) navigator.vibrate(50);
      } else {
        // Swipe right - go to card view
        if (condensedView) condensedView = false;
        // Haptic feedback
        if (navigator.vibrate) navigator.vibrate(50);
      }
    }

    // Reset
    swipeInProgress = false;
    swipeIndicator = false;
    isPulling = false;
    pullDistance = 0;
  }

  onMount(() => {
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    const storedMode = localStorage.getItem('darkMode');
    darkMode = storedMode ? storedMode === 'true' : prefersDark;
    document.body.classList.toggle('dark-mode', darkMode);

    currentUsername = localStorage.getItem('username') || generateRandomUsername();
    if (!localStorage.getItem('username')) {
      localStorage.setItem('username', currentUsername);
    }

    // Add network status listeners
    window.addEventListener('online', updateOnlineStatus);
    window.addEventListener('offline', updateOnlineStatus);
    updateOnlineStatus(); // Initial check

    fetchIncidents();
    fetchIncidentStats(); // Fetch stats on mount

    // Refresh at a reasonable interval
    const refreshInterval = setInterval(() => {
      if (isOnline) {
        fetchIncidentStats(); // Refresh stats periodically
        fetchIncidents(); // Also refresh incidents periodically
      }
    }, 60000); // Every 1 minute

    // Attach scroll listener to the window
    window.addEventListener('scroll', debouncedHandleScroll);

    // Add touch event listeners for swipe detection and pull-to-refresh on the scroll container
    if (scrollContainer) {
      scrollContainer.addEventListener('touchstart', handleTouchStart, { passive: true });
      scrollContainer.addEventListener('touchmove', handleTouchMove, { passive: false });
      scrollContainer.addEventListener('touchend', handleTouchEnd, { passive: true });
    }


    onDestroy(() => {
      clearInterval(refreshInterval);
      // Remove network listeners
      window.removeEventListener('online', updateOnlineStatus);
      window.removeEventListener('offline', updateOnlineStatus);
      // Remove scroll listener from the window
      window.removeEventListener('scroll', debouncedHandleScroll);

      // Remove touch event listeners
      if (scrollContainer) {
        scrollContainer.removeEventListener('touchstart', handleTouchStart);
        scrollContainer.removeEventListener('touchmove', handleTouchMove);
        scrollContainer.removeEventListener('touchend', handleTouchEnd);
      }
    });
  });
</script>

<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">
<div class="container" bind:this={scrollContainer}> <!-- Removed on:scroll from here -->
  <div class="header">
    <button class="header-content" on:click={toggleDarkMode} type="button">
      <h1>San Diego Traffic Watch</h1>
      <p>Real-time incidents from CHP scanner data</p>
    </button>
    <button class="collapse-button" on:click={toggleEventCounters} aria-expanded={showEventCounters}>
      Incident Stats
      <span class="arrow-icon" class:rotated={showEventCounters}></span>
    </button>
    {#if showEventCounters}
      <div class="event-counters" transition:slide>
        <div class="time-period-section">
          <span class="section-label">Time Period</span>
          <div class="time-buttons">
            <button class="time-button {timeFilter === 'day' ? 'active' : ''}" on:click={() => setTimeFilter('day')}>1 Day</button>
            <button class="time-button {timeFilter === 'week' ? 'active' : ''}" on:click={() => setTimeFilter('week')}>Week</button>
            <button class="time-button {timeFilter === 'month' ? 'active' : ''}" on:click={() => setTimeFilter('month')}>Month</button>
            <button class="time-button {timeFilter === 'year' ? 'active' : ''}" on:click={() => setTimeFilter('year')}>Year</button>
          </div>
        </div>
        <div class="top-row">
          <div class="stats-grid">
            <div class="stat-card">
              <span class="stat-icon">📅</span>
              <span class="stat-value">{eventsToday}</span>
              <span class="stat-label">Events Today</span>
            </div>
            <div class="stat-card">
              <span class="stat-icon">🕒</span>
              <span class="stat-value">{eventsLastHour}</span>
              <span class="stat-label">Events Last Hour</span>
            </div>
            <div class="stat-card clickable {showActiveOnly ? 'active' : ''}" on:click={toggleActiveOnly} role="button" tabindex="0" on:keydown={(e) => e.key === 'Enter' && toggleActiveOnly()}>
              <span class="stat-icon">⚡</span>
              <span class="stat-value">{eventsActive}</span>
              <span class="stat-label">Active Events</span>
            </div>
            <div class="stat-card">
              <span class="stat-icon">📊</span>
              <span class="stat-value">{totalIncidents}</span>
              <span class="stat-label">Total Incidents</span>
            </div>
          </div>
        </div>
        <div class="activity-chart-section">
          <div class="activity-header">
            <span class="section-title">{sectionTitle}</span>
          </div>
          <div class="activity-chart-container">
            <div class="mini-chart">
              <canvas bind:this={chartCanvas} width="288" height="120"></canvas>
            </div>
          </div>
        </div>
        <div class="incident-breakdown-grid">
          <div class="breakdown-card">
            <div class="breakdown-header">
              <span class="breakdown-icon">🚨</span>
              <span class="breakdown-title">Incidents by Type</span>
            </div>
            <div class="breakdown-list">
              {#each Object.entries(incidentsByType) as [type, count], i}
                <div
                  class="breakdown-item"
                  style="animation-delay: {i * 50}ms"
                  in:fly="{{ y: 20, duration: 400 }}"
                >
                  <div
                    class="breakdown-item-bar"
                    style="width: {Math.max((count / Math.max(...Object.values(incidentsByType))) * 80, 8)}%"
                  ></div>
                  <span class="breakdown-item-label">{type}</span>
                  <span class="breakdown-item-count">{count}</span>
                </div>
              {/each}
            </div>
          </div>
          <div class="breakdown-card">
            <div class="breakdown-header">
              <span class="breakdown-icon">📍</span>
              <span class="breakdown-title">Top Locations</span>
            </div>
            <div class="breakdown-list">
              {#each Object.entries(topLocations) as [location, count], i}
                <div
                  class="breakdown-item"
                  style="animation-delay: {i * 50}ms"
                  in:fly="{{ y: 20, duration: 400 }}"
                >
                  <div
                    class="breakdown-item-bar"
                    style="width: {Math.max((count / Math.max(...Object.values(topLocations))) * 80, 8)}%"
                  ></div>
                  <span class="breakdown-item-label">{location}</span>
                  <span class="breakdown-item-count">{count}</span>
                </div>
              {/each}
            </div>
          </div>
        </div>
      </div>
    {/if}
  </div>
  
  <style>
    .filter-active {
      padding: 0px 4px;
      border-radius: 6px;
      box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
      transition: all 0.3s ease; /* Smooth transition for changes */
    }
    .stats-grid {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 0;
      margin: 0 0 0.5rem 0;
      width: 100%;
    }
    .stat-card {
      background: rgba(255, 255, 255, 0.1);
      border: 1px solid rgba(255, 255, 255, 0.2);
      border-radius: 10px;
      padding: 0.4rem;
      text-align: center;
      backdrop-filter: blur(8px);
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1), 0 1px 4px rgba(0, 0, 0, 0.1);
      transition: all 0.3s ease;
      width: 100%;
      box-sizing: border-box;
      display: flex;
      flex-direction: column;
      justify-content: center;
      min-height: 80px;
    }
    .stat-card:hover {
      transform: translateY(-1px);
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
    }
    .stat-card.clickable {
      cursor: pointer;
      border-color: rgba(255, 255, 255, 0.3);
    }
    .stat-card.clickable:hover {
      background: rgba(255, 255, 255, 0.15);
    }
    .stat-card.active {
      background: #c13117;
      border-color: #c13117;
      transform: translateY(-1px);
      box-shadow: 0 4px 12px rgba(193, 49, 23, 0.4);
      animation: cardPulse 2s infinite;
    }
    @keyframes cardPulse {
      0%, 100% { box-shadow: 0 4px 12px rgba(193, 49, 23, 0.4); }
      50% { box-shadow: 0 4px 12px rgba(193, 49, 23, 0.6), 0 0 0 8px rgba(193, 49, 23, 0); }
    }
    .stat-icon {
      font-size: 1.3rem;
      margin-bottom: 0.3rem;
      display: block;
    }
    .stat-value {
      font-size: 1.3rem;
      font-weight: 800;
      margin-bottom: 0.2rem;
      display: block;
    }
  .stat-label {
    font-size: 0.7rem;
    opacity: 0.8;
    display: block;
    font-weight: 600;
  }

  .time-period-section {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    padding: 0.25rem;
    background: rgba(255, 255, 255, 0.08);
    border: 1px solid rgba(255, 255, 255, 0.15);
    border-radius: 12px;
    backdrop-filter: blur(8px);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  }
  .section-label {
    font-size: 0.9rem;
    font-weight: 600;
    opacity: 0.9;
    margin-bottom: 0.75rem;
    color: white;
  }
  .time-buttons {
    display: flex;
    gap: 0.5rem;
    flex-wrap: wrap;
  }
  .time-button {
    background: rgba(255, 255, 255, 0.1);
    border: 1px solid rgba(255, 255, 255, 0.2);
    color: white;
    padding: 0.5rem 0.75rem;
    border-radius: 8px;
    font-size: 0.85rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;
  }
  .time-button:hover {
    background: rgba(255, 255, 255, 0.2);
  }
  .time-button.active {
    background: rgba(74, 222, 128, 0.6);
    border-color: rgba(74, 222, 128, 0.6);
  }

  .activity-chart-section {
    margin-top: 0.5rem;
    padding: 0.4rem;
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.15);
    border-radius: 12px;
    backdrop-filter: blur(10px);
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1);
  }
  .activity-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 0.5rem;
  }
  .section-title {
    font-size: 1rem;
    font-weight: 700;
    color: white;
    text-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
  }
  .total-badge {
    background: rgba(74, 222, 128, 0.2);
    color: #22c55e;
    padding: 0.25rem 0.75rem;
    border-radius: 20px;
    font-size: 0.85rem;
    font-weight: 600;
    border: 1px solid rgba(74, 222, 128, 0.3);
    backdrop-filter: blur(8px);
  }
  .activity-chart-container {
    position: relative;
  }

  .incident-breakdown-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.5rem;
    margin-top: 1rem;
  }

  .breakdown-card {
    background: rgba(255, 255, 255, 0.05);
    border: 2px solid rgba(255, 255, 255, 0.15);
    border-radius: 12px;
    padding: 0.75rem;
    backdrop-filter: blur(10px);
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1);
    transition: all 0.3s ease;
  }

  .breakdown-card:hover {
    transform: translateY(-1px);
    box-shadow: 0 6px 20px rgba(0, 0, 0, 0.14);
  }

  .breakdown-header {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-bottom: 0.75rem;
  }

  .breakdown-icon {
    font-size: 1.2rem;
    width: 24px;
    height: 24px;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .breakdown-title {
    font-size: 0.8rem;
    font-weight: 700;
    color: white;
    text-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
    margin: 0;
  }

  .breakdown-list {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }

  .breakdown-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    position: relative;
    padding: 0rem;
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.3s ease;
    min-height: 40px;
    overflow: hidden;
  }

  .breakdown-item:hover {
    transform: translateY(-1px);
    background: rgba(255, 255, 255, 0.08);
    border-color: rgba(255, 255, 255, 0.2);
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
  }

  .breakdown-item-bar {
    position: absolute;
    left: 0;
    top: 0;
    height: 100%;
    background: rgba(74, 222, 128, 0.6);
    border-radius: inherit;
    transition: width 0.8s cubic-bezier(0.4, 0, 0.2, 1);
    z-index: 0;
    opacity: 1;
  }

  .breakdown-item-label {
    flex: 1;
    font-size: 0.8rem;
    font-weight: 600;
    color: white;
    margin-right: 0.5rem;
    z-index: 1;
    line-height: 1.3;
  }

  .breakdown-item-count {
    background: rgba(74, 222, 128, 0.3);
    color: #ffffff;
    padding: 0.25rem 0.5rem;
    margin-right: 0.25rem;
    border-radius: 12px;
    font-size: 0.7rem;
    font-weight: 700;
    border: 1px solid rgba(74, 222, 128, 0.25);
    backdrop-filter: blur(6px);
    z-index: 1;
    white-space: nowrap;
  }

  @media (max-width: 768px) {
    .top-row {
      flex-direction: column;
    }

    .stats-grid {
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 0;
    }

    .time-period-section {
      min-width: 100%;
    }

    .activity-chart-section {
      padding: 0.3rem;
    }
    .activity-header {
      flex-direction: column;
      align-items: flex-start;
      gap: 0.5rem;
      margin-bottom: 0.3rem;
    }
    .incident-breakdown-grid {
      grid-template-columns: 1fr;
      gap: 0.75rem;
      margin-top: 1rem;
    }
    .breakdown-card {
      padding: 0.75rem;
    }
    .breakdown-title {
      font-size: 0.9rem;
    }
    .breakdown-icon {
      font-size: 1.1rem;
      width: 20px;
      height: 20px;
    }
    .breakdown-header {
      margin-bottom: 0.5rem;
    }
    .breakdown-list {
      gap: 0.2rem;
    }
  }

  @media (max-width: 480px) {
    .event-counters {
      gap: 0.4rem;
      margin-top: 0.4rem;
      padding-top: 0.4rem;
    }
    .stats-grid {
      gap: 0;
    }
    .stat-card {
      padding: 0.25rem;
      border-radius: 8px;
      min-height: 80px;
    }
    .stat-value {
      font-size: 1.2rem;
    }
    .stat-icon {
      font-size: 1.1rem;
      margin-bottom: 0.2rem;
    }
    .stat-label {
      font-size: 0.6rem;
    }
    .time-period-section {
      padding: 0.2rem;
    }
    .section-label {
      font-size: 0.8rem;
      margin-bottom: 0.5rem;
    }
    .time-button {
      padding: 0.4rem 0.6rem;
      font-size: 0.8rem;
    }
    .activity-chart-section {
      margin-top: 0.3rem;
      padding: 0.3rem;
      border-radius: 10px;
    }
    .section-title {
      font-size: 0.9rem;
    }
    .incident-breakdown-grid {
      gap: 0.5rem;
      margin-top: 0.8rem;
    }
    .breakdown-card {
      padding: 0.6rem;
      border-radius: 10px;
    }
    .breakdown-item {
      padding: 0rem;
      min-height: 36px;
      border-radius: 6px;
    }
    .breakdown-item-label {
      font-size: 0.75rem;
      margin-right: 0.3rem;
    }
    .breakdown-item-count {
      font-size: 0.65rem;
      padding: 0.2rem 0.4rem;
    }
    .breakdown-title {
      font-size: 0.8rem;
    }
    .breakdown-header {
      gap: 0.4rem;
      margin-bottom: 0.4rem;
    }
  }
  </style>
  
  <div class="view-controls">
    <button 
      class="view-toggle-button" 
      on:click={() => condensedView = !condensedView}
      aria-label={condensedView ? "Expand to card view" : "Condense to table view"}
      aria-checked={condensedView}
      role="switch"
      tabindex="0"
      on:keydown={(e) => e.key === 'Enter' && (condensedView = !condensedView)}
    >
      <span class="toggle-icon">{condensedView ? "🔍" : "📋"}</span>
      <span class="toggle-text">{condensedView ? "Expand View" : "Condense View"}</span>
      <span class="toggle-description">{condensedView ? "Show details" : "Show as table"}</span>
      <span class="toggle-state" aria-hidden="true">
        <span class="toggle-indicator"></span>
      </span>
    </button>
  </div>
  
  <button 
    class="side-toggle" 
    class:condensed={condensedView}
    on:click={() => condensedView = !condensedView}
    aria-label={condensedView ? "Expand to card view" : "Condense to table view"}
  >
    <span class="side-toggle-arrow">{condensedView ? "→" : "←"}</span>
    <span class="side-toggle-text">{condensedView ? "Cards" : "Table"}</span>
  </button>
  
  {#if swipeIndicator}
    <div class="swipe-indicator {swipeDirection}" in:fade={{ duration: 100 }}>
      <span class="swipe-arrow">{swipeDirection === 'left' ? '👈' : '👉'}</span>
      <span class="swipe-text">{swipeDirection === 'left' ? 'Table View' : 'Card View'}</span>
    </div>
  {/if}

  <!-- Pull-to-refresh indicator -->
  {#if isPulling || refreshing}
    <div class="pull-refresh-indicator {refreshing ? 'refreshing' : ''}" style="transform: translateX(-50%) translateY({isPulling ? pullDistance : 0}px)">
      {#if refreshing}
        <span>🔄 Refreshing...</span>
      {:else}
        <span>⬇️ Pull to refresh</span>
      {/if}
    </div>
  {/if}
  
  {#if loading && posts.length === 0}
    <div class="loading-container" in:fade={{ duration: 150 }}>
      {#each Array(6) as _}
        <div class="skeleton-card" in:fade={{ duration: 150, delay: 50 }}>
          <div class="skeleton-image"></div>
          <div class="skeleton-content">
            <div class="skeleton-line skeleton-title"></div>
            <div class="skeleton-line skeleton-text"></div>
            <div class="skeleton-line skeleton-text"></div>
            <div class="skeleton-actions">
              <div class="skeleton-button"></div>
              <div class="skeleton-button"></div>
              <div class="skeleton-button"></div>
            </div>
          </div>
        </div>
      {/each}
    </div>
  {:else if posts.length === 0}
    <div class="empty-state" in:fade={{ duration: 150 }}>
      <div class="empty-icon">🔍</div>
      <p>No incidents to display at the moment.</p>
      <p>Check back soon for updates.</p>
    </div>
  {:else if condensedView}
    <div class="incidents-table" in:fade={{ duration: 200 }}>
      <div class="table-header">
        <div class="table-cell type-cell">Type</div>
        <div class="table-cell time-cell">Time</div>
        <div class="table-cell location-cell">Location</div>
        <div class="table-cell status-cell">Status</div>
      </div>
      
      {#each posts as post, i (post.compositeId)}
        <div 
          class="table-row" 
          class:active={post.active}
          class:expanded={expandedPostId === post.id}
          on:click={() => {
            // If closing the currently expanded row and its comments are open, close comments first
            if (expandedPostId === post.id && post.showComments) {
              posts = posts.map(p => p.id === post.id ? { ...p, showComments: false } : p);
            }
            // Toggle expanded state
            expandedPostId = expandedPostId === post.id ? null : post.id;
          }}
          in:slide={{ delay: Math.min(i * 30, 300), duration: 150 }}
        >
          <div class="table-cell type-cell">
            <span class="incident-icon-small">{getIconForIncidentType(post.type)}</span>
            <span class="incident-type-small">{post.type}</span>
          </div>
          <div class="table-cell time-cell">
            <span class="full-time">{post.time}</span>
            <span class="mobile-time">{formatTimeOnly(post.timestamp)}</span>
          </div>
          <div class="table-cell location-cell">{post.location}</div>
          <div class="table-cell status-cell">
            {#if post.active}
              <span class="status-badge active">Active</span>
            {:else}
              <span class="status-badge">Inactive</span>
            {/if}
          </div>
        </div>
        
        {#if expandedPostId === post.id}
          <div class="expanded-details" transition:slide={{ duration: 200 }}>
            <div class="expanded-content">
              <div class="expanded-image">
                <img src={post.image} alt="Incident location map" loading="lazy" />
              </div>
              <div class="expanded-info">
                <div class="post-description">
                  {#if post.description}
                    {post.showFullDescription ? post.description : truncateDescription(post.description)}
                    {#if post.description.length > 200}
                      <button class="more-button" on:click={(e) => {
                        e.stopPropagation();
                        toggleDescription(post.id);
                      }}>
                        {post.showFullDescription ? 'less' : 'more'}
                      </button>
                    {/if}
                  {:else}
                    No description available.
                  {/if}
                </div>
                <div class="expanded-actions">
                  <button 
                    class="action-button like-button" 
                    class:liked={post.likes > 0}
                    class:like-error={post.likeErrorAnimation}
                    on:click={(e) => {
                      e.stopPropagation();
                      likePost(post.id);
                    }}
                  >
                    <span class="button-icon">❤️</span>
                    <span>{post.likes > 0 ? post.likes : 'Like'}</span>
                  </button>
                  <button class="action-button comment-button" on:click={(e) => {
                    e.stopPropagation();
                    toggleComments(post.id);
                  }}>
                    <span class="button-icon">💬</span>
                    <span>{post.comments.length > 0 ? post.comments.length : 'Comment'}</span>
                  </button>
                  <button class="action-button share-button" on:click={(e) => {
                    e.stopPropagation();
                    sharePost(post);
                  }}>
                    <span class="button-icon">🔗</span>
                    <span>Share</span>
                  </button>
                </div>
              </div>
            </div>
            
            {#if post.showComments}
              <div
                class="table-comments-overlay"
                in:fly="{{ y: 200, duration: 300 }}"
                out:fly="{{ y: 200, duration: 200 }}"
              >
                <button class="close-comments" on:click={(e) => {
                  e.stopPropagation();
                  toggleComments(post.id);
                }}>×</button>
                <h3 class="comments-title">Comments ({post.comments.length})</h3>
                {#if post.commentError}
                  <p class="error-message">{post.commentError}</p>
                {/if}
                <div class="comments-container">
                  {#if post.comments.length === 0}
                    <p class="no-comments">Be the first to comment!</p>
                  {:else}
                    {#each post.comments as comment, i}
                      <div class="comment" style="animation-delay: {i * 20}ms">
                        <div class="comment-header">
                          <div class="comment-avatar">👤</div>
                          <div class="comment-user-info">
                            <span class="comment-username">{comment.username}</span>
                            <span class="comment-timestamp">{formatCommentTimestamp(comment.timestamp)}</span>
                          </div>
                        </div>
                        <div class="comment-content">
                          {comment.comment}
                        </div>
                      </div>
                    {/each}
                  {/if}
                </div>
                <div class="add-comment">
                  <input
                    type="text"
                    bind:value={post.newComment}
                    placeholder="Write a comment..."
                    maxlength="150"
                    on:keypress={(e) => e.key === 'Enter' && submitComment(post.id)}
                  />
                  <button on:click={(e) => {
                    e.stopPropagation();
                    submitComment(post.id);
                  }}>Send</button>
                </div>
              </div>
            {/if}
          </div>
        {/if}
      {/each}

      {#if !allPostsLoaded && posts.length > 0 && posts.length >= postsPerPage}
        <div class="scroll-indicator" in:fade={{ duration: 150 }} on:click={forceLoadMore} role="button" tabindex="0" on:keydown={(e) => e.key === 'Enter' && forceLoadMore()}>
          <div class="scroll-dots">
            <span class="dot"></span>
            <span class="dot"></span>
            <span class="dot"></span>
          </div>
          <p>More incidents available</p>
        </div>
      {/if}
    </div>
  {:else}
    <div class="feed">
      {#each posts as post, i (post.compositeId)}
        <div
          class="post"
          class:active={post.active}
          in:slide={{ delay: Math.min(i % postsPerPage * 50, 300), duration: 200 }}
          animate:flip={{ duration: 200 }}
        >
          <div class="post-content">
            <div class="post-image-container">
              <div class="post-badge">
                <span class="incident-icon">{getIconForIncidentType(post.type)}</span>
                <span class="incident-type">{post.type}</span>
              </div>
              {#if post.active}
                <div class="active-badge">
                  <span class="active-icon">⚡</span>
                  <span>Active</span>
                </div>
              {/if}
              <img src={post.image} alt="Incident location map" class="post-image" loading="lazy" />
            </div>
            
            <div class="post-info">
              <div class="post-header">
                <span class="post-time">{post.time}</span>
                <span class="post-location">{post.location}</span>
              </div>
              <div class="post-description">
                {#if post.description}
                  {post.showFullDescription ? post.description : truncateDescription(post.description)}
                  {#if post.description.length > 200}
                    <button class="more-button" on:click={() => toggleDescription(post.id)}>
                      {post.showFullDescription ? 'less' : 'more'}
                    </button>
                  {/if}
                {:else}
                  No description available.
                {/if}
              </div>
              <div class="post-actions">
                <button 
                  class="action-button like-button" 
                  class:liked={post.likes > 0}
                  class:like-error={post.likeErrorAnimation}
                  on:click={() => likePost(post.id)}
                >
                  <span class="button-icon">❤️</span>
                  <span>{post.likes > 0 ? post.likes : 'Like'}</span>
                </button>
                <button class="action-button comment-button" on:click={() => toggleComments(post.id)}>
                  <span class="button-icon">💬</span>
                  <span>{post.comments.length > 0 ? post.comments.length : 'Comment'}</span>
                </button>
                <button class="action-button share-button" on:click={() => sharePost(post)}>
                  <span class="button-icon">🔗</span>
                  <span>Share</span>
                </button>
              </div>

              {#if post.showComments}
                <div
                  class="comments-overlay"
                  in:fly="{{ y: 200, duration: 300 }}"
                  out:fly="{{ y: 200, duration: 200 }}"
                >
                  <button class="close-comments" on:click={() => toggleComments(post.id)}>×</button>
                  <h3 class="comments-title">Comments ({post.comments.length})</h3>
                  {#if post.commentError}
                    <p class="error-message">{post.commentError}</p>
                  {/if}
                  <div class="comments-container">
                    {#if post.comments.length === 0}
                      <p class="no-comments">Be the first to comment!</p>
                    {:else}
                      {#each post.comments as comment, i}
                        <div class="comment" style="animation-delay: {i * 20}ms">
                          <div class="comment-header">
                            <div class="comment-avatar">👤</div>
                            <div class="comment-user-info">
                              <span class="comment-username">{comment.username}</span>
                              <span class="comment-timestamp">{formatCommentTimestamp(comment.timestamp)}</span>
                            </div>
                          </div>
                          <div class="comment-content">
                            {comment.comment}
                          </div>
                        </div>
                      {/each}
                    {/if}
                  </div>
                  <div class="add-comment">
                    <input
                      type="text"
                      bind:value={post.newComment}
                      placeholder="Write a comment..."
                      maxlength="150"
                      on:keypress={(e) => e.key === 'Enter' && submitComment(post.id)}
                    />
                    <button on:click={() => submitComment(post.id)}>Send</button>
                  </div>
                </div>
              {/if}
            </div>
          </div>
        </div>
      {/each}
      
      {#if !allPostsLoaded && posts.length > 0 && posts.length >= postsPerPage}
        <div class="scroll-indicator" in:fade={{ duration: 150 }} on:click={forceLoadMore} role="button" tabindex="0" on:keydown={(e) => e.key === 'Enter' && forceLoadMore()}>
          <div class="scroll-dots">
            <span class="dot"></span>
            <span class="dot"></span>
            <span class="dot"></span>
          </div>
          <p>More incidents available</p>
        </div>
      {/if}
    </div>
  {/if}
  
  <!-- Toast notifications -->
  {#if toasts.length > 0}
    <div class="toast-container">
      {#each toasts as toast (toast.id)}
        <div
          class="toast toast-{toast.type}"
          in:fly="{{ y: -50, duration: 300 }}"
          out:fly="{{ y: -50, duration: 200 }}"
        >
          <span class="toast-message">{toast.message}</span>
          <button class="toast-close" on:click={() => removeToast(toast.id)}>×</button>
        </div>
      {/each}
    </div>
  {/if}

  <footer class="app-footer" in:fade={{ delay: 400, duration: 200 }}>
    <p>Created and Developed by <a href="https://github.com/DuffyAdams" target="_blank" rel="noopener noreferrer">Duffy Adams</a></p>
  </footer>
</div>

<style>
  :global(html), :global(body) {
    margin: 0;
    padding: 0;
    overflow-x: hidden;
    width: 100%;
    max-width: 100%;
    position: relative;
  }
  :global(body) {
    font-family: 'Inter', 'Segoe UI', system-ui, -apple-system, sans-serif;
    transition: background-color 0.3s, color 0.3s;
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

  .filter-active {
    color: #c13117 !important; /* Red color for active filter */
    font-weight: bold;
  }

  .toggle-switch {
    position: relative;
    display: inline-flex;
    background: rgba(255, 255, 255, 0.15);
    border-radius: 24px;
    padding: 4px;
    border: none;
    cursor: pointer;
    transition: background 0.3s ease;
    overflow: hidden;
  }

  .toggle-switch:hover {
    background: rgba(255, 255, 255, 0.2);
  }

  .toggle-option {
    position: relative;
    padding: 6px 16px;
    font-size: 0.85rem;
    font-weight: 600;
    color: rgba(255, 255, 255, 0.6);
    transition: color 0.3s ease;
    z-index: 2;
    user-select: none;
  }

  .toggle-option.active {
    color: rgba(26, 32, 44, 0.9);
  }

  :global(body.dark-mode) .toggle-option.active {
    color: white;
  }

  .toggle-slider {
    position: absolute;
    top: 4px;
    left: 4px;
    width: calc(50% - 4px);
    height: calc(100% - 8px);
    background: rgba(255, 255, 255, 0.15);
    border-radius: 20px;
    transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
    z-index: 1;
  }

  :global(body.dark-mode) .toggle-slider {
    background: rgba(255, 255, 255, 0.05);
  }

  .toggle-slider.daily {
    transform: translateX(100%);
  }

  .counter-item.toggle-item {
    align-items: center;
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
    overflow-x: hidden;
    position: relative;
  }
  .header {
    text-align: center;
    margin-bottom: 1.5rem;
    padding: 1.5rem;
    background: linear-gradient(135deg, var(--primary-color), var(--primary-dark));
    color: white;
    border-radius: 16px;
    box-shadow: 0 10px 25px -5px rgba(var(--primary-dark), 0.1), 0 10px 10px -5px rgba(var(--primary-dark), 0.04);
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
    background: radial-gradient(circle, rgba(255,255,255,0.1) 0%, rgba(255,255,255,0) 60%);
    opacity: 0.6;
    transform: rotate(30deg);
    pointer-events: none;
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
    text-shadow: 0 1px 2px rgba(0,0,0,0.1);
  }
  .header p {
    margin: 0;
    font-size: 1.1rem;
    opacity: 0.9;
    font-weight: 500;
  }
  .event-counters {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    margin-top: 0.5rem;
    padding-top: 0.5rem;
    border-top: 1px solid rgba(255, 255, 255, 0.2);
    position: relative;
    z-index: 1;
  }

  .top-row {
    display: flex;
    gap: 1rem;
    align-items: stretch;
  }

  .stats-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: .25rem;
    flex: 1;
  }

  .stat-card {
    background: rgba(255, 255, 255, 0.1);
    border: 1px solid rgba(255, 255, 255, 0.2);
    border-radius: 12px;
    text-align: center;
    backdrop-filter: blur(8px);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1), 0 2px 8px rgba(0, 0, 0, 0.1);
    transition: all 0.3s ease;
    display: flex;
    flex-direction: column;
    justify-content: center;
    min-height: 80px;
    flex: 1;
    min-width: 0;
  }

  .time-period-section {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 0.8rem;
    background: rgba(255, 255, 255, 0.1);
    border: 1px solid rgba(255, 255, 255, 0.2);
    border-radius: 12px;
    backdrop-filter: blur(8px);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
    min-width: 200px;
    gap: 0.5rem;
  }

  .section-label {
    font-size: 0.9rem;
    font-weight: 600;
    opacity: 0.9;
    color: white;
    white-space: nowrap;
  }
  .collapse-button {
    background: none;
    border: none;
    color: white;
    font-size: 0.9rem;
    font-weight: 600;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.5rem;
    margin: 0.5rem auto 0;
    padding: 0.5rem 1rem;
    border-radius: 20px;
    transition: background-color 0.2s, transform 0.2s;
    opacity: 0.8;
  }
  .collapse-button:hover {
    opacity: 1;
    background-color: rgba(255, 255, 255, 0.1);
    transform: translateY(-1px);
  }
  .collapse-button:active {
    transform: translateY(0);
  }
  .arrow-icon {
    display: inline-block;
    width: 0;
    height: 0;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 5px solid white;
    transition: transform 0.3s ease;
  }
  .arrow-icon.rotated {
    transform: rotate(180deg);
  }
  .counter-item {
    text-align: center;
    color: white;
    font-size: 1rem;
    font-weight: 600;
    display: flex;
    flex-direction: column;
    align-items: center;
    flex-shrink: 0;
    min-width: 140px;
  }

  .combined-stats {
    flex-direction: row !important;
    gap: 1rem;
    align-items: stretch;
  }

  .stats-column {
    flex: 0 0 50%;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
  }
  .type-breakdown, .location-breakdown {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
    margin-top: 0.5rem;
    font-size: 0.8rem;
    font-weight: 500;
    min-height: 120px;
  }
  .type-item, .location-item {
    background-color: rgba(255, 255, 255, 0.1);
    padding: 0.25rem 0.5rem;
    border-radius: 4px;
    text-align: center;
  }
  .counter-label {
    font-size: 0.8rem;
    opacity: 0.8;
    margin-bottom: 0.2rem;
    text-align: center;
    width: 100%;
  }
  .counter-value {
    font-size: 1.5rem;
    font-weight: 800;
    text-shadow: 0 1px 2px rgba(0,0,0,0.1);
  }
  .loading-container {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
    gap: 1.5rem;
    padding: 2rem;
    max-width: 1200px;
    margin: 0 auto;
  }
  .skeleton-card {
    background: var(--card-bg);
    border-radius: 18px;
    box-shadow: 0 4px 20px var(--shadow-color), 0 0 0 1px rgba(0,0,0,0.03);
    overflow: hidden;
    animation: skeleton-pulse 1.5s ease-in-out infinite;
    flex: 0 0 calc(33.333% - 1.5rem);
    min-width: 300px;
    max-width: 400px;
    box-sizing: border-box;
    margin-bottom: 2rem;
  }
  .skeleton-image {
    height: 200px;
    background: linear-gradient(90deg, var(--border-color) 25%, transparent 50%, var(--border-color) 75%);
    background-size: 200% 100%;
    animation: skeleton-shimmer 1.5s infinite;
  }
  .skeleton-content {
    padding: 1.4rem;
  }
  .skeleton-line {
    height: 16px;
    background: var(--border-color);
    border-radius: 8px;
    margin-bottom: 0.8rem;
  }
  .skeleton-title {
    width: 60%;
    height: 20px;
  }
  .skeleton-text {
    width: 100%;
  }
  .skeleton-actions {
    display: flex;
    justify-content: space-between;
    margin-top: 1rem;
  }
  .skeleton-button {
    width: 60px;
    height: 32px;
    background: var(--border-color);
    border-radius: 8px;
  }
  .skeleton-card-small {
    display: flex;
    align-items: center;
    background: var(--card-bg);
    border-radius: 12px;
    padding: 1rem;
    box-shadow: 0 2px 8px var(--shadow-color);
    animation: skeleton-pulse 1.5s ease-in-out infinite;
  }
  .skeleton-image-small {
    width: 60px;
    height: 60px;
    background: var(--border-color);
    border-radius: 8px;
    margin-right: 1rem;
    animation: skeleton-shimmer 1.5s infinite;
  }
  .skeleton-content-small {
    flex: 1;
  }
  .skeleton-line-small {
    height: 12px;
    background: var(--border-color);
    border-radius: 6px;
    margin-bottom: 0.5rem;
    width: 100%;
  }
  .skeleton-line-small:last-child {
    width: 70%;
  }
  .skeleton-table-row {
    display: flex;
    padding: 0.4rem 0.5rem;
    border-bottom: 1px solid var(--border-color);
    animation: skeleton-pulse 1.5s ease-in-out infinite;
  }
  .skeleton-cell {
    padding: 0.2rem 0.5rem;
    flex: 1;
    height: 16px;
    background: var(--border-color);
    border-radius: 4px;
    margin: 0 0.25rem;
  }
  .skeleton-cell:first-child {
    flex: 0 0 18%;
  }
  .skeleton-cell:nth-child(2) {
    flex: 0 0 22%;
  }
  .skeleton-cell:nth-child(3) {
    flex: 1;
  }
  .skeleton-cell:last-child {
    flex: 0 0 12%;
  }
  @keyframes skeleton-pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.7; }
  }
  @keyframes skeleton-shimmer {
    0% { background-position: -200% 0; }
    100% { background-position: 200% 0; }
  }
  @keyframes spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
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
  .feed {
    display: flex;
    flex-wrap: wrap;
    gap: 1.5rem;
    justify-content: center;
    width: 100%;
    box-sizing: border-box;
  }
  .post {
    flex: 0 0 calc(33.333% - 1.5rem);
    min-width: 300px;
    max-width: 400px;
    box-sizing: border-box;
    background: var(--card-bg);
    border-radius: 18px;
    box-shadow: 0 4px 20px var(--shadow-color), 0 0 0 1px rgba(0,0,0,0.03);
    transition: all 0.25s ease-out;
    position: relative;
    display: flex;
    flex-direction: column;
    margin-bottom: 2rem;
    width: 100%;
    overflow: hidden;
    transform: translateZ(0);
  }
  .post:hover {
    box-shadow: 0 12px 28px var(--shadow-color), 0 0 0 1px rgba(0,0,0,0.03);
    transform: translateY(-3px);
  }
  .post.active {
    position: relative;
    box-shadow: 0 6px 15px var(--shadow-color);
  }
  .post-content {
    padding: 0;
    display: flex;
    flex-direction: column;
    height: 100%;
    position: relative;
  }
  .post-image-container {
    position: relative;
    width: 100%;
    height: 200px;
    overflow: hidden;
    border-radius: 18px 18px 0 0;
  }
  .post-badge {
    position: absolute;
    top: 0.8rem;
    left: 0.8rem;
    background-color: rgba(0, 0, 0, 0.65);
    color: white;
    padding: 0.4rem 0.7rem;
    border-radius: 20px;
    font-size: 0.75rem;
    font-weight: 600;
    display: flex;
    align-items: center;
    gap: 0.4rem;
    z-index: 1;
    backdrop-filter: blur(8px);
    box-shadow: 0 2px 8px rgba(0,0,0,0.2);
    border: 1px solid rgba(255,255,255,0.1);
  }
  .active-badge {
    position: absolute;
    top: 0.8rem;
    right: 0.8rem;
    background-color: #c13117d9;
    color: #fff;
    padding: 0.25rem 0.5rem;
    border-radius: 16px;
    font-size: 0.65rem;
    font-weight: 600;
    display: flex;
    align-items: center;
    gap: 0.25rem;
    z-index: 1;
    backdrop-filter: blur(8px);
    box-shadow: 0 2px 6px #0003;
    border: 1px solid rgba(255, 255, 255, .1);
    animation: badgePulse 2s linear infinite;
  }
  .incident-icon {
    font-size: 1rem;
  }
  .active-icon {
    font-size: 0.7rem;
  }
  .post-image {
    width: 100%;
    height: 100%;
    object-fit: cover;
    transition: transform 0.5s ease;
  }
  .post:hover .post-image {
    transform: scale(1.05);
  }
  .post-info {
    padding: 1.4rem;
    flex-grow: 1;
    display: flex;
    flex-direction: column;
  }
  .post-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1rem;
    font-size: 0.9rem;
  }
  .post-time {
    color: var(--text-muted);
    font-weight: 500;
    display: flex;
    align-items: center;
    gap: 0.3rem;
  }
  .post-time::before {
    content: "🕒";
    font-size: 0.8rem;
  }
  .post-location {
    color: var(--primary-color);
    font-weight: 600;
    display: flex;
    align-items: center;
    gap: 0.3rem;
  }
  .post-location::before {
    content: "📍";
    font-size: 0.9rem;
  }
  .post-description {
    font-size: 1rem;
    line-height: 1.5;
    margin-bottom: 1.2rem;
    color: var(--text-darker);
    position: relative;
    text-align: center; /* Center the text */
  }
  .post-actions {
    display: flex;
    justify-content: space-between;
    border-top: 1px solid var(--border-color);
    padding-top: 0.7rem;
    margin-bottom: 0.5rem;
    gap: 0.3rem; /* reduced from 0.5rem for closer buttons */
  }
  .action-button {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.25rem; /* reduced from 0.4rem for closer icon/text */
    background: none;
    border: none;
    color: var(--text-muted);
    font-size: 0.9rem;
    font-weight: 600;
    padding: 0.6875rem 0; /* increased to ensure 44px height (44px / 16px = 2.75rem, but adjusted for existing styles) */
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.2s;
    outline: none;
    flex: 1;
    min-height: 44px; /* ensure minimum touch target */
  }
  .like-button, .comment-button, .share-button {
    flex: 1;
    text-align: center;
    max-width: calc(100% / 3);
    position: relative;
    overflow: hidden;
  }
  .action-button::after {
    content: "";
    position: absolute;
    bottom: 0;
    left: 50%;
    width: 0;
    height: 2px;
    background-color: var(--primary-color);
    transition: all 0.25s ease;
    transform: translateX(-50%);
  }
  .action-button:hover::after {
    width: 70%;
  }
  .action-button:hover {
    background-color: var(--hover-bg);
    color: var(--primary-color);
  }
  .action-button:focus {
    outline: none;
  }
  .button-icon {
    font-size: 1.1rem;
  }
  .like-button.liked {
    color: #e53e3e;
  }
  .like-button.liked .button-icon {
    transform: scale(1.1);
    animation: heartbeat 0.6s;
  }
  @keyframes heartbeat {
    0%, 100% { transform: scale(1); }
    50% { transform: scale(1.3); }
  }
  .like-button.like-error {
    color: var(--error-color);
    animation: errorShake 0.4s;
    background-color: rgba(229, 62, 62, 0.1);
  }
  .comments-title {
    font-size: 1.1rem;
    font-weight: 700;
    margin: 0 0 0.8rem 0;
    color: var(--text-darker);
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }
  .comments-title::before {
    content: "💬";
    font-size: 1rem;
  }
  .comments-overlay {
    position: absolute;
    top: 50px; /* Leave 50px space at the top */
    left: 0;
    width: 100%;
    height: calc(100% - 50px); /* Fill remaining height */
    background-color: var(--card-bg);
    display: flex;
    flex-direction: column;
    padding: 1.2rem;
    z-index: 10;
    border-radius: 18px 18px 0 0; /* Round only top corners */
    box-sizing: border-box;
    box-shadow: 0 4px 10px rgba(0,0,0,0.2);
    will-change: opacity;
    backface-visibility: hidden;
  }
  .close-comments {
    position: absolute;
    top: 0.8rem;
    right: 0.8rem;
    background: var(--text-muted);
    border: none;
    color: var(--card-bg);
    font-size: 1rem;
    font-weight: bold;
    line-height: 1;
    cursor: pointer;
    z-index: 11;
    width: 24px;
    height: 24px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 50%;
    padding: 0;
    transition: all 0.2s ease;
    opacity: 0.7;
    box-shadow: 0 1px 3px var(--shadow-color);
    outline: none;
  }
  .close-comments:hover {
    opacity: 1;
    transform: scale(1.1);
    background: var(--error-color);
  }
  .close-comments:focus {
    outline: none;
  }
  .comments-container {
    flex: 1;
    overflow-y: auto;
    padding-right: 0.6rem;
    margin: 0.3rem 0;
    max-height: calc(100% - 90px);
  }
  .comments-container::-webkit-scrollbar {
    width: 4px;
  }
  .comments-container::-webkit-scrollbar-track {
    background: var(--border-color);
    border-radius: 10px;
  }
  .comments-container::-webkit-scrollbar-thumb {
    background: var(--primary-color);
    border-radius: 10px;
  }
  .no-comments {
    color: var(--text-muted);
    font-style: italic;
    text-align: center;
    padding: 1rem 0;
    background-color: var(--comment-bg);
    border-radius: 10px;
    opacity: 0.8;
  }
  .comment {
    display: flex;
    flex-direction: column;
    margin-bottom: 0.8rem;
    animation: fadeIn 150ms ease-in forwards;
    opacity: 0;
    will-change: transform, opacity;
  }
  .comment-header {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    margin-bottom: 0.2rem;
    padding-left: 0.1rem;
  }
  .comment-avatar {
    width: 24px;
    height: 24px;
    background-color: var(--primary-light);
    color: white;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    font-size: 0.75rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
  }
  .comment-user-info {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }
  .comment-username {
    font-weight: 600;
    color: var(--primary-color);
    font-size: 0.8rem;
    white-space: nowrap;
  }
  .comment-timestamp {
    font-size: 0.7rem;
    color: var(--text-muted);
    font-weight: 500;
    position: relative;
    padding-left: 0.5rem;
  }
  .comment-timestamp::before {
    content: "•";
    position: absolute;
    left: 0;
    color: var(--text-muted);
    opacity: 0.5;
  }
  .comment-content {
    background-color: var(--comment-bg);
    padding: 0.6rem 0.8rem;
    border-radius: 12px;
    box-shadow: 0 1px 2px var(--shadow-color);
    font-size: 0.9rem;
    line-height: 1.4;
    color: var(--text-darker);
    margin-left: 2rem;
    word-break: break-word;
    border-top-left-radius: 2px;
    position: relative;
  }
  .comment-text {
    margin-bottom: 0.3rem;
  }
  .comment-timestamp {
    font-size: 0.7rem;
    color: var(--text-muted);
    font-weight: 500;
    text-align: right;
  }
  .comment-content::before {
    content: "";
    position: absolute;
    top: 0;
    left: -6px;
    width: 12px;
    height: 12px;
    background-color: var(--comment-bg);
    transform: rotate(45deg);
    border-radius: 2px;
    z-index: -1;
  }
  @keyframes fadeIn {
    from { opacity: 0; transform: translateY(5px); }
    to { opacity: 1; transform: translateY(0); }
  }
  .add-comment {
    display: flex;
    gap: 0.5rem;
    margin-top: 0.8rem;
  }
  .add-comment input {
    flex: 1;
    padding: 0.7rem 1rem;
    border: 1px solid var(--border-color);
    border-radius: 24px;
    font-size: 0.9rem;
    background-color: var(--comment-bg);
    color: var(--text-darker);
    transition: all 0.2s;
  }
  .add-comment input:focus {
    outline: none;
    border-color: var(--primary-color);
    box-shadow: 0 0 0 3px rgba(66, 153, 225, 0.15);
  }
  .add-comment input::placeholder {
    color: var(--text-muted);
  }
  .add-comment button {
    background-color: var(--primary-color);
    color: white;
    border: none;
    border-radius: 24px;
    padding: 0.7rem 1.2rem;
    font-weight: 600;
    font-size: 0.9rem;
    cursor: pointer;
    transition: all 0.2s;
    outline: none;
    box-shadow: 0 2px 6px rgba(0,0,0,0.1);
  }
  .add-comment button:hover {
    background-color: var(--primary-dark);
    box-shadow: 0 4px 10px rgba(0,0,0,0.15);
    transform: translateY(-1px);
  }
  .add-comment button:active {
    transform: translateY(0);
  }
  .error-message {
    color: var(--error-color);
    background-color: var(--error-bg);
    border-left: 4px solid var(--error-color);
    padding: 0.6rem 1rem;
    margin-top: 0.6rem;
    font-size: 0.85rem;
    border-radius: 6px;
    animation: errorShake 0.4s;
  }
  .refresh-info {
    text-align: center;
    margin-top: 2rem;
    color: var(--text-muted);
    font-size: 0.9rem;
    padding: 0.5rem 1rem;
    background-color: var(--bg-color);
    border-radius: 30px;
    display: inline-block;
    margin-left: auto;
    margin-right: auto;
    box-shadow: 0 1px 3px var(--shadow-color);
    border: 1px solid var(--border-color);
  }
  @keyframes errorShake {
    0%, 100% { transform: translateX(0); }
    10%, 30%, 50%, 70%, 90% { transform: translateX(-5px); }
    20%, 40%, 60%, 80% { transform: translateX(5px); }
  }
  @media (max-width: 1024px) {
    .skeleton-card {
      flex: 0 0 calc(50% - 1.5rem);
    }
  }
  @media (max-width: 768px) {
    .container {
      padding: 0.5rem;
    }
    .feed {
      gap: 1rem;
      padding: 0;
    }
    .post {
      flex: 0 0 100%;
      max-width: 100%;
      margin: 0 0 0.8rem 0;
      border-radius: 14px;
    }
    .post-image-container {
      border-radius: 14px 14px 0 0;
    }
    .header {
      padding: 0.8rem;
      margin-bottom: 0.8rem;
      border-radius: 12px;
    }
    .header h1 {
      font-size: 1.5rem;
      margin-bottom: 0.3rem;
    }
    .header p {
      font-size: 0.9rem;
    }
    .post-info {
      padding: 1rem 1rem 0.6rem;
    }
    .post-description {
      font-size: 0.95rem;
      line-height: 1.4;
      margin-bottom: 1rem;
    }
    
    .skeleton-card {
      flex: 0 0 100%;
      max-width: 100%;
      margin: 0 0 0.8rem 0;
      border-radius: 14px;
    }
    
    .skeleton-image {
      border-radius: 14px 14px 0 0;
    }
    
    .skeleton-content {
      padding: 1rem 1rem 0.6rem;
    }
    
    .skeleton-line {
      margin-bottom: 0.7rem;
    }
    
    .skeleton-title {
      margin-bottom: 0.7rem;
    }
    
    .skeleton-text {
      height: 14px;
      margin-bottom: 1rem;
    }
    
    .skeleton-actions {
      padding-top: 0.7rem;
    }
  }
  @media (max-width: 480px) {
    .container {
      padding: 0.15rem;
    }
    .feed {
      gap: 0.5rem;
    }
    .post {
      margin: 0 0 0.5rem 0;
      border-radius: 12px;
    }
    .post-image-container {
      border-radius: 12px 12px 0 0;
    }
    .post-info {
      padding: 0.7rem 0.7rem 0.5rem;
    }
    .post-header {
      margin-bottom: 0.7rem;
    }
    .post-description {
      font-size: 0.9rem;
      line-height: 1.35;
      margin-bottom: 0.8rem;
    }
    .header {
      padding: 0.7rem;
      margin-bottom: 0.7rem;
      border-radius: 10px;
    }
    .post-actions {
      gap: 0.2rem;
      padding-top: 0.7rem;
    }
    .action-button {
      padding: 0.4rem 0.2rem;
      font-size: 0.85rem;
      gap: 0.2rem;
      min-height: 44px;
    }
    .action-button span:last-child {
      min-width: 18px;
    }
    
    .skeleton-card {
      margin: 0 0 0.5rem 0;
      border-radius: 12px;
    }
    
    .skeleton-image {
      border-radius: 12px 12px 0 0;
    }
    
    .skeleton-content {
      padding: 0.7rem 0.7rem 0.5rem;
    }
    
    .skeleton-line {
      height: 18px;
      margin-bottom: 0.7rem;
    }

    .skeleton-title {
      height: 22px;
      margin-bottom: 0.7rem;
    }
    
    .skeleton-text {
      margin-bottom: 0.8rem;
    }
    
    .skeleton-actions {
      gap: 0.2rem;
      padding-top: 0.7rem;
    }
    
    .skeleton-button {
      height: 44px;
    }
  }

  @media (max-width: 320px) {
    .container {
      padding: 0.1rem;
      overflow-x: hidden;
    }
    .feed {
      gap: 0.3rem;
    }
    .post {
      margin: 0 0 0.3rem 0;
      border-radius: 8px;
      min-width: unset;
      max-width: 100%;
    }
    .post-image-container {
      border-radius: 8px 8px 0 0;
    }
    .post-info {
      padding: 0.5rem 0.5rem 0.3rem;
    }
    .header {
      padding: 0.5rem;
      margin-bottom: 0.5rem;
      border-radius: 8px;
    }
    .action-button {
      padding: 0.3rem 0.1rem;
      font-size: 0.8rem;
      min-height: 44px;
    }
    .incidents-table {
      min-width: unset;
      overflow-x: auto;
    }
    
    .skeleton-card {
      margin: 0 0 0.3rem 0;
      border-radius: 8px;
      min-width: unset;
      max-width: 100%;
    }
    
    .skeleton-image {
      border-radius: 8px 8px 0 0;
    }
    
    .skeleton-content {
      padding: 0.5rem 0.5rem 0.3rem;
    }
  }
  :global(button) {
    outline: none;
    -webkit-tap-highlight-color: transparent;
  }
  :global(*) {
    -webkit-tap-highlight-color: transparent;
  }
  .loading-more {
    width: 100%;
    display: flex;
    justify-content: center;
    padding: 1rem 0;
  }
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
  .scroll-indicator:active {
    transform: translateY(0);
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
    0%, 80%, 100% { transform: translateY(0); }
    40% { transform: translateY(-8px); }
  }
  .app-footer {
    text-align: center;
    margin-top: 2rem;
    padding: 0rem 0;
    color: var(--text-muted);
    font-size: 0.9rem;
    border-top: 1px solid var(--border-color);
  }
  
  .app-footer a {
    color: var(--primary-color);
    text-decoration: none;
    font-weight: 600;
    transition: color 0.2s ease;
  }
  
  .app-footer a:hover {
    color: var(--primary-dark);
    text-decoration: underline;
  }

  /* Toast notifications */
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
    background-color: var(--primary-color);
    color: white;
  }

  .toast-success {
    background-color: var(--success-color);
    color: white;
  }

  .toast-warning {
    background-color: #ed8936;
    color: white;
  }

  .toast-error {
    background-color: var(--error-color);
    color: white;
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
  .more-button {
    background: none;
    border: none;
    color: var(--primary-color);
    padding: 0;
    margin-left: 0.25rem;
    font-size: 0.85rem;
    font-weight: 600;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    transition: color 0.2s ease;
  }
  .more-button:hover {
    color: var(--primary-dark);
    text-decoration: underline;
  }
  .view-controls {
    display: flex;
    justify-content: flex-end;
    margin-bottom: 1rem;
    display: none; /* Hide the old button control */
  }
  
  .view-toggle-button {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    background-color: var(--primary-lightest);
    color: var(--primary-color);
    border: 1px solid var(--primary-light);
    border-radius: 24px;
    padding: 0.6rem 1.2rem;
    font-size: 0.9rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    position: relative;
    overflow: hidden;
  }
  
  .view-toggle-button:hover {
    background-color: var(--primary-light);
    color: white;
    transform: translateY(-1px);
    box-shadow: 0 3px 8px rgba(0,0,0,0.15);
  }
  
  .view-toggle-button:focus {
    outline: none;
    box-shadow: 0 0 0 3px rgba(66, 153, 225, 0.4);
  }
  
  .view-toggle-button:active {
    transform: translateY(0);
  }
  
  .toggle-icon {
    font-size: 1.2rem;
    position: relative;
    z-index: 2;
  }
  
  .toggle-text {
    font-weight: 700;
    position: relative;
    z-index: 2;
  }
  
  .toggle-description {
    font-size: 0.8rem;
    font-weight: 400;
    opacity: 0.8;
    position: relative;
    z-index: 2;
  }
  
  .toggle-state {
    position: absolute;
    height: 100%;
    width: 24px;
    right: 12px;
    top: 0;
    display: flex;
    align-items: center;
    justify-content: center;
  }
  
  .toggle-indicator {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    background-color: var(--primary-color);
    transition: all 0.3s;
  }
  
  @media (max-width: 768px) {
    .toggle-description {
      display: none;
    }
    
    .view-toggle-button {
      padding: 0.5rem 1rem;
    }
  }
  
  @media (max-width: 480px) {
    .toggle-text {
      display: none;
    }
    
    .view-toggle-button {
      padding: 0.5rem 0.7rem;
      justify-content: center;
    }
  }
  
  .incidents-table {
    width: 100%;
    min-width: 800px;
    background: var(--card-bg);
    border-radius: 16px;
    overflow: hidden;
    box-shadow: 0 4px 20px var(--shadow-color), 0 0 0 1px rgba(0,0,0,0.03);
    margin-bottom: 2rem;
    box-sizing: border-box;
    max-width: 100%;
    min-width: 100%;
  }
  
  .table-header {
    display: flex;
    background-color: var(--primary-color);
    color: white;
    font-weight: 600;
    padding: 1rem;
    border-bottom: 1px solid var(--border-color);
    width: 100%;
    box-sizing: border-box;
  }
  
  .table-row {
    display: flex;
    padding: 0.4rem 0.5rem;
    border-bottom: 1px solid var(--border-color);
    cursor: pointer;
    transition: all 0.2s;
    position: relative;
    width: 100%;
    box-sizing: border-box;
  }
  
  .table-row:hover {
    background-color: var(--hover-bg);
    transform: translateX(2px);
    box-shadow: 0 2px 8px var(--shadow-color);
    z-index: 1;
  }
  
  .table-row.active {
    border-left: 4px solid #c13117;
  }
  
  .table-row.expanded {
    background-color: var(--primary-lightest);
    border-bottom: none;
    box-shadow: 0 2px 8px var(--shadow-color);
  }
  
  .table-row::after {
    content: "▼";
    position: absolute;
    right: 1rem;
    top: 50%;
    transform: translateY(-50%);
    color: var(--text-muted);
    transition: transform 0.2s ease;
  }
  
  .table-row.expanded::after {
    transform: translateY(-50%) rotate(180deg);
  }
  
  .table-cell {
    padding: 0.2rem 0.5rem;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  
  .type-cell {
    flex: 0 0 18%;
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .time-cell {
    flex: 0 0 22%;
  }

  .location-cell {
    flex: 1;
  }

  .status-cell {
    flex: 0 0 12%;
    text-align: center;
  }
  
  .incident-icon-small {
    font-size: 1rem;
    display: inline-block;
    margin-right: 0.3rem;
  }
  
  .incident-type-small {
    font-weight: 500;
  }
  
  .status-badge {
    display: inline-block;
    padding: 0.2rem 0.5rem;
    border-radius: 20px;
    font-size: 0.75rem;
    font-weight: 600;
    background-color: var(--border-color);
    color: var(--text-dark);
  }
  
  .status-badge.active {
    background-color: #c13117;
    color: white;
    animation: badgePulse 2s linear infinite;
  }
  
  .expanded-details {
    background-color: var(--primary-lightest);
    padding: 0 1rem 1rem 1rem;
    border-bottom: 1px solid var(--border-color);
    overflow: hidden;
    width: 100%;
    box-sizing: border-box;
    position: relative;
  }
  
  .expanded-content {
    display: flex;
    gap: 1rem;
    align-items: center; /* Vertically center content */
  }
  
  .expanded-image {
    flex: 0 0 30%;
    max-width: 300px;
    border-radius: 12px;
    overflow: hidden;
  }
  
  .expanded-image img {
    width: 100%;
    height: 200px;
    object-fit: cover;
    border-radius: 12px; /* Add rounded corners to all sides */
  }
  
  .expanded-info {
    flex: 1;
    display: flex;
    flex-direction: column;
  }
  
  .expanded-actions {
    display: flex;
    justify-content: center; /* Center the buttons */
    gap: 1rem;
    margin-top: 1rem;
  }
  
  .expanded-actions .action-button {
    border-radius: 8px;
    max-width: none;
  }
  
  @media (max-width: 768px) {
    .expanded-content {
      flex-direction: column;
    }

    .expanded-image {
      max-width: 100%;
      width: 100%; /* Ensure it takes full width */
      margin-bottom: 1rem;
      padding-top: 0.5rem; /* Add space above the image without shifting other content */
    }

    .type-cell {
      flex: 0 0 25%;
    }

    .time-cell {
      flex: 0 0 25%;
    }

    .status-cell {
      flex: 0 0 20%;
    }

    .combined-stats {
      flex-direction: column !important;
      gap: 1rem;
    }

    .view-toggle-button span:not(.toggle-icon):not(.arrow-icon) {
      display: none;
    }

    .view-toggle-button {
      padding: 0.5rem;
    }
  }
  
  @media (max-width: 480px) {
    .table-header {
      padding: 0.7rem 0.5rem;
    }
    
    .table-row {
      padding: 0.4rem 0.5rem;
    }
    
    .table-cell {
      padding: 0.1rem 0.2rem;
      font-size: 0.85rem;
    }
    
    .incident-type-small {
      display: none;
    }
    
    .type-cell {
      flex: 0 0 10%;
      justify-content: center;
    }
    
    .time-cell {
      flex: 0 0 30%;
    }
    
    .status-cell {
      flex: 0 0 20%;
    }
    
    .status-badge {
      display: none;
    }
    
    .table-header .status-cell {
      display: none;
    }
  }
  
  @keyframes badgePulse {
    0% {
      box-shadow: 0 0 0 0 rgba(255, 99, 71, 0.4);
    }
    70% {
      box-shadow: 0 0 0 6px rgba(255, 99, 71, 0);
    }
    100% {
      box-shadow: 0 0 0 0 rgba(255, 99, 71, 0);
    }
  }
  
  .full-time {
    display: inline;
  }
  
  .mobile-time {
    display: none;
  }
  
  @media (max-width: 768px) {
    .expanded-content {
      flex-direction: column;
    }
    
    .expanded-image {
      max-width: 100%;
      margin-bottom: 1rem;
    }
    
    .type-cell {
      flex: 0 0 25%;
    }
    
    .time-cell {
      flex: 0 0 25%;
    }
    
    .status-cell {
      flex: 0 0 20%;
    }
    
    .view-toggle-button span:not(.toggle-icon):not(.arrow-icon) {
      display: none;
    }
    
    .view-toggle-button {
      padding: 0.5rem;
    }
  }
  
  @media (max-width: 480px) {
    .full-time {
      display: none;
    }
    
    .mobile-time {
      display: inline;
    }
    
    .table-header {
      padding: 0.7rem 0.5rem;
    }
    
    .table-row {
      padding: 0.4rem 0.5rem;
    }
    
    .table-cell {
      padding: 0.1rem 0.2rem;
      font-size: 0.85rem;
    }
    
    .incident-type-small {
      display: none;
    }
    
    .type-cell {
      flex: 0 0 10%;
      justify-content: center;
    }
    
    .time-cell {
      flex: 0 0 30%;
    }
    
    .status-cell {
      flex: 0 0 20%;
    }
    
    .status-badge {
      display: none;
    }
    
    .table-header .status-cell {
      display: none;
    }
  }
  
  .swipe-indicator {
    position: fixed;
    top: 50%;
    transform: translateY(-50%);
    background-color: rgba(0, 0, 0, 0.7);
    color: white;
    padding: 1rem;
    border-radius: 8px;
    display: flex;
    flex-direction: column;
    align-items: center;
    z-index: 100;
    pointer-events: none;
    backdrop-filter: blur(4px);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
    width: 100px;
    text-align: center;
  }
  
  .swipe-indicator.left {
    right: 20px;
    animation: slideInRight 0.3s forwards;
  }
  
  .swipe-indicator.right {
    left: 20px;
    animation: slideInLeft 0.3s forwards;
  }
  
  .swipe-arrow {
    font-size: 1.8rem;
    margin-bottom: 0.5rem;
  }
  
  .swipe-text {
    font-size: 0.9rem;
    font-weight: 600;
  }
  
  @keyframes slideInRight {
    from { opacity: 0; transform: translate(20px, -50%); }
    to { opacity: 1; transform: translate(0, -50%); }
  }
  
  @keyframes slideInLeft {
    from { opacity: 0; transform: translate(-20px, -50%); }
    to { opacity: 1; transform: translate(0, -50%); }
  }

  .side-toggle {
    position: fixed;
    right: -6px;
    top: 50%;
    transform: translateY(-50%);
    background-color: var(--primary-color);
    color: white;
    border: none;
    border-radius: 8px 0 0 8px;
    padding: 0.8rem .5rem;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 0.5rem;
    cursor: pointer;
    z-index: 100;
    box-shadow: -2px 0 10px rgba(0, 0, 0, 0.1);
    transition: all 0.3s ease;
  }

  .side-toggle:hover {
    background-color: var(--primary-dark);
    transform: translateY(-50%) translateX(-5px);
  }

  .side-toggle.condensed {
    right: -8px;
  }

  .side-toggle-arrow {
    font-size: 1.5rem;
    font-weight: bold;
    line-height: 1;
  }

  .side-toggle-text {
    font-size: 0.8rem;
    writing-mode: vertical-rl;
    transform: rotate(180deg);
    text-transform: uppercase;
    letter-spacing: 1px;
  }

  .table-comments-overlay {
    position: absolute;
    top: 20px; /* Reduced space at the top */
    left: 0;
    width: 100%;
    height: calc(100% - 20px); /* Adjust height accordingly */
    background-color: var(--card-bg);
    display: flex;
    flex-direction: column;
    padding: 1.2rem;
    z-index: 20;
    border-radius: 16px 16px 0 0; /* Round only top corners */
    box-sizing: border-box;
    box-shadow: 0 4px 10px rgba(0, 0, 0, 0.2);
    will-change: opacity;
    backface-visibility: hidden;
  }

  @media (max-width: 768px) {
    .side-toggle {
      display: none; /* Hide the side toggle on mobile - use swipe instead */
    }
  }

  /* Pull-to-refresh indicator */
  .pull-refresh-indicator {
    position: fixed;
    top: -60px;
    left: 50%;
    transform: translateX(-50%);
    background: var(--primary-color);
    color: white;
    padding: 0.5rem 1rem;
    border-radius: 20px;
    font-size: 0.9rem;
    font-weight: 600;
    z-index: 1000;
    transition: transform 0.3s ease;
    box-shadow: 0 2px 10px rgba(0,0,0,0.2);
  }

  .pull-refresh-indicator.refreshing {
    transform: translateX(-50%) translateY(60px);
  }

  /* Optimize animations for lower-end devices */
  @media (prefers-reduced-motion: reduce) {
    *, *::before, *::after {
      animation-duration: 0.01ms !important;
      animation-iteration-count: 1 !important;
      transition-duration: 0.01ms !important;
    }
  }

  /* Add will-change for better performance */
  .post, .table-row, .toast, .swipe-indicator {
    will-change: transform, opacity;
  }

  .chart-item {
    flex: 0 0 100%;
    min-width: 280px;
    max-width: 500px;
  }

  .mini-chart {
    border-radius: 8px;
    padding: 4px;
    position: relative;
  }



  .chart-labels {
    display: flex;
    justify-content: space-between;
    font-size: 0.65rem;
  }

  @media (max-width: 768px) {
    .chart-item {
      min-width: 100%;
    }
  }
</style>
