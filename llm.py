# llm.py
"""
LLM integration for generating incident descriptions and severity scores.
Uses OpenRouter with a primary + fallback model strategy.
"""

import json

from config import (
    BATCH_LLM_MODEL,
    IMMEDIATE_LLM_MODEL,
    LLM_API_CONFIGURED,
    TESTMODE,
    llm_client,
    print_lock,
)
from logger import safe_print

# Track total LLM calls (thread-safe via print_lock)
_call_count = 0
_batch_call_count = 0


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
    safe_print(f"Immediate LLM calls: {count}")

    is_sig_alert = bool(data.get("Type")) and "SIG" in data.get("Type", "").upper()

    if TESTMODE:
        return (f"Mock incident summary for {data.get('Location')}.", 5 if is_sig_alert else 2)
    if not LLM_API_CONFIGURED:
        return ("Traffic incident reported.", 5 if is_sig_alert else None)

    details = data.get("Details") or []
    if isinstance(details, str):
        details = [details]
    prompt = (
        f"Neighborhood: {data.get('Neighborhood')}\n"
        f"Location: {data.get('Location')} - {data.get('Location Desc.')}\n"
        f"Type: {data.get('Type')}\n"
        f"Details: {', '.join(str(detail) for detail in details)}"
    )
    system_prompt = (
        "You are a traffic incident analyst. Respond ONLY with a valid JSON "
        "object, no markdown or extra text.\n"
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


def generate_batch_descriptions(incidents):
    """Refine a group of incident summaries with the configured batch model.

    The caller supplies database-shaped dictionaries. Results use the caller's
    list position as ``item_id`` so incident numbers that repeat across dates
    cannot collide.
    """
    global _batch_call_count

    if not incidents:
        return []

    with print_lock:
        _batch_call_count += 1
        count = _batch_call_count
    safe_print(
        f"Batch LLM API calls: {count} "
        f"({len(incidents)} incident{'s' if len(incidents) != 1 else ''})"
    )

    payload = [
        _format_batch_incident(index, incident)
        for index, incident in enumerate(incidents, start=1)
    ]

    if TESTMODE:
        return [
            {
                "item_id": item["item_id"],
                "summary": f"Batch-refined incident summary for {item['location']}.",
                "severity": 5 if item["is_sig_alert"] else 2,
            }
            for item in payload
        ]
    if not LLM_API_CONFIGURED:
        raise RuntimeError("GPT_KEY is required for batch LLM refinement")

    system_prompt = (
        "You are a senior San Diego traffic incident analyst. Refine every incident "
        "in the supplied batch independently. Use details from other incidents only "
        "to recognize related events, shared closures, or escalating regional impact; "
        "never merge distinct incident IDs. Return one result for every item_id. "
        "Each summary must be factual, under 200 characters, and may include useful "
        "traffic-related emojis. Do not add warnings, driving advice, hashtags, or "
        "facts absent from the input. Assign severity from 1 to 5: 1 minor, 2 low, "
        "3 moderate, 4 high, 5 critical. SIG alerts must always be severity 5."
    )
    response = llm_client.chat.completions.create(
        model=BATCH_LLM_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": "Refine this traffic incident batch:\n" + json.dumps(payload),
            },
        ],
        temperature=0.2,
        max_tokens=max(512, min(8192, len(payload) * 160)),
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "traffic_batch_refinement",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "incidents": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "item_id": {"type": "integer"},
                                    "summary": {"type": "string"},
                                    "severity": {
                                        "type": "integer",
                                        "minimum": 1,
                                        "maximum": 5,
                                    },
                                },
                                "required": ["item_id", "summary", "severity"],
                                "additionalProperties": False,
                            },
                        }
                    },
                    "required": ["incidents"],
                    "additionalProperties": False,
                },
            },
        },
    )

    usage = getattr(response, "usage", None)
    if usage:
        safe_print(
            "Batch LLM tokens: "
            f"{getattr(usage, 'prompt_tokens', 0)} input, "
            f"{getattr(usage, 'completion_tokens', 0)} output"
        )
    return _parse_batch_response(response, payload)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _call_llm(system_prompt, user_message):
    """Call the configured immediate-summary model."""
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": user_message},
    ]
    return llm_client.chat.completions.create(
        model=IMMEDIATE_LLM_MODEL, messages=messages
    )


def _format_batch_incident(item_id, incident):
    details = incident.get("details", incident.get("Details", []))
    if isinstance(details, str):
        try:
            details = json.loads(details)
        except json.JSONDecodeError:
            details = [details]
    if not isinstance(details, list):
        details = [str(details)]

    incident_type = incident.get("type", incident.get("Type", "")) or ""
    return {
        "item_id": item_id,
        "incident_no": incident.get("incident_no")
        or incident.get("No.")
        or incident.get("Incident No."),
        "timestamp": incident.get("timestamp", incident.get("Timestamp", "")),
        "source": incident.get("source", incident.get("Source", "")),
        "neighborhood": incident.get(
            "neighborhood", incident.get("Neighborhood", "")
        ),
        "location": incident.get("location", incident.get("Location", "")),
        "location_description": incident.get(
            "location_desc", incident.get("Location Desc.", "")
        ),
        "type": incident_type,
        "details": details,
        "immediate_summary": incident.get(
            "description", incident.get("Description", "")
        ),
        "is_sig_alert": "SIG" in incident_type.upper(),
    }


def _parse_batch_response(response, payload):
    """Validate that Gemini returned exactly one usable result per input item."""
    raw = response.choices[0].message.content.strip()
    try:
        parsed = json.loads(raw)
        results = parsed["incidents"]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise ValueError(f"Invalid batch JSON: {raw[:200]}") from exc

    if not isinstance(results, list):
        raise ValueError("Batch response incidents must be a list")

    expected = {item["item_id"]: item for item in payload}
    validated = {}
    for result in results:
        if not isinstance(result, dict):
            raise ValueError("Batch result must be an object")
        try:
            item_id = int(result["item_id"])
            raw_summary = result["summary"]
            if not isinstance(raw_summary, str):
                raise TypeError("summary must be a string")
            summary = raw_summary.strip()
            severity = int(result["severity"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("Batch result contains invalid fields") from exc

        if item_id not in expected or item_id in validated:
            raise ValueError(f"Unexpected or duplicate batch item_id: {item_id}")
        if not summary or len(summary) > 200 or not 1 <= severity <= 5:
            raise ValueError(f"Invalid batch result for item_id: {item_id}")
        if expected[item_id]["is_sig_alert"]:
            severity = 5
        validated[item_id] = {
            "item_id": item_id,
            "summary": summary,
            "severity": severity,
        }

    if set(validated) != set(expected):
        missing = sorted(set(expected) - set(validated))
        raise ValueError(f"Batch response omitted item_id values: {missing}")
    return [validated[item_id] for item_id in sorted(validated)]


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
