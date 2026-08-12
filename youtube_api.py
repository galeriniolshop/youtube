"""YouTube OAuth, channel and upload helpers.

The OAuth flow follows the same practical pattern as the referenced
``serverliveupdate1`` project (authorization URL -> callback/code exchange),
but does not ship a client secret. Configure Google OAuth credentials in
Streamlit secrets or enter them in the app during setup.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Callable

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]
TOKEN_URI = "https://oauth2.googleapis.com/token"


def _google_imports():
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import Flow
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload

        return Request, Credentials, Flow, build, MediaFileUpload
    except ImportError as exc:  # pragma: no cover - exercised on misconfigured deploys
        raise RuntimeError(
            "Dependensi Google belum terpasang. Jalankan pip install -r requirements.txt."
        ) from exc


def normalize_client_config(config: dict[str, Any] | str | None) -> dict[str, Any] | None:
    """Accept a downloaded Google OAuth JSON or its ``web``/``installed`` node."""
    if not config:
        return None
    if isinstance(config, str):
        try:
            config = json.loads(config)
        except json.JSONDecodeError:
            return None
    config = dict(config)
    if "web" in config:
        config = dict(config["web"])
    elif "installed" in config:
        config = dict(config["installed"])
    required = ("client_id", "client_secret")
    if any(not config.get(key) for key in required):
        return None
    config.setdefault("auth_uri", "https://accounts.google.com/o/oauth2/auth")
    config.setdefault("token_uri", TOKEN_URI)
    return config


def manual_client_config(client_id: str, client_secret: str) -> dict[str, Any] | None:
    if not client_id.strip() or not client_secret.strip():
        return None
    return {
        "client_id": client_id.strip(),
        "client_secret": client_secret.strip(),
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": TOKEN_URI,
    }


def create_flow(
    client_config: dict[str, Any], redirect_uri: str, state: str | None = None
):
    _, _, Flow, _, _ = _google_imports()
    config = normalize_client_config(client_config)
    if not config:
        raise ValueError("Google OAuth client config belum lengkap.")
    return Flow.from_client_config(
        {"web": config}, scopes=SCOPES, redirect_uri=redirect_uri, state=state
    )


def authorization_url(
    client_config: dict[str, Any], redirect_uri: str
) -> tuple[str, str]:
    flow = create_flow(client_config, redirect_uri)
    url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    return url, state


def _credential_to_dict(credentials: Any) -> dict[str, Any]:
    expiry = getattr(credentials, "expiry", None)
    expiry_value = expiry.isoformat() if expiry else None
    return {
        "token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri": credentials.token_uri or TOKEN_URI,
        "client_id": credentials.client_id,
        "client_secret": credentials.client_secret,
        "scopes": list(credentials.scopes or SCOPES),
        "expiry": expiry_value,
    }


def exchange_code(
    client_config: dict[str, Any], redirect_uri: str, code: str, state: str | None = None
) -> dict[str, Any]:
    flow = create_flow(client_config, redirect_uri, state=state)
    flow.fetch_token(code=code.strip())
    return _credential_to_dict(flow.credentials)


def credentials_from_token(
    token_info: dict[str, Any], client_config: dict[str, Any] | None = None
):
    _, Credentials, _, _, _ = _google_imports()
    info = dict(token_info)
    if client_config:
        info.setdefault("client_id", client_config.get("client_id"))
        info.setdefault("client_secret", client_config.get("client_secret"))
        info.setdefault("token_uri", client_config.get("token_uri", TOKEN_URI))
    expiry = info.get("expiry")
    if isinstance(expiry, str):
        try:
            info["expiry"] = datetime.fromisoformat(expiry.replace("Z", "+00:00"))
        except ValueError:
            info["expiry"] = None
    info.setdefault("scopes", SCOPES)
    return Credentials(
        token=info.get("token") or info.get("access_token"),
        refresh_token=info.get("refresh_token"),
        token_uri=info.get("token_uri", TOKEN_URI),
        client_id=info.get("client_id"),
        client_secret=info.get("client_secret"),
        scopes=info.get("scopes") or SCOPES,
        expiry=info.get("expiry"),
    )


def build_service(
    token_info: dict[str, Any], client_config: dict[str, Any] | None = None
):
    _, _, _, build, _ = _google_imports()
    credentials = credentials_from_token(token_info, client_config)
    if credentials.expired and credentials.refresh_token:
        Request, _, _, _, _ = _google_imports()
        credentials.refresh(Request())
    return build("youtube", "v3", credentials=credentials, cache_discovery=False)


def channel_profile(service) -> dict[str, Any]:
    response = service.channels().list(part="snippet,statistics", mine=True).execute()
    items = response.get("items", [])
    if not items:
        raise RuntimeError("Akun Google ini belum memiliki channel YouTube aktif.")
    item = items[0]
    snippet = item.get("snippet", {})
    stats = item.get("statistics", {})
    custom_url = snippet.get("customUrl", "")
    return {
        "channel_id": item.get("id", ""),
        "name": snippet.get("title", "Channel YouTube"),
        "handle": custom_url,
        "description": snippet.get("description", ""),
        "thumbnail_url": snippet.get("thumbnails", {}).get("default", {}).get("url", ""),
        "subscribers": int(stats.get("subscriberCount") or 0),
        "total_views": int(stats.get("viewCount") or 0),
        "video_count": int(stats.get("videoCount") or 0),
    }


def channel_videos(service, channel_id: str, limit: int = 10) -> list[dict[str, Any]]:
    search_response = (
        service.search()
        .list(part="snippet", channelId=channel_id, type="video", order="date", maxResults=limit)
        .execute()
    )
    ids = [item.get("id", {}).get("videoId") for item in search_response.get("items", [])]
    ids = [video_id for video_id in ids if video_id]
    if not ids:
        return []
    stats_response = service.videos().list(part="snippet,statistics", id=",".join(ids)).execute()
    videos = []
    for item in stats_response.get("items", []):
        snippet = item.get("snippet", {})
        statistics = item.get("statistics", {})
        videos.append(
            {
                "id": item.get("id", ""),
                "title": snippet.get("title", ""),
                "published_at": snippet.get("publishedAt", ""),
                "views": int(statistics.get("viewCount") or 0),
                "likes": int(statistics.get("likeCount") or 0),
                "comments": int(statistics.get("commentCount") or 0),
                "thumbnail_url": snippet.get("thumbnails", {}).get("medium", {}).get("url", ""),
            }
        )
    return sorted(videos, key=lambda item: item.get("published_at", ""), reverse=True)


def keyword_search(service, query: str, region_code: str = "ID", limit: int = 10) -> dict[str, Any]:
    """Fetch a lightweight, quota-conscious SERP sample for a keyword."""
    query = query.strip()
    if not query:
        raise ValueError("Keyword tidak boleh kosong.")
    search_params = {
        "part": "snippet",
        "q": query,
        "type": "video",
        "order": "relevance",
        "maxResults": min(max(limit, 1), 25),
    }
    if region_code:
        search_params["regionCode"] = region_code
    response = service.search().list(**search_params).execute()
    items = response.get("items", [])
    ids = [item.get("id", {}).get("videoId") for item in items]
    ids = [video_id for video_id in ids if video_id]
    stat_map: dict[str, dict[str, Any]] = {}
    if ids:
        stat_response = service.videos().list(part="snippet,statistics", id=",".join(ids)).execute()
        for item in stat_response.get("items", []):
            stat_map[item.get("id", "")] = item
    results = []
    for item in items:
        video_id = item.get("id", {}).get("videoId", "")
        snippet = item.get("snippet", {})
        stat = stat_map.get(video_id, {}).get("statistics", {})
        results.append(
            {
                "video_id": video_id,
                "title": snippet.get("title", ""),
                "channel_title": snippet.get("channelTitle", ""),
                "published_at": snippet.get("publishedAt", ""),
                "views": int(stat.get("viewCount") or 0),
                "likes": int(stat.get("likeCount") or 0),
                "comments": int(stat.get("commentCount") or 0),
                "url": f"https://www.youtube.com/watch?v={video_id}",
            }
        )
    total_results = int(response.get("pageInfo", {}).get("totalResults") or 0)
    avg_views = round(sum(item["views"] for item in results) / len(results)) if results else 0
    return {
        "query": query,
        "total_results": total_results,
        "sample_size": len(results),
        "average_views": avg_views,
        "results": results,
        "source": "YouTube Data API",
    }


def upload_video(
    service,
    file_path: str,
    title: str,
    description: str,
    tags: list[str] | None = None,
    category_id: str = "22",
    privacy_status: str = "private",
    made_for_kids: bool = False,
    progress_callback: Callable[[float], None] | None = None,
) -> dict[str, Any]:
    """Resumable upload to YouTube with optional progress reporting."""
    _, _, _, _, MediaFileUpload = _google_imports()
    clean_tags: list[str] = []
    tag_length = 0
    for raw_tag in (tags or []):
        tag = str(raw_tag).strip()
        if not tag or len(clean_tags) >= 30:
            continue
        extra = len(tag) + (1 if clean_tags else 0)
        if tag_length + extra > 500:
            break
        clean_tags.append(tag)
        tag_length += extra
    body = {
        "snippet": {
            "title": title.strip()[:100],
            "description": description[:5000],
            "tags": clean_tags,
            "categoryId": str(category_id or "22"),
        },
        "status": {
            "privacyStatus": privacy_status,
            "selfDeclaredMadeForKids": bool(made_for_kids),
        },
    }
    media = MediaFileUpload(file_path, chunksize=8 * 1024 * 1024, resumable=True)
    request = service.videos().insert(part="snippet,status", body=body, media_body=media)
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status and progress_callback:
            progress_callback(float(status.progress()))
    if progress_callback:
        progress_callback(1.0)
    video_id = response.get("id", "")
    return {
        "video_id": video_id,
        "url": f"https://www.youtube.com/watch?v={video_id}" if video_id else "",
        "response": response,
    }


def format_number(value: int | float) -> str:
    value = int(value or 0)
    if value >= 1_000_000_000:
        return f"{value / 1_000_000_000:.1f}B"
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"{value / 1_000:.1f}K"
    return f"{value:,}".replace(",", ".")
