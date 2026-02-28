<script>
    import { createEventDispatcher } from "svelte";
    import { slide, fly } from "svelte/transition";
    import CommentOverlay from "./CommentOverlay.svelte";
    import {
        getIconForIncidentType,
        formatTimestamp,
        truncateDescription,
    } from "../utils/helpers.js";
    import Zap from "lucide-svelte/icons/zap";
    import Clock from "lucide-svelte/icons/clock";
    import MapPin from "lucide-svelte/icons/map-pin";
    import Heart from "lucide-svelte/icons/heart";
    import MessageSquare from "lucide-svelte/icons/message-square";
    import Share2 from "lucide-svelte/icons/share-2";
    import Info from "lucide-svelte/icons/info";
    import X from "lucide-svelte/icons/x";
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
        // Police
        "AUTO THEFT": "#3b82f6",
        "MISD HIT/RUN": "#ef4444",
        VANDALISM: "#8b5cf6",
        ROBBERY: "#1d4ed8",
        "SUICIDE-THREATS": "#9333ea",
        "DISTURBING PEACE": "#6366f1",
        "REPORT OF DEATH": "#000000",
        "PRISONER IN CUSTODY": "#374151",
        "MENTAL CASE": "#ec4899",
        // Fire
        MEDICAL: "#ef4444",
        "STRUCTURE FIRE": "#b91c1c",
        "VEGETATION FIRE": "#166534",
        "TRAFFIC ACCIDENT": "#f59e0b",
    };

    $: badgeColor = incidentColors[post.type] || "#fbbf24";
    $: isSigAlert = post.type === "SIG Alert";

    let showRawDetails = false;

    function toggleRawDetails() {
        showRawDetails = !showRawDetails;
    }

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
            <div
                class="post-badge"
                class:sig-alert-badge={isSigAlert}
                style="--badge-color: {badgeColor}"
            >
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
            {#if post.details && post.details.length > 0}
                <button
                    class="raw-details-button"
                    on:click={toggleRawDetails}
                    title="View raw details"
                >
                    <Info size={12} />
                    <span class="details-text">Details</span>
                </button>
            {/if}
            <div
                class={`placeholder-container ${post.active ? "active" : ""}`}
                style="--bg-color: {badgeColor}"
            >
                {#if post.image && post.image !== "/maps/" && post.image !== "/maps/"}
                    <LazyImage
                        src={post.image}
                        alt="Incident location map"
                        className="post-image"
                        priority={index < 3}
                    />
                {:else}
                    <div class="placeholder-content">
                        <IncidentIcon type={post.type} size={48} />
                    </div>
                {/if}
            </div>
            {#if showRawDetails}
                <div
                    class="raw-details-inline-overlay"
                    transition:fly={{ y: 200, duration: 300 }}
                >
                    <div class="raw-details-inline-header">
                        <h4>Raw Event Details</h4>
                        <button
                            class="close-inline-button"
                            on:click={() => (showRawDetails = false)}
                        >
                            <X size={16} />
                        </button>
                    </div>
                    <div class="raw-details-inline-content">
                        {#each post.details as detail}
                            <div class="detail-item">{detail}</div>
                        {/each}
                    </div>
                </div>
            {/if}
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
                    <span class="description-text">
                        {post.showFullDescription
                            ? post.description
                            : truncateDescription(post.description)}
                    </span>
                    {#if post.description.length > 200}
                        <button
                            class="more-button"
                            on:click={handleToggleDescription}
                        >
                            {post.showFullDescription ? "[-]" : "[+]"}
                        </button>
                    {/if}
                {:else}
                    <span class="no-data">NO DATA AVAILABLE.</span>
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
        background: var(--bg-surface);
        border-radius: 6px;
        border: 1px solid var(--border-color);
        transition: all 0.15s ease-out;
        position: relative;
        display: flex;
        flex-direction: column;
        margin-bottom: 2rem;
        width: 100%;
        overflow: hidden;
        transform: translateZ(0);
    }

    .post:hover {
        border-color: var(--accent-primary);
        box-shadow: inset 0 0 0 1px rgba(51, 102, 255, 0.2);
    }

    .post.active {
        position: relative;
    }

    .post.sig-alert {
        border-color: var(--accent-secondary);
        background: var(--bg-surface-elevated);
        animation: retroPulse 1.5s infinite alternate;
    }

    .post.sig-alert:hover {
        border-color: #ff4d4d;
        box-shadow:
            0 0 15px rgba(255, 51, 51, 0.5),
            inset 0 0 5px rgba(255, 51, 51, 0.3);
    }

    @keyframes retroPulse {
        0% {
            box-shadow:
                0 0 4px rgba(255, 51, 51, 0.2),
                inset 0 0 2px rgba(255, 51, 51, 0.1);
            border-color: rgba(255, 51, 51, 0.4);
        }
        100% {
            box-shadow:
                0 0 12px rgba(255, 51, 51, 0.6),
                inset 0 0 4px rgba(255, 51, 51, 0.3);
            border-color: var(--accent-secondary);
        }
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
        border-bottom: 1px solid var(--border-color);
        background-color: #000;
        border-radius: 6px 6px 0 0;
    }

    .placeholder-container {
        width: 100%;
        height: 100%;
        position: relative;
    }

    .placeholder-content {
        width: 100%;
        height: 100%;
        display: flex;
        align-items: center;
        justify-content: center;
        background: linear-gradient(
            135deg,
            var(--bg-color) 0%,
            var(--card-bg) 100%
        );
        opacity: 0.8;
        color: var(--text-muted);
    }

    .post-badge {
        position: absolute;
        top: 0.8rem;
        left: 0.8rem;
        background-color: var(--bg-surface-elevated);
        color: var(--badge-color);
        padding: 0.3rem 0.6rem;
        border-radius: 6px;
        border: 1px solid var(--badge-color);
        font-family: var(--font-mono);
        text-transform: uppercase;
        font-size: 0.75rem;
        font-weight: bold;
        display: flex;
        align-items: center;
        gap: 0.4rem;
        z-index: 1;
        transition: all 0.15s ease;
    }

    .post-badge:hover {
        background-color: var(--badge-color);
        color: #000;
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
        background-color: var(--accent-secondary);
        color: #fff;
        padding: 0.25rem 0.5rem;
        border-radius: 6px;
        font-family: var(--font-mono);
        text-transform: uppercase;
        font-size: 0.7rem;
        font-weight: bold;
        display: flex;
        align-items: center;
        gap: 0.25rem;
        z-index: 1;
        border: 1px solid #ff4d4d;
        box-shadow: 0 0 10px rgba(255, 51, 51, 0.3);
    }

    .raw-details-button {
        position: absolute;
        bottom: 0.6rem;
        left: 0.6rem;
        background-color: rgba(0, 0, 0, 0.65);
        color: white;
        border: none;
        border-radius: 6px;
        height: 26px;
        padding: 0 7px;
        display: flex;
        align-items: center;
        justify-content: center;
        cursor: pointer;
        z-index: 2;
        backdrop-filter: blur(8px);
        box-shadow: 0 2px 6px #0003;
        transition:
            background-color 0.2s ease,
            transform 0.15s ease;
        font-size: 0.65rem;
        font-weight: 600;
    }

    .raw-details-button :global(svg) {
        flex-shrink: 0;
    }

    .raw-details-button .details-text {
        max-width: 0;
        opacity: 0;
        margin-left: 0;
        overflow: hidden;
        white-space: nowrap;
        transition:
            max-width 0.25s ease,
            opacity 0.2s ease,
            margin-left 0.25s ease;
    }

    .raw-details-button:hover {
        background-color: rgba(0, 0, 0, 0.85);
        transform: scale(1.05);
    }

    .raw-details-button:hover .details-text {
        max-width: 50px;
        opacity: 1;
        margin-left: 5px;
    }

    .raw-details-inline-overlay {
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background-color: rgba(0, 0, 0, 0.92);
        display: flex;
        flex-direction: column;
        z-index: 10;
        border-radius: 6px 6px 0 0;
        overflow: hidden;
    }

    .raw-details-inline-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 0.75rem 1rem;
        border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        flex-shrink: 0;
    }

    .raw-details-inline-header h4 {
        margin: 0;
        font-size: 0.9rem;
        font-weight: 600;
        color: white;
    }

    .close-inline-button {
        background: rgba(255, 255, 255, 0.1);
        border: none;
        color: white;
        cursor: pointer;
        padding: 0.3rem;
        display: flex;
        align-items: center;
        justify-content: center;
        border-radius: 6px;
        transition: all 0.2s;
    }

    .close-inline-button:hover {
        background-color: rgba(255, 255, 255, 0.2);
    }

    .raw-details-inline-content {
        padding: 0.75rem 1rem;
        overflow-y: auto;
        flex: 1;
    }

    .detail-item {
        padding: 0.5rem 0;
        border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        font-size: 0.8rem;
        color: rgba(255, 255, 255, 0.9);
        line-height: 1.4;
    }

    .detail-item:last-child {
        border-bottom: none;
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
        border-radius: 6px 6px 0 0;
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
        border-radius: 6px 6px 0 0;
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

    .post-actions {
        display: flex;
        justify-content: space-between;
        border-top: 1px dashed var(--border-color);
        padding: 0.75rem 1rem;
        gap: 0.5rem;
        position: absolute;
        bottom: 0;
        left: 0;
        right: 0;
        background: var(--bg-surface);
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
        padding: 0.4rem 0;
        border-radius: 6px;
        cursor: pointer;
        transition: all 0.15s;
        flex: 1;
        max-width: calc(100% / 3);
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

    .like-button.liked:hover {
        background-color: rgba(255, 51, 51, 0.25);
    }

    .button-icon {
        font-size: 1.1rem;
    }

    .like-button.like-error {
        color: var(--accent-secondary);
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
            border-radius: 6px;
        }
        .post-image-container {
            border-radius: 6px 6px 0 0;
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
            border-radius: 6px;
        }
        .post-image-container {
            border-radius: 6px 6px 0 0;
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
            border-radius: 2px;
            min-width: unset;
            max-width: 100%;
        }
        .post-image-container {
            border-radius: 2px 2px 0 0;
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
