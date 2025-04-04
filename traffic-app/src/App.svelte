<script>
  import { onMount, onDestroy } from 'svelte';
  import { fade, slide } from 'svelte/transition';
  import { flip } from 'svelte/animate';

  let posts = [];
  let allPosts = [];
  let loading = true;
  let darkMode = false;
  let currentUsername = '';
  let lastToggleTime = 0;
  let postsPerPage = 20;
  let currentPage = 1;
  let loadingMore = false;
  let allPostsLoaded = false;
  let scrollContainer;
  let selectedType = null;

  const adjectives = ['Cool', 'Happy', 'Swift', 'Brave', 'Clever', 'Lucky'];
  const nouns = ['Panda', 'Tiger', 'Eagle', 'Fox', 'Wolf', 'Bear'];

  function generateRandomUsername() {
    const adj = adjectives[Math.floor(Math.random() * adjectives.length)];
    const noun = nouns[Math.floor(Math.random() * nouns.length)];
    const num = Math.floor(Math.random() * 100);
    return `${adj}${noun}${num}`;
  }

  function toggleDarkMode() {
    darkMode = !darkMode;
    document.body.classList.toggle('dark-mode', darkMode);
    localStorage.setItem('darkMode', darkMode.toString());
  }

  function getUniqueIncidentTypes() {
    const types = new Set();
    allPosts.forEach(post => types.add(post.type));
    return Array.from(types);
  }

  function filterByType(type) {
    selectedType = selectedType === type ? null : type;
    currentPage = 1;
    loadPostsPage();
  }

  async function fetchIncidents() {
    try {
      loading = true;
      const res = await fetch('/api/incidents');
      
      if (!res.ok) {
        console.error(`Failed to fetch incidents: ${res.status} ${res.statusText}`);
        loading = false;
        return;
      }
      
      const incidents = await res.json();
      const uniqueIncidents = [];
      const seenKeys = new Set();
      
      for (const incident of incidents) {
        const date = incident.timestamp ? new Date(incident.timestamp).toLocaleDateString() : '';
        const compositeKey = `${incident.incident_no}-${date}`;
        
        if (!seenKeys.has(compositeKey)) {
          seenKeys.add(compositeKey);
          incident.compositeId = compositeKey;
          uniqueIncidents.push(incident);
        }
      }
      
      const processedPosts = uniqueIncidents
        .filter(incident => incident.map_filename) 
        .map(incident => ({
          id: incident.incident_no,
          compositeId: incident.compositeId,
          time: formatTimestamp(incident.timestamp),
          description: incident.description,
          showFullDescription: false,
          location: incident.location,
          image: `/maps/${incident.map_filename}`,
          likes: incident.likes,
          comments: incident.comments || [],
          newComment: "",
          showComments: false,
          type: incident.type || "Traffic Incident",
          likeError: "",
          commentError: "",
          likeErrorAnimation: false,
          active: incident.active
        }));

      allPosts = processedPosts;
      currentPage = 1;
      allPostsLoaded = false;
      loadPostsPage();
      
    } catch (err) {
      console.error("Error fetching incidents:", err);
    } finally {
      loading = false;
    }
  }
  
  function loadPostsPage() {
    const endIndex = currentPage * postsPerPage;
    let postsToShow = allPosts;
    
    if (selectedType) {
      postsToShow = allPosts.filter(post => post.type === selectedType);
    }
    
    postsToShow = postsToShow.slice(0, endIndex);
    
    posts = postsToShow.map(newPost => {
      const existingPost = posts.find(p => p.compositeId === newPost.compositeId);
      return existingPost
        ? { ...newPost, likes: existingPost.likes, comments: existingPost.comments, showComments: existingPost.showComments, newComment: existingPost.newComment, likeError: existingPost.likeError, commentError: existingPost.commentError, showFullDescription: existingPost.showFullDescription }
        : newPost;
    });
    
    allPostsLoaded = endIndex >= postsToShow.length;
    loadingMore = false;
  }
  
  function loadMorePosts() {
    if (loadingMore || allPostsLoaded) return;
    loadingMore = true;
    currentPage++;
    setTimeout(() => {
      loadPostsPage();
    }, 300);
  }
  
  function handleScroll() {
    if (!scrollContainer || loadingMore || allPostsLoaded) return;
    const { scrollTop, scrollHeight, clientHeight } = scrollContainer;
    const scrollBottom = scrollHeight - scrollTop - clientHeight;
    if (scrollBottom < 300) {
      loadMorePosts();
    }
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

  async function likePost(postId) {
    try {
      posts = posts.map(p =>
        p.id === postId ? { ...p, likeError: "", likeErrorAnimation: false } : p
      );

      const res = await fetch(`/api/incidents/${postId}/like`, { method: 'POST' });
      const data = await res.json();
      if (res.ok) {
        posts = posts.map(p =>
          p.id === postId ? { ...p, likes: data.likes, likeError: "" } : p
        );
      } else {
        posts = posts.map(p =>
          p.id === postId ? { ...p, likeErrorAnimation: true } : p
        );
        setTimeout(() => {
          posts = posts.map(p =>
            p.id === postId ? { ...p, likeErrorAnimation: false } : p
          );
        }, 500);
      }
    } catch (err) {
      console.error("Error liking post:", err);
      posts = posts.map(p =>
        p.id === postId ? { ...p, likeErrorAnimation: true } : p
      );
      setTimeout(() => {
        posts = posts.map(p =>
          p.id === postId ? { ...p, likeErrorAnimation: false } : p
        );
      }, 500);
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
      posts = posts.map(p =>
        p.id === postId ? { ...p, commentError: "You can only leave 2 comments per post." } : p
      );
      setTimeout(() => {
        posts = posts.map(p =>
          p.id === postId ? { ...p, commentError: "" } : p
        );
      }, 3000);
      return;
    }

    const newCommentObj = {
      username: currentUsername,
      comment: post.newComment,
      timestamp: new Date().toISOString()
    };
    try {
      const res = await fetch(`/api/incidents/${postId}/comment`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newCommentObj)
      });
      const data = await res.json();
      if (res.ok) {
        posts = posts.map(p =>
          p.id === postId ? { 
            ...p, 
            comments: data.comments,
            newComment: "", 
            commentError: "" 
          } : p
        );
      } else {
        posts = posts.map(p =>
          p.id === postId ? { ...p, commentError: data.error } : p
        );
        setTimeout(() => {
          posts = posts.map(p =>
            p.id === postId ? { ...p, commentError: "" } : p
          );
        }, 3000);
      }
    } catch (err) {
      console.error("Error submitting comment:", err);
      posts = posts.map(p =>
        p.id === postId ? { ...p, commentError: "Error submitting comment." } : p
      );
      setTimeout(() => {
        posts = posts.map(p =>
          p.id === postId ? { ...p, commentError: "" } : p
        );
      }, 3000);
    }
  }

  function getIconForIncidentType(type) {
    const types = {
      "Accident": "🚗",
      "Traffic Hazard": "⚠️",
      "Road Closure": "🚧",
      "Fire": "🔥",
      "Police": "👮‍♂️",
      "Weather": "🌧️"
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

  onMount(() => {
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    const storedMode = localStorage.getItem('darkMode');
    darkMode = storedMode ? storedMode === 'true' : prefersDark;
    document.body.classList.toggle('dark-mode', darkMode);

    currentUsername = localStorage.getItem('username') || generateRandomUsername();
    if (!localStorage.getItem('username')) {
      localStorage.setItem('username', currentUsername);
    }

    fetchIncidents();
    const refreshInterval = setInterval(fetchIncidents, 60000);
    document.querySelector('.refresh-info').textContent = 'Refreshing automatically every 60 seconds';
    if (scrollContainer) {
      scrollContainer.addEventListener('scroll', handleScroll);
    }
    onDestroy(() => {
      clearInterval(refreshInterval);
      if (scrollContainer) {
        scrollContainer.removeEventListener('scroll', handleScroll);
      }
    });
  });
</script>

<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">
<div class="container" bind:this={scrollContainer} on:scroll={handleScroll}>
  <div class="header">
    <button class="header-content" on:click={toggleDarkMode} type="button">
      <h1>San Diego Traffic Watch</h1>
      <p>Real-time incidents from CHP scanner data</p>
    </button>
  </div>
  
  {#if loading && posts.length === 0}
    <div class="loading-container" in:fade={{ duration: 150 }}>
      <div class="loading-spinner"></div>
      <p>Loading incidents...</p>
    </div>
  {:else if posts.length === 0}
    <div class="empty-state" in:fade={{ duration: 150 }}>
      <div class="empty-icon">🔍</div>
      <p>No incidents to display at the moment.</p>
      <p>Check back soon for updates.</p>
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
                <div class="comments-overlay" transition:fade={{ duration: 100 }}>
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
      
      {#if loadingMore}
        <div class="loading-more" in:fade={{ duration: 150 }}>
          <div class="loading-spinner-small"></div>
          <p>Loading more incidents...</p>
        </div>
      {:else if !allPostsLoaded}
        <div class="scroll-indicator" in:fade={{ duration: 150 }}>
          <div class="scroll-dots">
            <span class="dot"></span>
            <span class="dot"></span>
            <span class="dot"></span>
          </div>
          <p>Scroll for more</p>
        </div>
      {/if}
    </div>
  {/if}
  
  <div class="refresh-info" in:fade={{ delay: 300, duration: 150 }}>
    Refreshing automatically every 60 seconds
  </div>
  
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
  .loading-container {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 3rem 0;
  }
  .loading-spinner {
    width: 40px;
    height: 40px;
    border: 4px solid rgba(66, 153, 225, 0.1);
    border-radius: 50%;
    border-left-color: var(--primary-color);
    animation: spin 1s linear infinite;
    margin-bottom: 1rem;
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
    -webkit-backdrop-filter: blur(8px);
    box-shadow: 0 2px 6px #0003;
    border: 1px solid rgba(255, 255, 255, .1);
    animation: badgePulse 2s linear infinite;
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
  }
  .post-actions {
    display: flex;
    justify-content: space-between;
    border-top: 1px solid var(--border-color);
    padding-top: 1rem;
    margin-bottom: 0.5rem;
    gap: 0.5rem;
  }
  .action-button {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.4rem;
    background: none;
    border: none;
    color: var(--text-muted);
    font-size: 0.9rem;
    font-weight: 600;
    padding: 0.6rem 0;
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.2s;
    outline: none;
    flex: 1;
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
  .action-button span:last-child {
    min-width: 24px;
    text-align: center;
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
    top: 200px;
    left: 0;
    width: 100%;
    height: calc(100% - 200px);
    background-color: var(--card-bg);
    display: flex;
    flex-direction: column;
    padding: 1.2rem;
    z-index: 10;
    border-radius: 0 0 18px 18px;
    box-sizing: border-box;
    box-shadow: inset 0 4px 6px -1px var(--shadow-color);
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
    .post {
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
    }
    .action-button span:last-child {
      min-width: 18px;
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
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 1.5rem 0;
    color: var(--text-muted);
  }
  .loading-spinner-small {
    width: 30px;
    height: 30px;
    border: 3px solid rgba(66, 153, 225, 0.1);
    border-radius: 50%;
    border-left-color: var(--primary-color);
    animation: spin 1s linear infinite;
    margin-bottom: 0.5rem;
  }
  .scroll-indicator {
    width: 100%;
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 1rem 0;
    color: var(--text-muted);
    font-size: 0.9rem;
    opacity: 0.7;
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
</style>