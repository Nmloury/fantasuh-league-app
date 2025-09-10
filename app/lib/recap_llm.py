# app/lib/recap_llm.py
from __future__ import annotations

import hashlib
import json
import os
from typing import Dict, List, Optional, TypedDict

from dotenv import load_dotenv
from openai import OpenAI

from .supa import supa

load_dotenv()

# ----- Output schema (loose-typed for resilience) -----
class RecapOut(TypedDict, total=False):
    title: str
    headlines: List[Dict]  # [{"text": "..."}]
    sections: List[Dict]   # [{"title":"...", "body":"..."}]

SYSTEM_PROMPT = """You are 'League Scribe'. Use ONLY the JSON facts the user provides.
Do NOT invent stats, injuries, or rumors. Style=trash-talk with football references, R-rated (no slurs).
Output must be valid JSON with fields:
- title: string
- headlines: array of 3–5 items, each: {"text": "..."} (short bullet-worthy lines)
- sections: array of 2–3 items, each: {"title": "...", "body": "..."} (Markdown allowed)
Try to include different or complementary information in the sections from what is covered in the headlines.
Max 500 words total across all fields.
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


def _generate_prompt_hash(facts: Dict) -> str:
    """Generate a hash of the facts to detect when inputs change."""
    facts_str = json.dumps(facts, sort_keys=True)
    return hashlib.md5(facts_str.encode()).hexdigest()


def _recap_to_markdown(recap: RecapOut) -> str:
    """Convert recap dict to markdown format for storage."""
    lines = [f"# {recap['title']}", ""]
    
    if recap.get("headlines"):
        for h in recap["headlines"]:
            lines.append(f"- {h.get('text', '')}")
        lines.append("")
    
    if recap.get("sections"):
        for s in recap["sections"]:
            lines.append(f"## {s.get('title', '')}")
            lines.append(s.get("body", ""))
            lines.append("")
    
    return "\n".join(lines)


def insert_recap(league_id: str, week: int, facts: Dict, model: Optional[str] = None) -> Optional[str]:
    """
    Generate and insert a weekly recap into the recaps table.
    
    Args:
        league_id: The league identifier
        week: The week number
        facts: The facts dict to generate recap from
        model: Optional model override (defaults to env var)
    
    Returns:
        The generated recap ID if successful, None if recap already exists
    """
    sb = supa()
    
    # Check if recap already exists for this week
    existing = sb.table("recaps").select("id").eq("league_id", league_id).eq("week", week).execute().data
    if existing:
        return None  # Recap already exists
    
    # Generate the recap
    recap = generate_recap(facts)
    
    # Convert to markdown
    content_md = _recap_to_markdown(recap)
    
    # Generate prompt hash
    prompt_hash = _generate_prompt_hash(facts)
    
    # Get model name
    if model is None:
        model = os.getenv("OPENAI_MODEL_RECAP", "gpt-5-mini-2025-08-07")
    
    # Insert into database
    result = sb.table("recaps").insert({
        "league_id": league_id,
        "week": week,
        "title": recap["title"],
        "content_md": content_md,
        "model": model,
        "prompt_hash": prompt_hash,
        "inputs_json": facts
    }).execute()
    
    if result.data:
        return result.data[0]["id"]
    return None


