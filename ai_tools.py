"""Ollama Cloud helpers and a deterministic offline fallback.

The fallback keeps the Streamlit app useful in a preview or while a user is
setting up Ollama. It is intentionally transparent: generated content is
marked ``fallback`` and should be reviewed before publishing.
"""
from __future__ import annotations

import json
import re
from typing import Any

import requests

DEFAULT_OLLAMA_URL = "https://ollama.com/api"
DEFAULT_MODEL = "gpt-oss:20b"


def _endpoint(base_url: str) -> str:
    value = (base_url or DEFAULT_OLLAMA_URL).strip().rstrip("/")
    if value.endswith("/chat"):
        return value
    return f"{value}/chat"


def ollama_chat(
    api_key: str,
    messages: list[dict[str, str]],
    model: str = DEFAULT_MODEL,
    base_url: str = DEFAULT_OLLAMA_URL,
    timeout: int = 75,
) -> str:
    if not api_key.strip():
        raise ValueError("Ollama Cloud API key belum diisi.")
    response = requests.post(
        _endpoint(base_url),
        headers={
            "Authorization": f"Bearer {api_key.strip()}",
            "Content-Type": "application/json",
        },
        json={
            "model": model.strip() or DEFAULT_MODEL,
            "messages": messages,
            "stream": False,
            "format": "json",
        },
        timeout=timeout,
    )
    if response.status_code >= 400:
        detail = response.text[:300].replace("\n", " ")
        raise RuntimeError(f"Ollama Cloud mengembalikan HTTP {response.status_code}: {detail}")
    data = response.json()
    message = data.get("message", {})
    content = message.get("content") if isinstance(message, dict) else None
    if not content:
        raise RuntimeError("Respons Ollama tidak memiliki message.content.")
    return str(content)


def _parse_json(content: str) -> dict[str, Any]:
    content = content.strip()
    try:
        value = json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, flags=re.DOTALL)
        if not match:
            raise ValueError("Respons AI bukan JSON yang valid.")
        value = json.loads(match.group(0))
    if not isinstance(value, dict):
        raise ValueError("Respons AI harus berupa object JSON.")
    return value


def _split_terms(value: Any) -> list[str]:
    if isinstance(value, list):
        raw = value
    elif isinstance(value, str):
        raw = re.split(r"[,\n|]", value)
    else:
        raw = []
    result: list[str] = []
    for item in raw:
        term = str(item).strip().lstrip("#")
        if term and term.lower() not in {x.lower() for x in result}:
            result.append(term)
    return result


def normalize_metadata(value: dict[str, Any], topic: str = "") -> dict[str, Any]:
    tags = _split_terms(value.get("tags", value.get("tag", [])))[:30]
    keywords = _split_terms(value.get("keywords", value.get("keyword", [])))[:30]
    title = str(value.get("title", "")).strip()[:100]
    description = str(value.get("description", "")).strip()[:5000]
    hashtags = _split_terms(value.get("hashtags", []))[:15]
    if not hashtags:
        hashtags = [term.replace(" ", "") for term in keywords[:3]]
    return {
        "title": title or topic.strip()[:100] or "Video YouTube baru",
        "description": description,
        "tags": tags,
        "keywords": keywords,
        "hashtags": hashtags,
        "seo_notes": str(value.get("seo_notes", value.get("notes", ""))).strip(),
        "source": value.get("source", "ollama-cloud"),
    }


def fallback_metadata(topic: str, niche: str, language: str, tone: str) -> dict[str, Any]:
    topic = topic.strip() or "tips terbaru"
    niche = niche.strip() or "konten digital"
    title = f"{topic.title()} | Panduan {niche.title()} yang Praktis"
    description = (
        f"Di video ini kita membahas {topic} secara praktis untuk kamu yang tertarik dengan {niche}. "
        "Simpan video ini, tulis pertanyaanmu di komentar, dan subscribe untuk tips berikutnya.\n\n"
        f"Topik: {topic}\nKategori: {niche}"
    )
    keywords = [
        topic,
        f"{topic} terbaru",
        f"cara {topic}",
        f"tips {niche}",
        f"tutorial {niche}",
        f"{niche} Indonesia",
    ]
    return normalize_metadata(
        {
            "title": title,
            "description": description,
            "tags": keywords + ["youtube", "tutorial", "tips"],
            "keywords": keywords,
            "hashtags": [niche.replace(" ", ""), "tips", "tutorial"],
            "seo_notes": "Mode fallback aktif. Hubungkan Ollama Cloud untuk riset intent, variasi judul, dan clustering yang lebih dalam.",
            "source": "fallback",
        },
        topic,
    )


def generate_metadata(
    topic: str,
    niche: str = "",
    language: str = "Indonesia",
    tone: str = "Edukatif dan hangat",
    audience: str = "Penonton umum",
    api_key: str = "",
    model: str = DEFAULT_MODEL,
    base_url: str = DEFAULT_OLLAMA_URL,
) -> dict[str, Any]:
    if not api_key.strip():
        return fallback_metadata(topic, niche, language, tone)
    system = (
        "Kamu adalah YouTube SEO strategist. Balas HANYA dengan JSON valid tanpa markdown. "
        "Jangan membuat klaim yang tidak ada di topik. Prioritaskan search intent, CTR yang jujur, "
        "dan keyword long-tail yang relevan."
    )
    prompt = f"""
Buat metadata YouTube untuk video berikut.
Topik: {topic}
Niche: {niche or 'belum ditentukan'}
Bahasa: {language}
Tone: {tone}
Target penonton: {audience}

Schema JSON wajib:
{{
  "title": "maksimal 100 karakter",
  "description": "deskripsi natural 2-4 paragraf, maksimal 5000 karakter",
  "tags": ["10-20 tag relevan tanpa #"],
  "keywords": ["10-20 keyword utama dan long-tail"],
  "hashtags": ["3-5 hashtag tanpa #"],
  "seo_notes": "alasan intent dan saran optimasi thumbnail"
}}
""".strip()
    try:
        response = ollama_chat(
            api_key,
            [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            model=model,
            base_url=base_url,
        )
        result = normalize_metadata(_parse_json(response), topic)
        result["source"] = "ollama-cloud"
        return result
    except Exception as exc:
        fallback = fallback_metadata(topic, niche, language, tone)
        fallback["seo_notes"] = f"Ollama gagal dipanggil ({exc}). {fallback['seo_notes']}"
        fallback["source"] = "fallback-after-error"
        return fallback


def _competition_label(total_results: int, avg_views: int) -> str:
    if total_results >= 10_000_000 or avg_views >= 500_000:
        return "Tinggi"
    if total_results >= 1_000_000 or avg_views >= 100_000:
        return "Sedang"
    return "Rendah"


def heuristic_keyword_analysis(seed: str, niche: str, serp: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    seed = seed.strip()
    words = [word for word in re.split(r"\s+", seed) if word]
    variations = [
        seed,
        f"cara {seed}",
        f"tips {seed}",
        f"{seed} untuk pemula",
        f"{seed} terbaru 2026",
        f"kesalahan {seed}",
        f"tutorial {seed}",
    ]
    if niche.strip():
        variations.extend([f"{seed} {niche.strip()}", f"strategi {seed} {niche.strip()}"])
    rows = []
    for index, keyword in enumerate(dict.fromkeys(variations)):
        score = max(42, 88 - index * 6 - max(0, len(words) - 3) * 2)
        rows.append(
            {
                "keyword": keyword,
                "intent": "Informasional" if any(x in keyword.lower() for x in ("cara", "tips", "tutorial")) else "Eksplorasi",
                "opportunity": score,
                "competition": "Rendah" if score >= 70 else "Sedang",
                "reason": "Long-tail lebih spesifik dan lebih mudah dipasangkan dengan judul yang menjawab kebutuhan penonton.",
            }
        )
    return {
        "seed": seed,
        "summary": "Gunakan keyword utama di awal judul, lalu jawab intent penonton pada 30 detik pertama.",
        "keywords": rows,
        "content_angles": [
            f"Panduan step-by-step: {seed}",
            f"3 kesalahan yang sering terjadi saat {seed}",
            f"Eksperimen dan hasil nyata terkait {seed}",
        ],
        "source": "fallback",
        "serp": serp or [],
    }


def analyze_keywords(
    seed: str,
    niche: str = "",
    language: str = "Indonesia",
    serp: list[dict[str, Any]] | None = None,
    api_key: str = "",
    model: str = DEFAULT_MODEL,
    base_url: str = DEFAULT_OLLAMA_URL,
) -> dict[str, Any]:
    fallback = heuristic_keyword_analysis(seed, niche, serp)
    if not api_key.strip():
        return fallback
    compact_serp = (serp or [])[:10]
    prompt = f"""
Analisis keyword YouTube dalam bahasa {language}.
Seed keyword: {seed}
Niche: {niche or 'umum'}
Contoh hasil pencarian YouTube (boleh kosong): {json.dumps(compact_serp, ensure_ascii=False)}

Balas hanya JSON valid dengan schema:
{{
  "summary": "ringkasan peluang",
  "keywords": [
    {{"keyword":"...", "intent":"Informasional/Komersial/Navigasi", "opportunity": 0, "competition":"Rendah/Sedang/Tinggi", "reason":"..."}}
  ],
  "content_angles": ["3 ide angle konten"],
  "watchouts": ["risiko atau hal yang perlu divalidasi"]
}}
Buat 8-12 keyword, opportunity angka 0-100. Jangan mengarang volume pencarian.
""".strip()
    try:
        response = ollama_chat(
            api_key,
            [
                {
                    "role": "system",
                    "content": "Kamu adalah analis keyword YouTube yang konservatif dan fokus pada search intent.",
                },
                {"role": "user", "content": prompt},
            ],
            model=model,
            base_url=base_url,
        )
        value = _parse_json(response)
        keywords = value.get("keywords") if isinstance(value.get("keywords"), list) else []
        clean_keywords = []
        for item in keywords[:20]:
            if not isinstance(item, dict) or not str(item.get("keyword", "")).strip():
                continue
            try:
                opportunity = max(0, min(100, int(float(item.get("opportunity", 0)))))
            except (TypeError, ValueError):
                opportunity = 0
            clean_keywords.append(
                {
                    "keyword": str(item.get("keyword")).strip(),
                    "intent": str(item.get("intent", "Informasional")),
                    "opportunity": opportunity,
                    "competition": str(item.get("competition", "Sedang")),
                    "reason": str(item.get("reason", "")),
                }
            )
        if not clean_keywords:
            return fallback
        return {
            "seed": seed.strip(),
            "summary": str(value.get("summary", fallback["summary"])),
            "keywords": clean_keywords,
            "content_angles": [str(x) for x in value.get("content_angles", [])][:6],
            "watchouts": [str(x) for x in value.get("watchouts", [])][:6],
            "source": "ollama-cloud",
            "serp": serp or [],
        }
    except Exception as exc:
        fallback["summary"] = f"Ollama gagal dipanggil ({exc}). {fallback['summary']}"
        fallback["source"] = "fallback-after-error"
        return fallback


def score_serp_result(result: dict[str, Any]) -> dict[str, Any]:
    total = int(result.get("total_results") or 0)
    avg_views = int(result.get("average_views") or 0)
    return {
        "competition": _competition_label(total, avg_views),
        "total_results": total,
        "average_views": avg_views,
        "opportunity": max(10, min(98, 90 - min(60, round(total / 200_000)) + min(25, round(avg_views / 20_000)))),
    }
