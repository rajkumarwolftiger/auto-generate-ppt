import os, requests
from dotenv import load_dotenv
import json

load_dotenv()

AIPIPE_KEY = os.getenv("AIPIPE_KEY")

if not AIPIPE_KEY:
    raise RuntimeError("❌ AIPIPE_KEY not found. Please set it in .env or Fly.io secrets.")

def _chat(messages):
    url = "https://aipipe.org/openrouter/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {AIPIPE_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        # pick the model you want
        "model": "openai/gpt-4.1-nano",
        "messages": messages,
        "temperature": 0.3
    }

    r = requests.post(url, json=data, headers=headers, timeout=60)

    print("📡 DEBUG RESPONSE:", r.status_code, r.text)  # log raw response

    if r.status_code != 200:
        raise RuntimeError(f"LLM API error {r.status_code}: {r.text}")

    return r.json()["choices"][0]["message"]["content"].strip()


def generate_slide_plan(sections, tone=""):
    prompt = f"""
You are an expert presentation designer.

Task: Create a professional slide plan for the following text sections.

Rules:
- Return ONLY valid JSON (array of objects).
- Each object must have:
  - "title": short, max 6 words
  - "summary": 2–3 sentences summarizing key idea
- Number of slides should match content complexity (not fixed).
- Keep slides focused (1 idea per slide).
- Avoid duplicates.

Tone/style: {tone}

Content Sections:
{sections}
"""
    out = _chat([{"role": "user", "content": prompt}])

    try:
        slides = json.loads(out)
        if isinstance(slides, list) and all("title" in s for s in slides):
            return slides
    except Exception as e:
        print("⚠️ JSON parse failed, raw output:", out, e)

    # fallback: at least 3 slides
    return [
        {"title": "Introduction", "summary": "Overview of the topic."},
        {"title": "Key Insights", "summary": "Main highlights and findings."},
        {"title": "Conclusion", "summary": "Summary and next steps."}
    ]

def refine_slide_bullets(slide, tone=""):
    prompt = f"""
Turn the following summary into 3–5 professional bullet points.

Requirements:
- Each bullet ≤ 12 words
- Clear, concise, action-oriented
- Avoid repetition
- No numbering, no extra commentary

Slide Title: {slide.get('title')}
Summary: {slide.get('summary')}
Tone: {tone}
"""
    out = _chat([{"role": "user", "content": prompt}])

    bullets = [b.strip("-• ").strip() for b in out.splitlines() if b.strip()]
    if not bullets:
        bullets = ["Point 1", "Point 2", "Point 3"]

    return {"title": slide.get("title", ""), "bullets": bullets}

def maybe_notes(slides):
    notes = []
    for s in slides:
        prompt = f"""
Write 2–3 short speaker notes for this slide.

Slide Title: {s['title']}
Slide Bullets: {s['bullets']}

Requirements:
- Conversational, natural language
- Add context, examples, transitions
- 2–3 sentences max
"""
        out = _chat([{"role": "user", "content": prompt}])
        notes.append(out)
    return notes
