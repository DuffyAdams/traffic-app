import feedparser
import json
import os
import re
import time

STATE_FILE = "seen.json"
POLL_INTERVAL_SECONDS = 30

FEEDS = [
    "https://openai.com/news/rss.xml",
    "https://www.anthropic.com/news/rss.xml",
    "https://blog.google/technology/ai/rss/",
    "https://huggingface.co/blog/feed.xml",
]

MODEL_FAMILY_RE = re.compile(
    r"\b(gpt|claude|gemini|llama|mistral|mixtral|deepseek|qwen|phi|grok)\b",
    re.IGNORECASE,
)

RELEASE_CONTEXT_RE = re.compile(
    r"\b(release[ds]?|launch(?:ed|es|ing)?|introduc(?:e|ed|es|ing)|"
    r"announce(?:d|s|ment|ing)|unveil(?:ed|s|ing)|now available|"
    r"general availability|\bga\b|open\s*sourc(?:e|ed)|drop(?:ped|s|ping)?)\b",
    re.IGNORECASE,
)

MODEL_TOKEN_RE = re.compile(
    r"\b(?:gpt|claude|gemini|llama|mistral|mixtral|deepseek|qwen|phi|grok)"
    r"[-\s]?(?:[a-z]*\d+(?:\.\d+)?|[a-z0-9-]{2,})\b",
    re.IGNORECASE,
)

EXCLUDE_TERMS = {
    "policy",
    "safety",
    "research update",
    "hiring",
    "funding",
    "partnership",
    "acquisition",
    "quarterly",
    "earnings",
    "lawsuit",
    "regulation",
    "conference recap",
    "benchmark",
    "tooling",
    "sdk",
    "api update",
    "security",
}


def load_seen():
    if not os.path.exists(STATE_FILE):
        return set()
    with open(STATE_FILE, "r") as f:
        return set(json.load(f))


def save_seen(seen):
    with open(STATE_FILE, "w") as f:
        json.dump(list(seen), f)


def is_model_post(text):
    text_l = text.lower()
    has_family = bool(MODEL_FAMILY_RE.search(text))
    has_release_signal = bool(RELEASE_CONTEXT_RE.search(text))
    has_model_token = bool(MODEL_TOKEN_RE.search(text))

    if not (has_family and has_release_signal and has_model_token):
        return False

    # Ignore broad corporate/industry news unless it clearly looks like a model drop.
    if any(term in text_l for term in EXCLUDE_TERMS):
        if "new model" not in text_l and "foundation model" not in text_l:
            return False

    return True


def check_once():
    seen = load_seen()
    new_seen = set(seen)

    found = 0

    for url in FEEDS:
        feed = feedparser.parse(url)

        for entry in feed.entries:
            uid = entry.get("id", entry.get("link"))

            if uid in seen:
                continue

            title = entry.get("title", "")
            summary = entry.get("summary", "")
            link = entry.get("link", "")

            if is_model_post(title + " " + summary):
                print("\n" + "=" * 60)
                print("🚨 NEW AI MODEL ALERT")
                print("=" * 60)
                print(f"Title : {title}")
                print(f"Source: {feed.feed.get('title', url)}")
                print(f"Link  : {link}")
                print("=" * 60 + "\n")

                found += 1

            new_seen.add(uid)

    save_seen(new_seen)
    return found


if __name__ == "__main__":
    while True:
        print(f"[checking...] {time.strftime('%Y-%m-%d %H:%M:%S')}")
        count = check_once()
        print(f"[done] alerts: {count}")
        time.sleep(POLL_INTERVAL_SECONDS)  # check every 30 seconds