import re

def map_text_to_sections(text: str, tone_hint: str):
    # If markdown-like headings exist, split there
    heads = re.split(r"\n(?=#+\s)", text.strip())
    if len(heads) > 1:
        return heads

    # Otherwise, split by paragraphs and chunk to ~80-120 words/section
    words = text.split()
    sections, chunk = [], []
    for w in words:
        chunk.append(w)
        if len(chunk) >= 100:
            sections.append(" ".join(chunk))
            chunk = []
    if chunk:
        sections.append(" ".join(chunk))
    return sections
