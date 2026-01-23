<script>
    import { createEventDispatcher } from "svelte";
    import { slide } from "svelte/transition";
    import CommentOverlay from "./CommentOverlay.svelte";
    import {
        getIconForIncidentType,
        formatTimestamp,
        truncateDescription,
    } from "../utils/helpers.js";
    import {
        Zap,
        Clock,
        MapPin,
        Heart,
        MessageSquare,
        Share2,
    } from "lucide-svelte";
    import IncidentIcon from "./IncidentIcon.svelte";
    import LazyImage from "./LazyImage.svelte";

    export let post;
    export let index = 0;
    export let postsPerPage = 30;

    const dispatch = createEventDispatcher();

    const incidentColors = {
        "Traffic Hazard": "#fbbf24",
        "Traffic Collision": "#ef4444",
        "Car Fire": "#f97316",
        "Report of Fire": "#f97316",
        "Fatality": "#991b1b",
        "Hit and Run No Injuries": "#dc2626",
        "Road Closure": "#374151",
        "Construction": "#f59e0b",
        "Debris From Vehicle": "#9ca3af",
        "Live or Dead Animal": "#a78bfa",
        "Animal Hazard": "#a78bfa",
        "Defective Traffic Signals": "#eab308",
        "JUMPER": "#8b5cf6",
        "SPINOUT": "#06b6d4",
        "Wrong Way Driver": "#ec4899",
        "SIG Alert": "#dc2626",
        "Aircraft Emergency": "#3b82f6",
        "Provide Traffic Control": "#6366f1",
        "Assist CT with Maintenance": "#8b5cf6",
        "Maintenance": "#6b7280",
        "Request CalTrans Notify": "#64748b",
        "Road Conditions": "#84cc16",
        "Traffic Break": "#0ea5e9",
    };

    $: badgeColor = incidentColors[post.type] || "#fbbf24";
    $: isSigAlert = post.type === "SIG Alert";

    function handleLike() {
        dispatch("like", { postId: post.id });
    }

    function handleToggleComments() {
        dispatch("toggleComments", { postId: post.id });
    }

    function handleShare() {
        dispatch("share", { post });
    }

    function handleToggleDescription() {
        dispatch("toggleDescription", { postId: post.id });
    }

    function handleCommentSubmit(event) {
        dispatch("submitComment", {
            postId: post.id,
            comment: event.detail.comment,
        });
    }

    function handleCommentClose() {
        dispatch("toggleComments", { postId: post.id });
    }
</script>

<div
    class="post"
    class:active={post.active}
    class:sig-alert={isSigAlert}
    in:slide={{
        delay: Math.min((index % postsPerPage) * 50, 300),
        duration: 200,
    }}
>
    <div class="post-content">
        <div class="post-image-container">
            <div class="post-badge" class:sig-alert-badge={isSigAlert} style="--badge-color: {badgeColor}">
                <span class="incident-icon">
                    <IncidentIcon type={post.type} />
                </span>
                <span class="incident-type">{post.type}</span>
            </div>
            {#if post.active}
                <div class="active-badge">
                    <span class="active-icon"><Zap size={12} /></span>
                    <span>Active</span>
                </div>
            {/if}
            <LazyImage
                src={post.image}
                alt="Incident location map"
                className="post-image"
                priority={index < 3}
            />
        </div>

        <div class="post-info">
            <div class="post-header">
                <span class="post-time">
                    <Clock size={14} />
                    {post.time}
                </span>
                <span class="post-location">
                    <MapPin size={14} />
                    {post.location}
                </span>
            </div>
            <div class="post-description">
                {#if post.description}
                    {post.showFullDescription
                        ? post.description
                        : truncateDescription(post.description)}
                    {#if post.description.length > 200}
                        <button
                            class="more-button"
                            on:click={handleToggleDescription}
                        >
                            {post.showFullDescription ? "less" : "more"}
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
                    on:click={handleLike}
                >
                    <span class="button-icon">
                        <Heart
                            size={18}
                            fill={post.likes > 0 ? "currentColor" : "none"}
                        />
                    </span>
                    <span>{post.likes > 0 ? post.likes : "Like"}</span>
                </button>
                <button
                    class="action-button comment-button"
                    on:click={handleToggleComments}
                >
                    <span class="button-icon">
                        <MessageSquare size={18} />
                    </span>
                    <span>
                        {post.comments.length > 0
                            ? post.comments.length
                            : "Comment"}
                    </span>
                </button>
                <button
                    class="action-button share-button"
                    on:click={handleShare}
                >
                    <span class="button-icon">
                        <Share2 size={18} />
                    </span>
                    <span>Share</span>
                </button>
            </div>

            {#if post.showComments}
                <CommentOverlay
                    comments={post.comments}
                    newComment={post.newComment}
                    commentError={post.commentError}
                    on:close={handleCommentClose}
                    on:submit={handleCommentSubmit}
                />
            {/if}
        </div>
    </div>
</div>

<style>
    .post {
        flex: 0 0 calc(33.333% - 1.5rem);
        min-width: 300px;
        max-width: 400px;
        box-sizing: border-box;
        background: var(--card-bg);
        border-radius: 18px;
        box-shadow:
            0 4px 20px var(--shadow-color),
            0 0 0 1px rgba(0, 0, 0, 0.03);
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
        box-shadow:
            0 12px 28px var(--shadow-color),
            0 0 0 1px rgba(0, 0, 0, 0.03);
        transform: translateY(-3px);
    }

    .post.active {
        position: relative;
        box-shadow: 0 6px 15px var(--shadow-color);
    }

    .post.sig-alert {
        box-shadow:
            0 4px 20px var(--shadow-color),
            0 0 0 1px rgba(220, 38, 38, 0.15),
            0 0 12px color-mix(in srgb, #dc2626 30%, transparent),
            0 0 24px color-mix(in srgb, #dc2626 20%, transparent),
            0 0 36px color-mix(in srgb, #dc2626 10%, transparent);
    }

    .post.sig-alert:hover {
        box-shadow:
            0 12px 28px var(--shadow-color),
            0 0 0 1px rgba(220, 38, 38, 0.2),
            0 0 18px color-mix(in srgb, #dc2626 35%, transparent),
            0 0 36px color-mix(in srgb, #dc2626 25%, transparent),
            0 0 54px color-mix(in srgb, #dc2626 15%, transparent);
        transform: translateY(-3px);
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
        height: 190px;
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
        box-shadow: 
            0 2px 8px rgba(0, 0, 0, 0.2),
            0 0 4px color-mix(in srgb, var(--badge-color) 40%, transparent),
            0 0 8px color-mix(in srgb, var(--badge-color) 25%, transparent),
            0 0 12px color-mix(in srgb, var(--badge-color) 12%, transparent);
        border: none;
        transition: all 0.3s ease;
    }

    .post-badge:hover {
        box-shadow: 
            0 4px 12px rgba(0, 0, 0, 0.3),
            0 0 6px color-mix(in srgb, var(--badge-color) 50%, transparent),
            0 0 12px color-mix(in srgb, var(--badge-color) 30%, transparent),
            0 0 18px color-mix(in srgb, var(--badge-color) 18%, transparent),
            0 0 24px color-mix(in srgb, var(--badge-color) 8%, transparent);
    }

    .post-badge.sig-alert-badge {
        border: none;
        box-shadow: 
            0 2px 8px rgba(0, 0, 0, 0.2),
            0 0 6px color-mix(in srgb, #dc2626 35%, transparent),
            0 0 12px color-mix(in srgb, #dc2626 25%, transparent),
            0 0 18px color-mix(in srgb, #dc2626 15%, transparent),
            0 0 24px color-mix(in srgb, #dc2626 8%, transparent);
    }

    .post-badge.sig-alert-badge:hover {
        box-shadow: 
            0 4px 12px rgba(0, 0, 0, 0.3),
            0 0 10px color-mix(in srgb, #dc2626 40%, transparent),
            0 0 20px color-mix(in srgb, #dc2626 30%, transparent),
            0 0 30px color-mix(in srgb, #dc2626 20%, transparent),
            0 0 40px color-mix(in srgb, #dc2626 12%, transparent);
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
        border: 1px solid rgba(255, 255, 255, 0.1);
        animation: badgePulse 2s linear infinite;
    }

    .incident-icon {
        display: flex;
        align-items: center;
        justify-content: center;
    }

    .active-icon {
        display: flex;
        align-items: center;
    }

    :global(.post-image) {
        width: 100%;
        height: 100%;
        object-fit: cover;
        border-radius: 8px;
        transition: transform 0.3s ease;
    }

    .post:hover :global(.post-image) {
        transform: scale(1.05);
    }

    /* Keep this as a backup in case the global selector doesn't work */
    .post-image {
        width: 100%;
        height: 100%;
        object-fit: cover;
        border-radius: 8px;
        transition: transform 0.3s ease;
    }

    .post:hover .post-image {
        transform: scale(1.05);
    }

    .post-info {
        padding: 1.4rem;
        padding-bottom: 4rem;
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

    /* Pseudo-elements removed as icons are now inline SVGs */

    .post-description {
        font-size: 1rem;
        line-height: 1.5;
        margin-bottom: 1rem;
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
        display: inline-flex;
        align-items: center;
        transition: color 0.2s ease;
    }

    .more-button:hover {
        color: var(--primary-dark);
        text-decoration: underline;
    }

    .post-actions {
        display: flex;
        justify-content: space-between;
        border-top: 1px solid var(--border-color);
        padding: 1rem 1.4rem 1rem 1.4rem;
        gap: 0.3rem;
        position: absolute;
        bottom: 0;
        left: 0;
        right: 0;
        background: var(--card-bg);
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
        padding: 0.45rem 0;
        border-radius: 8px;
        cursor: pointer;
        transition: all 0.2s;
        outline: none;
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

    .like-button.like-error {
        color: var(--error-color);
        animation: errorShake 0.4s;
        background-color: rgba(229, 62, 62, 0.1);
    }

    @keyframes heartbeat {
        0%,
        100% {
            transform: scale(1);
        }
        50% {
            transform: scale(1.3);
        }
    }

    @keyframes errorShake {
        0%,
        100% {
            transform: translateX(0);
        }
        10%,
        30%,
        50%,
        70%,
        90% {
            transform: translateX(-5px);
        }
        20%,
        40%,
        60%,
        80% {
            transform: translateX(5px);
        }
    }

    @keyframes badgePulse {
        0% {
            box-shadow: 0 0 0 0 rgba(255, 99, 71, 0.7);
        }
        70% {
            box-shadow: 0 0 0 6px rgba(255, 99, 71, 0);
        }
        100% {
            box-shadow: 0 0 0 0 rgba(255, 99, 71, 0);
        }
    }

    /* Mobile responsive styles */
    @media (max-width: 768px) {
        .post {
            flex: 0 0 100%;
            max-width: 100%;
            margin: 0 0 0.8rem 0;
            border-radius: 14px;
        }
        .post-image-container {
            border-radius: 14px 14px 0 0;
        }
        .post-info {
            padding: 1rem 1rem 4rem;
        }
        .post-description {
            font-size: 0.95rem;
            line-height: 1.4;
            margin-bottom: 0.8rem;
        }
    }

    @media (max-width: 480px) {
        .post {
            margin: 0 0 0.5rem 0;
            border-radius: 12px;
        }
        .post-image-container {
            border-radius: 12px 12px 0 0;
        }
        .post-info {
            padding: 0.7rem 0.7rem 4rem;
        }
        .post-header {
            margin-bottom: 0.7rem;
        }
        .post-description {
            font-size: 0.9rem;
            line-height: 1.35;
            margin-bottom: 0.7rem;
        }
        .post-actions {
            gap: 0.2rem;
            padding: 0.7rem 0.7rem 1rem 0.7rem;
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
    }

    @media (max-width: 320px) {
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
            padding: 0.5rem 0.5rem 4rem;
        }
        .post-actions {
            gap: 0.2rem;
            padding: 0.5rem 0.5rem 1rem 0.5rem;
        }
        .action-button {
            padding: 0.3rem 0.1rem;
            font-size: 0.8rem;
            min-height: 44px;
        }
    }
</style>
