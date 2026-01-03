<script>
    import { createEventDispatcher } from "svelte";
    import { fly } from "svelte/transition";
    import { formatCommentTimestamp } from "../utils/helpers.js";

    export let comments = [];
    export let newComment = "";
    export let commentError = "";

    const dispatch = createEventDispatcher();

    function handleClose() {
        dispatch("close");
    }

    function handleSubmit() {
        dispatch("submit");
    }

    function handleKeyPress(e) {
        if (e.key === "Enter") {
            handleSubmit();
        }
    }
</script>

<div
    class="comments-overlay"
    in:fly={{ y: 200, duration: 300 }}
    out:fly={{ y: 200, duration: 200 }}
>
    <button class="close-comments" on:click={handleClose}>×</button>
    <h3 class="comments-title">Comments ({comments.length})</h3>

    {#if commentError}
        <p class="error-message">{commentError}</p>
    {/if}

    <div class="comments-container">
        {#if comments.length === 0}
            <p class="no-comments">Be the first to comment!</p>
        {:else}
            {#each comments as comment, i}
                <div class="comment" style="animation-delay: {i * 20}ms">
                    <div class="comment-header">
                        <div class="comment-avatar">👤</div>
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
            bind:value={newComment}
            placeholder="Write a comment..."
            maxlength="150"
            on:keypress={handleKeyPress}
        />
        <button on:click={handleSubmit}>Send</button>
    </div>
</div>

<style>
    .comments-overlay {
        position: absolute;
        top: 50px;
        left: 0;
        width: 100%;
        height: calc(100% - 50px);
        background-color: var(--card-bg);
        display: flex;
        flex-direction: column;
        padding: 1.2rem;
        z-index: 10;
        border-radius: 18px 18px 0 0;
        box-sizing: border-box;
        box-shadow: 0 4px 10px rgba(0, 0, 0, 0.2);
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
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
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
        box-shadow: 0 2px 6px rgba(0, 0, 0, 0.1);
    }

    .add-comment button:hover {
        background-color: var(--primary-dark);
        box-shadow: 0 4px 10px rgba(0, 0, 0, 0.15);
        transform: translateY(-1px);
    }

    .error-message {
        color: var(--error-color);
        background-color: var(--error-bg);
        border-left: 4px solid var(--error-color);
        padding: 0.6rem 1rem;
        margin-top: 0.6rem;
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
</style>
