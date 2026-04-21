# llm.py
"""
LLM integration for generating incident descriptions and severity scores.
Uses OpenRouter with a primary + fallback model strategy.
"""

import json

from config import llm_client, print_lock, TESTMODE
from logger import safe_print

# Track total LLM calls (thread-safe via print_lock)
_call_count = 0


def generate_description(data):
    """Generate a plain-English summary and 1–5 severity score for an incident.

    Args:
        data: dict with keys Neighborhood, Location, Location Desc., Type, Details.

    Returns:
        (summary: str, severity: int | None)
    """
    global _call_count
    with print_lock:
        _call_count += 1
        count = _call_count
    safe_print(f"GPT API Calls: {count}")

    is_sig_alert = bool(data.get("Type")) and "SIG" in data.get("Type", "").upper()

    if TESTMODE:
        return (f"Mock incident summary for {data.get('Location')}.", 5 if is_sig_alert else 2)

    prompt = (
        f"Neighborhood: {data.get('Neighborhood')}\n"
        f"Location: {data.get('Location')} - {data.get('Location Desc.')}\n"
        f"Type: {data.get('Type')}\n"
        f"Details: {', '.join(data.get('Details', []))}"
    )
    system_prompt = (
        "You are a traffic incident analyst. Respond ONLY with a valid JSON object, no markdown or extra text.\n"
        "The JSON must have exactly two keys:\n"
        '  "summary": a factual, tweet-length summary (under 200 chars) with related emojis. '
        "No warnings, advice, hashtags, or extra commentary.\n"
        '  "severity": an integer from 1 to 5 based on this scale:\n'
        "    1 = minor (very small delay, single vehicle stopped, should clear soon)\n"
        "    2 = low (some lane impact, slowdowns)\n"
        "    3 = moderate (multiple lanes impacted or prolonged delay)\n"
        "    4 = high (road closed, serious collision, emergency response on scene)\n"
        "    5 = critical (major incident, long-duration closure, multiple vehicles or injury)\n"
    )
    user_message = f"Analyze this traffic incident and return JSON.\n{prompt}"

    try:
        response = _call_llm(system_prompt, user_message)
        return _parse_response(response, is_sig_alert)
    except Exception as e:
        safe_print(f"Error generating description: {e}")
        return ("Traffic incident reported.", 5 if is_sig_alert else None)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _call_llm(system_prompt, user_message):
    """Call primary model, fall back to mistral-nemo on failure."""
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": user_message},
    ]
    try:
        return llm_client.chat.completions.create(
            model="openrouter/hunter-alpha", messages=messages
        )
    except Exception as e:
        safe_print(f"Primary model failed: {e}. Falling back to mistralai/mistral-nemo")
        return llm_client.chat.completions.create(
            model="mistralai/mistral-nemo", messages=messages
        )


def _parse_response(response, is_sig_alert):
    """Parse JSON from LLM response; fall back to raw text on error."""
    raw = response.choices[0].message.content.strip()
    try:
        cleaned = raw
        # Strip markdown fences
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        # Extract first JSON object (handles trailing emojis/text)
        brace_start = cleaned.find("{")
        brace_end   = cleaned.rfind("}")
        if brace_start != -1 and brace_end != -1 and brace_end > brace_start:
            cleaned = cleaned[brace_start : brace_end + 1]

        parsed  = json.loads(cleaned)
        summary = str(parsed.get("summary", "")).strip() or raw[:500]
        sev     = parsed.get("severity")
        severity = int(sev) if sev is not None and 1 <= int(sev) <= 5 else None

        if is_sig_alert:
            severity = 5
        return (summary, severity)

    except (json.JSONDecodeError, ValueError, TypeError):
        safe_print(f"Could not parse JSON from LLM, raw response: {raw[:200]}")
        return (raw[:500], 5 if is_sig_alert else None)
