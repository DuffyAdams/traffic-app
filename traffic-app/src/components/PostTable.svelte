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
    import Zap from "lucide-svelte/icons/zap";
    import Heart from "lucide-svelte/icons/heart";
    import MessageSquare from "lucide-svelte/icons/message-square";
    import Share2 from "lucide-svelte/icons/share-2";
    import User from "lucide-svelte/icons/user";
    import X from "lucide-svelte/icons/x";
    import ChevronDown from "lucide-svelte/icons/chevron-down";
    import Send from "lucide-svelte/icons/send";
    import IncidentIcon from "./IncidentIcon.svelte";
    import LazyImage from "./LazyImage.svelte";

    export let posts = [];

    export let expandedPostId = null;

    const dispatch = createEventDispatcher();

    const incidentColors = {
        "Traffic Hazard": "#fbbf24",
        "Traffic Collision": "#ef4444",
        "Car Fire": "#f97316",
        "Report of Fire": "#f97316",
        Fatality: "#991b1b",
        "Hit and Run No Injuries": "#dc2626",
        "Road Closure": "#374151",
        Construction: "#f59e0b",
        "Debris From Vehicle": "#9ca3af",
        "Live or Dead Animal": "#a78bfa",
        "Animal Hazard": "#a78bfa",
        "Defective Traffic Signals": "#eab308",
        JUMPER: "#8b5cf6",
        SPINOUT: "#06b6d4",
        "Wrong Way Driver": "#ec4899",
        "SIG Alert": "#dc2626",
        "Aircraft Emergency": "#3b82f6",
        "Provide Traffic Control": "#6366f1",
        "Assist CT with Maintenance": "#8b5cf6",
        Maintenance: "#6b7280",
        "Request CalTrans Notify": "#64748b",
        "Road Conditions": "#84cc16",
        "Traffic Break": "#0ea5e9",
    };

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
                <span
                    class="incident-icon-small"
                    style="color: {incidentColors[post.type] || '#fbbf24'}"
                >
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
                        <LazyImage
                            src={post.image}
                            alt="Incident location map"
                            className=""
                            priority={i < 3}
                        />
                    </div>
                    <div class="expanded-info">
                        <div class="post-description">
                            {#if post.description}
                                <span class="description-text">
                                    {post.showFullDescription
                                        ? post.description
                                        : truncateDescription(post.description)}
                                </span>
                                {#if post.description.length > 200}
                                    <button
                                        class="more-button"
                                        on:click={(e) =>
                                            handleToggleDescription(e, post.id)}
                                    >
                                        {post.showFullDescription
                                            ? "[-]"
                                            : "[+]"}
                                    </button>
                                {/if}
                            {:else}
                                <span class="no-data">NO DATA AVAILABLE.</span>
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
        background: var(--bg-surface);
        border-radius: 6px;
        border: 1px solid var(--border-color);
        overflow: hidden;
        margin-bottom: 2rem;
        box-sizing: border-box;
        max-width: 100%;
    }

    .table-header {
        display: flex;
        background: var(--bg-surface-elevated);
        color: var(--text-muted);
        font-family: var(--font-mono);
        text-transform: uppercase;
        font-weight: normal;
        padding: 0.75rem 1rem;
        border-bottom: 1px solid var(--border-color);
        width: 100%;
        box-sizing: border-box;
    }

    .table-row {
        display: flex;
        padding: 0.5rem 0.5rem;
        border-bottom: 1px solid var(--border-color);
        background-color: var(--bg-surface);
        cursor: pointer;
        transition: all 0.1s;
        position: relative;
        width: 100%;
        box-sizing: border-box;
        font-family: var(--font-mono);
    }

    .table-row:hover {
        background-color: rgba(51, 102, 255, 0.05);
        border-left: 2px solid var(--accent-primary);
        z-index: 1;
    }

    .table-row.active {
        border-left: 4px solid var(--accent-secondary);
        background-color: rgba(255, 51, 102, 0.05);
    }

    .table-row.expanded {
        background-color: var(--bg-surface-elevated);
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
        border-radius: 6px;
        font-size: 0.75rem;
        font-family: var(--font-mono);
        text-transform: uppercase;
        background-color: var(--bg-surface-elevated);
        border: 1px solid var(--border-color);
        color: var(--text-muted);
    }

    .status-badge.active {
        background-color: rgba(255, 51, 51, 0.1);
        border-color: #ff4d4d;
        color: #ff4d4d;
    }

    .expanded-details {
        background-color: var(--bg-surface-elevated);
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
        border-radius: 6px;
        overflow: hidden;
    }

    .expanded-image :global(img) {
        width: 100%;
        height: 200px;
        object-fit: cover;
        border-radius: 6px;
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
        font-size: 0.85rem;
        line-height: 1.6;
        margin-bottom: 1.25rem;
        color: var(--text-muted);
        position: relative;
        text-align: left;
        font-family: var(--font-mono);
        background: var(--bg-surface-elevated);
        padding: 0.85rem;
        border-left: 2px solid var(--accent-primary);
        border-radius: 0 6px 6px 0;
    }

    .description-text {
        white-space: pre-wrap;
    }

    .no-data {
        color: var(--text-muted);
        opacity: 0.6;
        font-style: italic;
    }

    .more-button {
        background: rgba(51, 102, 255, 0.05);
        border: 1px solid var(--accent-primary);
        color: var(--accent-primary);
        padding: 0.2rem 0.5rem;
        margin-left: 0.5rem;
        margin-top: 0.25rem;
        font-size: 0.7rem;
        font-weight: bold;
        font-family: var(--font-mono);
        cursor: pointer;
        display: inline-flex;
        align-items: center;
        transition: all 0.15s ease;
        text-transform: uppercase;
        border-radius: 4px;
        vertical-align: middle;
    }

    .more-button:hover {
        background: var(--accent-primary);
        color: #000;
        box-shadow: 0 0 8px rgba(51, 102, 255, 0.4);
    }

    .action-button {
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 0.3rem;
        background: rgba(51, 102, 255, 0.05);
        border: 1px solid rgba(51, 102, 255, 0.2);
        color: var(--accent-primary);
        font-family: var(--font-mono);
        text-transform: uppercase;
        font-size: 0.8rem;
        font-weight: bold;
        padding: 0.45rem 1rem;
        border-radius: 6px;
        cursor: pointer;
        transition: all 0.15s;
    }

    .action-button:hover {
        background: rgba(51, 102, 255, 0.15);
        border-color: var(--accent-primary);
        color: #fff;
    }

    @keyframes sharpFlash {
        0% {
            background-color: var(--accent-secondary);
            color: #fff;
            border-color: var(--accent-secondary);
        }
        50% {
            background-color: rgba(255, 51, 51, 0.05);
            color: var(--accent-secondary);
            border-color: rgba(255, 51, 51, 0.3);
        }
        100% {
            background-color: rgba(255, 51, 51, 0.15);
            color: var(--accent-secondary);
            border-color: var(--accent-secondary);
        }
    }

    .like-button.liked {
        color: var(--accent-secondary);
        border-color: var(--accent-secondary);
        animation: sharpFlash 0.3s steps(2);
        background-color: rgba(255, 51, 51, 0.15);
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
        background-color: var(--bg-surface);
        border: 1px solid var(--border-color);
        display: flex;
        flex-direction: column;
        padding: 1.2rem;
        z-index: 20;
        border-radius: 6px 6px 0 0;
        box-sizing: border-box;
    }

    .close-comments {
        position: absolute;
        top: 0.8rem;
        right: 0.8rem;
        background: rgba(255, 51, 51, 0.05);
        border: 1px solid var(--accent-secondary);
        color: var(--accent-secondary);
        font-size: 1rem;
        line-height: 1;
        cursor: pointer;
        z-index: 11;
        width: 24px;
        height: 24px;
        display: flex;
        align-items: center;
        justify-content: center;
        border-radius: 6px;
        padding: 0;
        transition: all 0.15s ease;
        outline: none;
    }

    .close-comments:hover {
        background: var(--accent-secondary);
        color: #000;
    }

    .comments-title {
        font-size: 1.1rem;
        font-family: var(--font-mono);
        color: var(--accent-primary);
        font-weight: normal;
        margin: 0 0 0.8rem 0;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }

    .comments-container {
        flex: 1;
        overflow-y: auto;
        padding-right: 0.6rem;
        margin: 0.3rem 0;
        max-height: calc(100% - 90px);
    }

    .no-comments {
        color: var(--text-muted);
        font-family: var(--font-mono);
        text-transform: uppercase;
        text-align: center;
        padding: 1rem 0;
        background-color: var(--bg-surface-elevated);
        border-radius: 6px;
        opacity: 0.8;
        border: 1px dashed var(--border-color);
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
        background: var(--bg-surface-elevated);
        border: 1px solid var(--border-color);
        color: var(--accent-primary);
        border-radius: 6px;
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
        font-family: var(--font-mono);
        color: var(--text-main);
        font-size: 0.8rem;
    }

    .comment-timestamp {
        font-size: 0.7rem;
        font-family: var(--font-mono);
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
        background-color: rgba(51, 102, 255, 0.05);
        border: 1px solid var(--border-color);
        padding: 0.6rem 0.8rem;
        border-radius: 6px;
        font-size: 0.9rem;
        line-height: 1.4;
        color: var(--text-main);
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
        border-radius: 6px;
        font-family: var(--font-mono);
        font-size: 0.9rem;
        background-color: var(--bg-surface-elevated);
        color: var(--text-main);
    }

    .add-comment input:focus {
        outline: none;
        border-color: var(--accent-primary);
        box-shadow: inset 0 0 0 1px var(--accent-primary);
    }

    .add-comment button {
        background: rgba(51, 102, 255, 0.1);
        color: var(--accent-primary);
        border: 1px solid var(--accent-primary);
        border-radius: 6px;
        padding: 0.7rem 1.2rem;
        font-family: var(--font-mono);
        text-transform: uppercase;
        font-size: 0.9rem;
        cursor: pointer;
        transition: all 0.15s;
        outline: none;
    }

    .add-comment button:hover {
        background: var(--accent-primary);
        color: #fff;
    }

    .error-message {
        color: var(--accent-secondary);
        background-color: rgba(255, 51, 51, 0.1);
        border-left: 2px solid var(--accent-secondary);
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
