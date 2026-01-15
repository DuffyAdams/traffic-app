<script>
    import { onMount } from "svelte";

    export let src;
    export let alt = "";
    export let className = "";
    export let priority = false;

    let img;
    let isLoaded = false;
    let isInView = false;

    // Create intersection observer for lazy loading
    let observer;

    onMount(() => {
        if (priority) {
            // Priority images load immediately
            isInView = true;
        } else {
            // Non-priority images use intersection observer
            observer = new IntersectionObserver(
                (entries) => {
                    entries.forEach((entry) => {
                        if (entry.isIntersecting) {
                            isInView = true;
                            observer.unobserve(entry.target);
                        }
                    });
                },
                {
                    rootMargin: "50px", // Start loading 50px before element enters viewport
                    threshold: 0.1,
                }
            );

            if (img) {
                observer.observe(img);
            }
        }

        return () => {
            if (observer && img) {
                observer.unobserve(img);
            }
        };
    });

    function handleLoad() {
        isLoaded = true;
    }
</script>

{#if isInView}
    <img
        bind:this={img}
        {src}
        {alt}
        class={className}
        class:loaded={isLoaded}
        on:load={handleLoad}
    />
{:else}
    <!-- Placeholder while not in view -->
    <div
        bind:this={img}
        class="image-placeholder {className}"
        class:loaded={isLoaded}
    ></div>
{/if}

<style>
    .image-placeholder {
        background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
        background-size: 200% 100%;
        animation: shimmer 1.5s infinite;
        border-radius: 8px;
    }

    .loaded {
        animation: none;
    }

    @keyframes shimmer {
        0% {
            background-position: -200% 0;
        }
        100% {
            background-position: 200% 0;
        }
    }
</style>