<script>
    import { createEventDispatcher } from "svelte";
    import { fly } from "svelte/transition";
    import { formatCommentTimestamp } from "../utils/helpers.js";
    import { X, User, MessageSquare, Send } from "lucide-svelte";

    export let comments = [];
    export let newComment = "";
    export let commentError = "";

    const dispatch = createEventDispatcher();

    function handleClose() {
        dispatch("close");
    }

    function handleSubmit() {
        dispatch("submit", { comment: newComment });
    }

    function handleKeyPress(e) {
        if (e.key === "Enter") {
            handleSubmit();
        }
    }
</script>

<div
    class="comments-overlay"
    in:fly={{ y: 400, duration: 400, opacity: 1 }}
    out:fly={{ y: 400, duration: 300, opacity: 1 }}
>
    <button class="close-comments" on:click={handleClose}>
        <X size={20} />
    </button>
    <h3 class="comments-title">
        <MessageSquare size={18} />
        Comments ({comments.length})
    </h3>

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
            bind:value={newComment}
            placeholder="Write a comment..."
            maxlength="150"
            on:keypress={handleKeyPress}
        />
        <button on:click={handleSubmit}>
            <Send size={14} />
            Send
        </button>
    </div>
</div>

<style>
    .comments-overlay {
        position: absolute;
        top: 50px;
        left: 0;
        width: 100%;
        height: calc(100% - 50px);
        background-color: var(--bg-surface);
        border: 1px solid var(--border-color);
        border-bottom: none;
        display: flex;
        flex-direction: column;
        padding: 1.2rem;
        z-index: 10;
        border-radius: 2px 2px 0 0;
        box-sizing: border-box;
        will-change: opacity;
        backface-visibility: hidden;
    }

    .close-comments {
        position: absolute;
        top: 0.8rem;
        right: 0.8rem;
        background: rgba(255, 51, 51, 0.05);
        color: var(--accent-secondary);
        border: 1px solid var(--accent-secondary);
        font-size: 1rem;
        line-height: 1;
        cursor: pointer;
        z-index: 11;
        width: 24px;
        height: 24px;
        display: flex;
        align-items: center;
        justify-content: center;
        border-radius: 2px;
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

    .comments-container::-webkit-scrollbar {
        width: 4px;
    }

    .comments-container::-webkit-scrollbar-track {
        background: var(--border-color);
        border-radius: 0;
    }

    .comments-container::-webkit-scrollbar-thumb {
        background: var(--accent-primary);
        border-radius: 0;
    }

    .no-comments {
        color: var(--text-muted);
        font-family: var(--font-mono);
        text-transform: uppercase;
        text-align: center;
        padding: 1rem 0;
        background-color: var(--bg-surface-elevated);
        border-radius: 2px;
        opacity: 0.8;
        border: 1px dashed var(--border-color);
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
        background: var(--bg-surface-elevated);
        color: var(--accent-primary);
        border-radius: 2px;
        display: flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
        font-size: 0.75rem;
        border: 1px solid var(--border-color);
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
        white-space: nowrap;
    }

    .comment-timestamp {
        font-size: 0.7rem;
        font-family: var(--font-mono);
        color: var(--text-muted);
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
        background-color: rgba(51, 102, 255, 0.05);
        padding: 0.6rem 0.8rem;
        border-radius: 2px;
        border: 1px solid var(--border-color);
        font-size: 0.9rem;
        line-height: 1.4;
        color: var(--text-main);
        margin-left: 2rem;
        word-break: break-word;
        position: relative;
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
        border-radius: 2px;
        font-size: 0.9rem;
        font-family: var(--font-mono);
        background-color: var(--bg-surface-elevated);
        color: var(--text-main);
        transition: all 0.15s;
    }

    .add-comment input:focus {
        outline: none;
        border-color: var(--accent-primary);
        box-shadow: inset 0 0 0 1px var(--accent-primary);
    }

    .add-comment input::placeholder {
        color: var(--text-muted);
    }

    .add-comment button {
        background: rgba(51, 102, 255, 0.1);
        color: var(--accent-primary);
        border: 1px solid var(--accent-primary);
        border-radius: 2px;
        font-family: var(--font-mono);
        text-transform: uppercase;
        padding: 0.7rem 1.2rem;
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
        margin-top: 0.6rem;
        font-size: 0.85rem;
        border-radius: 2px;
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
