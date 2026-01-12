<script>
    import { createEventDispatcher } from "svelte";
    import { slide } from "svelte/transition";
    import {
        getIconForIncidentType,
        formatTimestamp,
        formatTimeOnly,
        truncateDescription,
        formatCommentTimestamp,
    } from "../utils/helpers.js";
    import CommentOverlay from "./CommentOverlay.svelte";
    import { fly } from "svelte/transition";
    import {
        Zap,
        Heart,
        MessageSquare,
        Share2,
        User,
        X,
        ChevronDown,
        Send,
    } from "lucide-svelte";
    import IncidentIcon from "./IncidentIcon.svelte";

    export let posts = [];

    export let expandedPostId = null;

    const dispatch = createEventDispatcher();

    function handleRowClick(post) {
        // If closing the currently expanded row and its comments are open, close comments first
        if (expandedPostId === post.id && post.showComments) {
            dispatch("closeComments", { postId: post.id });
        }
        dispatch("toggleExpand", { postId: post.id });
    }

    function handleLike(e, postId) {
        e.stopPropagation();
        dispatch("like", { postId });
    }

    function handleToggleComments(e, postId) {
        e.stopPropagation();
        dispatch("toggleComments", { postId });
    }

    function handleShare(e, post) {
        e.stopPropagation();
        dispatch("share", { post });
    }

    function handleToggleDescription(e, postId) {
        e.stopPropagation();
        dispatch("toggleDescription", { postId });
    }

    function handleCommentSubmit(postId, comment) {
        dispatch("submitComment", { postId, comment });
    }

    function handleCommentClose(postId) {
        dispatch("toggleComments", { postId });
    }
</script>

<div class="incidents-table">
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
            role="button"
            tabindex="0"
            on:click={() => handleRowClick(post)}
            on:keydown={(e) =>
                (e.key === "Enter" || e.key === " ") && handleRowClick(post)}
            in:slide={{ delay: Math.min(i * 30, 300), duration: 150 }}
        >
            <div class="table-cell type-cell">
                <span class="incident-icon-small">
                    <IncidentIcon type={post.type} />
                </span>
                <span class="incident-type-small">{post.type}</span>
            </div>
            <div class="table-cell time-cell">
                <span class="full-time">{post.time}</span>
                <span class="mobile-time">{formatTimeOnly(post.timestamp)}</span
                >
            </div>
            <div class="table-cell location-cell">{post.location}</div>
            <div class="table-cell status-cell">
                {#if post.active}
                    <span class="status-badge active"
                        ><Zap size={10} fill="currentColor" /> Active</span
                    >
                {:else}
                    <span class="status-badge">Inactive</span>
                {/if}
            </div>
            <span class="row-arrow"><ChevronDown size={16} /></span>
        </div>

        {#if expandedPostId === post.id}
            <div class="expanded-details" transition:slide={{ duration: 200 }}>
                <div class="expanded-content">
                    <div class="expanded-image">
                        <img
                            src={post.image}
                            alt="Incident location map"
                            loading="lazy"
                        />
                    </div>
                    <div class="expanded-info">
                        <div class="post-description">
                            {#if post.description}
                                {post.showFullDescription
                                    ? post.description
                                    : truncateDescription(post.description)}
                                {#if post.description.length > 200}
                                    <button
                                        class="more-button"
                                        on:click={(e) =>
                                            handleToggleDescription(e, post.id)}
                                    >
                                        {post.showFullDescription
                                            ? "less"
                                            : "more"}
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
                                on:click={(e) => handleLike(e, post.id)}
                            >
                                <span class="button-icon">
                                    <Heart
                                        size={18}
                                        fill={post.likes > 0
                                            ? "currentColor"
                                            : "none"}
                                    />
                                </span>
                                <span
                                    >{post.likes > 0
                                        ? post.likes
                                        : "Like"}</span
                                >
                            </button>
                            <button
                                class="action-button comment-button"
                                on:click={(e) =>
                                    handleToggleComments(e, post.id)}
                            >
                                <span class="button-icon">
                                    <MessageSquare size={18} />
                                </span>
                                <span
                                    >{post.comments.length > 0
                                        ? post.comments.length
                                        : "Comment"}</span
                                >
                            </button>
                            <button
                                class="action-button share-button"
                                on:click={(e) => handleShare(e, post)}
                            >
                                <span class="button-icon">
                                    <Share2 size={18} />
                                </span>
                                <span>Share</span>
                            </button>
                        </div>
                    </div>
                </div>

                {#if post.showComments}
                    <div
                        class="table-comments-overlay"
                        in:fly={{ y: 200, duration: 300 }}
                        out:fly={{ y: 200, duration: 200 }}
                    >
                        <button
                            class="close-comments"
                            on:click={(e) => {
                                e.stopPropagation();
                                handleCommentClose(post.id);
                            }}><X size={18} /></button
                        >
                        <h3 class="comments-title">
                            <MessageSquare size={18} />
                            Comments ({post.comments.length})
                        </h3>
                        {#if post.commentError}
                            <p class="error-message">{post.commentError}</p>
                        {/if}
                        <div class="comments-container">
                            {#if post.comments.length === 0}
                                <p class="no-comments">
                                    Be the first to comment!
                                </p>
                            {:else}
                                {#each post.comments as comment, i}
                                    <div
                                        class="comment"
                                        style="animation-delay: {i * 20}ms"
                                    >
                                        <div class="comment-header">
                                            <div class="comment-avatar">
                                                <User size={14} />
                                            </div>
                                            <div class="comment-user-info">
                                                <span class="comment-username"
                                                    >{comment.username}</span
                                                >
                                                <span class="comment-timestamp"
                                                    >{formatCommentTimestamp(
                                                        comment.timestamp,
                                                    )}</span
                                                >
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
                                on:keypress={(e) =>
                                    e.key === "Enter" &&
                                    handleCommentSubmit(
                                        post.id,
                                        post.newComment,
                                    )}
                            />
                            <button
                                on:click={(e) => {
                                    e.stopPropagation();
                                    handleCommentSubmit(
                                        post.id,
                                        post.newComment,
                                    );
                                }}
                            >
                                <Send size={14} />
                                Send
                            </button>
                        </div>
                    </div>
                {/if}
            </div>
        {/if}
    {/each}
</div>

<style>
    .incidents-table {
        width: 100%;
        min-width: 100%;
        background: var(--card-bg);
        border-radius: 16px;
        overflow: hidden;
        box-shadow:
            0 4px 20px var(--shadow-color),
            0 0 0 1px rgba(0, 0, 0, 0.03);
        margin-bottom: 2rem;
        box-sizing: border-box;
        max-width: 100%;
    }

    .table-header {
        display: flex;
        background: linear-gradient(135deg, #1e3a5f 0%, #0d2137 100%);
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

    .table-row .row-arrow {
        color: var(--text-muted);
        transition: transform 0.2s ease;
        display: flex;
        align-items: center;
        margin-left: auto;
    }

    .table-row.expanded .row-arrow {
        transform: rotate(180deg);
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
        align-items: center;
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
        border-radius: 12px;
    }

    .expanded-info {
        flex: 1;
        display: flex;
        flex-direction: column;
    }

    .expanded-actions {
        display: flex;
        justify-content: center;
        gap: 1rem;
        margin-top: 1rem;
    }

    .post-description {
        font-size: 1rem;
        line-height: 1.5;
        margin-bottom: 1.2rem;
        color: var(--text-darker);
        position: relative;
        text-align: center;
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
    }

    .action-button {
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 0.25rem;
        background: none;
        border: none;
        color: var(--text-muted);
        font-size: 0.9rem;
        font-weight: 600;
        padding: 0.45rem 0.8rem;
        border-radius: 8px;
        cursor: pointer;
        transition: all 0.2s;
    }

    .action-button:hover {
        background-color: var(--hover-bg);
        color: var(--primary-color);
    }

    .like-button.liked {
        color: #e53e3e;
    }

    .button-icon {
        font-size: 1.1rem;
    }

    .full-time {
        display: inline;
    }

    .mobile-time {
        display: none;
    }

    .table-comments-overlay {
        position: absolute;
        top: 20px;
        left: 0;
        width: 100%;
        height: calc(100% - 20px);
        background-color: var(--card-bg);
        display: flex;
        flex-direction: column;
        padding: 1.2rem;
        z-index: 20;
        border-radius: 16px 16px 0 0;
        box-sizing: border-box;
        box-shadow: 0 4px 10px rgba(0, 0, 0, 0.2);
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
    }

    .close-comments:hover {
        opacity: 1;
        transform: scale(1.1);
        background: var(--error-color);
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

    /* Pseudo-element removed */

    .comments-container {
        flex: 1;
        overflow-y: auto;
        padding-right: 0.6rem;
        margin: 0.3rem 0;
        max-height: calc(100% - 90px);
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
    }

    .comment-header {
        display: flex;
        align-items: center;
        gap: 0.4rem;
        margin-bottom: 0.2rem;
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
        font-size: 0.75rem;
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
    }

    .comment-timestamp {
        font-size: 0.7rem;
        color: var(--text-muted);
        padding-left: 0.5rem;
        position: relative;
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
        font-size: 0.9rem;
        line-height: 1.4;
        color: var(--text-darker);
        margin-left: 2rem;
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
    }

    .add-comment input:focus {
        outline: none;
        border-color: var(--primary-color);
        box-shadow: 0 0 0 3px rgba(66, 153, 225, 0.15);
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
    }

    .add-comment button:hover {
        background-color: var(--primary-dark);
    }

    .error-message {
        color: var(--error-color);
        background-color: var(--error-bg);
        border-left: 4px solid var(--error-color);
        padding: 0.6rem 1rem;
        font-size: 0.85rem;
        border-radius: 6px;
    }

    @keyframes fadeIn {
        from {
            opacity: 0;
            transform: translateY(5px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
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

    @media (max-width: 768px) {
        .expanded-content {
            flex-direction: column;
        }
        .expanded-image {
            max-width: 100%;
            width: 100%;
            margin-bottom: 1rem;
            padding-top: 0.5rem;
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
</style>
