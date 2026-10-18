"""Readable search previews; ranking terms remain separate from display text."""

import html
import json
import re


def plain_text(markdown):
    text = re.sub(r"<!--.*?-->", " ", markdown, flags=re.DOTALL)
    text = re.sub(r"(`{3,}|~{3,})[^\n]*\n.*?\1", " ", text, flags=re.DOTALL)
    text = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"<[^>]*>", " ", text)
    text = re.sub(r"(?m)^\s*(?:#{1,6}\s+|>\s*|[-*+]\s+|\d+[.)]\s+)", "", text)
    text = re.sub(r"(?m)^\s*\|?[\s:|-]+\|?\s*$", " ", text)
    text = re.sub(r"[`*_~|]", " ", text)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def entry(title, url, content, *, preview=None):
    readable = plain_text(content if preview is None else preview) or title
    return {
        "title": title,
        "url": url,
        "text": readable,
        "preview": readable[:240].rstrip() + ("…" if len(readable) > 240 else ""),
        # Include code/diagram/API terms for retrieval without displaying their syntax.
        "keywords": re.sub(r"\s+", " ", content).strip(),
    }


def api_entry(path, method, operation):
    summary = operation.get("summary", "")
    description = operation.get("description", "")
    parameters = " ".join(p.get("name", "") for p in operation.get("parameters", []))
    responses = " ".join(
        str(code) + " " + response.get("description", "")
        for code, response in operation.get("responses", {}).items()
    )
    text = f"{summary} {description} {parameters} {responses}"
    result = entry(method.upper() + " " + path, "/api-explorer", text)
    result["keywords"] += " " + json.dumps(operation, ensure_ascii=False)
    return result
