# app/lib/recap_llm.py
from __future__ import annotations

import json
import os
from typing import Dict, List, TypedDict

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

# ----- Output schema (loose-typed for resilience) -----
class RecapOut(TypedDict, total=False):
    title: str
    headlines: List[Dict]  # [{"text": "..."}]
    sections: List[Dict]   # [{"title":"...", "body":"..."}]

SYSTEM_PROMPT = """You are 'League Scribe'. Use ONLY the JSON facts the user provides.
Do NOT invent stats, injuries, or rumors. Style=trash-talk, R-rated (no slurs).
Output must be valid JSON with fields:
- title: string
- headlines: array of 3–5 items, each: {"text": "..."} (short bullet-worthy lines)
- sections: array of 2–3 items, each: {"title": "...", "body": "..."} (Markdown allowed)
Max 450 words total across all fields.
"""

def _client() -> OpenAI:
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY missing")
    return OpenAI(api_key=key)

def generate_recap(facts: Dict) -> RecapOut:
    """
    Calls OpenAI to convert computed facts → recap JSON.
    Returns a dict with keys: title, headlines[], sections[].
    """
    client = _client()
    model = os.getenv("OPENAI_MODEL_RECAP", "gpt-5-mini-2025-08-07")

    # Some models (like gpt-5-mini) only support default temperature
    model_params = {
        "model": model,
        "response_format": {"type": "json_object"},  # enforce JSON
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(facts)},
        ],
    }
    
    # Only add temperature if it's not a model that requires default temperature
    if not model.startswith("gpt-5-mini"):
        model_params["temperature"] = 0.3
    
    resp = client.chat.completions.create(**model_params)
    raw = resp.choices[0].message.content or "{}"

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # Fallback minimal structure if model returns malformed JSON
        data = {"title": "Weekly Recap", "headlines": [], "sections": []}

    # Normalize shape
    title = data.get("title") or "Weekly Recap"
    headlines = data.get("headlines") or []
    sections = data.get("sections") or []
    # coerce headlines to [{"text": "..."}]
    norm_headlines = []
    for h in headlines:
        if isinstance(h, dict) and "text" in h:
            norm_headlines.append({"text": str(h["text"])})
        else:
            norm_headlines.append({"text": str(h)})
    # coerce sections to [{"title": "...", "body": "..."}]
    norm_sections = []
    for s in sections:
        if isinstance(s, dict):
            norm_sections.append({
                "title": str(s.get("title", "Section")),
                "body": str(s.get("body", "")),
            })
        else:
            norm_sections.append({"title": "Section", "body": str(s)})

    return {"title": title, "headlines": norm_headlines, "sections": norm_sections}
