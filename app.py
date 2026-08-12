from __future__ import annotations

import html
import json
import os
import re
import uuid
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

import ai_tools
import storage
import video_tools
import youtube_api

APP_NAME = "Orbit Studio"
APP_TAGLINE = "YouTube operations, dibuat lebih rapi."
NAV_ITEMS = ["Dashboard", "Channel manager", "Media studio", "SEO lab", "Scheduler", "Analytics"]
TIMEZONES = ["Asia/Jakarta", "Asia/Makassar", "Asia/Jayapura", "Asia/Singapore", "UTC"]
# Quick-connect OAuth profile from the supplied reference project.
# WARNING: this client secret is now part of the source code. Rotate/revoke
# the credential in Google Cloud before using this repository publicly.
PREDEFINED_OAUTH_CONFIG = {
    "web": {
        "client_id": "1086578184958-hin4d45sit9ma5psovppiq543eho41sl.apps.googleusercontent.com",
        "project_id": "anjelikakozme",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "client_secret": "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",
        "redirect_uris": ["https://livenews1x.streamlit.app"],
    }
}

CATEGORIES = {
    "22": "People & Blogs",
    "27": "Education",
    "28": "Science & Technology",
    "24": "Entertainment",
    "20": "Gaming",
    "26": "Howto & Style",
    "10": "Music",
    "25": "News & Politics",
    "17": "Sports",
    "19": "Travel & Events",
}

st.set_page_config(
    page_title=f"{APP_NAME} · YouTube manager",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="expanded",
)


# -------------------------------------------------------------------------
# Presentation helpers
# -------------------------------------------------------------------------

st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Space+Grotesk:wght@500;600;700&display=swap');
:root { --ink:#edf2ff; --muted:#8994b0; --line:rgba(148,163,184,.14); --panel:#111a2f; --panel-2:#0e172a; --accent:#8b7cff; --teal:#54dfc1; }
html, body, [class*="css"] { font-family:'DM Sans',sans-serif; }
.stApp { background: radial-gradient(circle at 78% -18%, rgba(109,91,255,.19), transparent 33%), #080d1b; color:var(--ink); }
[data-testid="stSidebar"] { background:linear-gradient(180deg,#0c1326 0%,#0a1020 100%); border-right:1px solid var(--line); }
[data-testid="stSidebar"] > div:first-child { padding:1.2rem .9rem; }
.block-container { padding:2.2rem 3.2rem 3.5rem; max-width:1500px; }
section[data-testid="stSidebar"] .stRadio label { font-size:.86rem; }
section[data-testid="stSidebar"] [data-baseweb="radio"] { padding:.44rem .6rem; border-radius:10px; }
section[data-testid="stSidebar"] [data-baseweb="radio"]:has(input:checked) { background:rgba(139,124,255,.15); }
[data-testid="stMetric"] { background:linear-gradient(145deg, rgba(20,31,56,.96), rgba(13,22,41,.96)); border:1px solid var(--line); border-radius:16px; padding:1rem 1.15rem; }
[data-testid="stMetricLabel"] { color:var(--muted); font-size:.77rem; }
[data-testid="stMetricValue"] { font-family:'Space Grotesk',sans-serif; font-size:1.7rem; }
.stButton > button, .stDownloadButton > button { border:1px solid rgba(139,124,255,.35); background:rgba(139,124,255,.1); color:#eef0ff; border-radius:10px; font-weight:600; transition:.2s; }
.stButton > button:hover, .stDownloadButton > button:hover { border-color:var(--accent); background:rgba(139,124,255,.22); color:white; }
[data-testid="stLinkButton"] a { border-radius:10px; font-weight:600; }
[data-testid="stTextInput"] input, [data-testid="stTextArea"] textarea, [data-baseweb="select"] > div, [data-testid="stDateInput"] input, [data-testid="stTimeInput"] input { background:#0b1427; border-color:var(--line); border-radius:10px; color:var(--ink); }
[data-testid="stFileUploader"] { background:rgba(17,26,47,.65); border:1px dashed rgba(139,124,255,.4); border-radius:14px; padding:.3rem; }
[data-testid="stExpander"] { border:1px solid var(--line); background:rgba(14,23,42,.55); border-radius:13px; }
[data-testid="stDataFrame"] { border:1px solid var(--line); border-radius:14px; overflow:hidden; }
hr { border-color:var(--line); }
.hero { padding:1.6rem 1.7rem; border:1px solid rgba(139,124,255,.22); border-radius:21px; background:linear-gradient(120deg,rgba(39,42,93,.78),rgba(15,28,50,.83)); box-shadow:0 18px 55px rgba(0,0,0,.18); margin-bottom:1.25rem; }
.hero-kicker { color:#bcb4ff; text-transform:uppercase; letter-spacing:.12em; font-size:.68rem; font-weight:700; margin-bottom:.5rem; }
.hero h1 { font-family:'Space Grotesk',sans-serif; font-size:2.05rem; line-height:1.1; margin:0 0 .55rem; color:#fff; }
.hero p { color:#b0bad2; max-width:680px; margin:0; line-height:1.6; }
.section-title { font-family:'Space Grotesk',sans-serif; color:#fff; font-size:1.25rem; font-weight:700; margin:1.45rem 0 .2rem; }
.section-subtitle { color:var(--muted); font-size:.88rem; margin:0 0 .9rem; }
.panel { background:linear-gradient(145deg,rgba(18,29,52,.94),rgba(11,20,37,.94)); border:1px solid var(--line); border-radius:17px; padding:1.12rem 1.2rem; height:100%; }
.panel-title { color:#f8f9ff; font-weight:700; font-size:.95rem; margin-bottom:.28rem; }
.panel-copy { color:var(--muted); font-size:.79rem; line-height:1.5; }
.pill { display:inline-block; padding:.25rem .55rem; margin:.16rem .16rem 0 0; border-radius:99px; font-size:.7rem; font-weight:600; background:rgba(84,223,193,.1); border:1px solid rgba(84,223,193,.22); color:#8debd8; }
.pill-purple { background:rgba(139,124,255,.12); border-color:rgba(139,124,255,.28); color:#c4beff; }
.pill-muted { background:rgba(148,163,184,.1); border-color:var(--line); color:#b7c0d5; }
.channel-card { background:linear-gradient(145deg,rgba(18,29,52,.95),rgba(11,20,37,.95)); border:1px solid var(--line); border-radius:16px; padding:1rem; margin-bottom:.65rem; }
.channel-avatar { width:42px; height:42px; border-radius:13px; display:flex; align-items:center; justify-content:center; background:linear-gradient(135deg,#8b7cff,#55d8c1); color:#0a1020; font-family:'Space Grotesk'; font-weight:700; font-size:1.05rem; }
.channel-name { color:#fff; font-weight:700; font-size:.96rem; }
.channel-meta { color:var(--muted); font-size:.75rem; margin-top:.18rem; }
.status-dot { display:inline-block; width:7px; height:7px; border-radius:50%; background:#54dfc1; margin-right:.35rem; box-shadow:0 0 10px #54dfc1; }
.status-dot-warn { background:#f6c96b; box-shadow:0 0 10px #f6c96b; }
.status-dot-danger { background:#ff7f96; box-shadow:0 0 10px #ff7f96; }
.empty { text-align:center; border:1px dashed rgba(148,163,184,.25); border-radius:16px; padding:2.3rem 1.5rem; color:var(--muted); background:rgba(14,23,42,.35); }
.empty strong { display:block; color:#e8ecfb; font-size:1rem; margin-bottom:.35rem; }
.small-note { color:var(--muted); font-size:.73rem; line-height:1.5; }
.callout { border-left:3px solid var(--teal); background:rgba(84,223,193,.07); border-radius:0 10px 10px 0; padding:.65rem .8rem; color:#b7e9df; font-size:.8rem; }
.queue-badge { display:inline-block; padding:.28rem .58rem; border-radius:8px; font-size:.7rem; font-weight:700; }
</style>
""",
    unsafe_allow_html=True,
)


def e(value: Any) -> str:
    return html.escape(str(value or ""))


def secret_value(name: str, default: Any = "") -> Any:
    """Read a root secret, then common [youtube]/[ollama] sections, safely."""
    try:
        value = st.secrets.get(name)
        if value not in (None, ""):
            return value
    except Exception:
        pass
    section_names = []
    lowered = name.lower()
    if "youtube" in lowered or "token" in lowered:
        section_names.append("youtube")
    if "ollama" in lowered:
        section_names.append("ollama")
    try:
        for section_name in section_names:
            section = st.secrets.get(section_name, {})
            if hasattr(section, "get"):
                value = section.get(name)
                if value in (None, ""):
                    value = section.get(name.lower())
                if value not in (None, ""):
                    return value
    except Exception:
        pass
    return os.getenv(name, default)


def get_default_redirect_uri() -> str:
    configured = str(secret_value("YOUTUBE_REDIRECT_URI", "") or "").strip()
    if configured:
        return configured
    try:
        host = st.context.headers.get("Host", "")
        if host:
            scheme = "https" if not host.startswith(("localhost", "127.0.0.1")) else "http"
            return f"{scheme}://{host}"
    except Exception:
        pass
    return "http://localhost:8501"


def get_configured_client() -> dict[str, Any] | None:
    raw = secret_value("YOUTUBE_CLIENT_CONFIG", "")
    config = youtube_api.normalize_client_config(raw)
    if config:
        return config
    client_id = secret_value("YOUTUBE_CLIENT_ID", "")
    client_secret = secret_value("YOUTUBE_CLIENT_SECRET", "")
    return youtube_api.manual_client_config(str(client_id or ""), str(client_secret or ""))


def get_predefined_client() -> dict[str, Any] | None:
    """Return the supplied one-click OAuth profile."""
    return youtube_api.normalize_client_config(PREDEFINED_OAUTH_CONFIG)


def init_state() -> None:
    defaults = {
        "nav": "Dashboard",
        "active_channel_id": "",
        "oauth_state": "",
        "oauth_redirect_uri": "",
        "processed_oauth_codes": [],
        "oauth_config_override": None,
        "services": {},
        "generated_metadata": {},
        "keyword_result": None,
        "last_created_jobs": [],
        "processed_upload_keys": [],
        "timezone": "Asia/Jakarta",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
    if "ollama_key_input" not in st.session_state:
        st.session_state["ollama_key_input"] = str(secret_value("OLLAMA_API_KEY", "") or "")
    if "ollama_model_input" not in st.session_state:
        st.session_state["ollama_model_input"] = str(secret_value("OLLAMA_MODEL", ai_tools.DEFAULT_MODEL) or ai_tools.DEFAULT_MODEL)
    if "ollama_url_input" not in st.session_state:
        st.session_state["ollama_url_input"] = str(secret_value("OLLAMA_BASE_URL", ai_tools.DEFAULT_OLLAMA_URL) or ai_tools.DEFAULT_OLLAMA_URL)


def initials(name: str) -> str:
    words = [part for part in str(name).split() if part]
    if not words:
        return "YT"
    return "".join(word[0] for word in words[:2]).upper()


def metric_card(label: str, value: str, helper: str = "") -> None:
    st.markdown(
        f'<div class="panel"><div class="panel-copy">{e(label)}</div>'
        f'<div style="font-family:Space Grotesk;font-weight:700;font-size:1.55rem;color:#fff;margin:.35rem 0 .15rem">{e(value)}</div>'
        f'<div class="small-note">{e(helper)}</div></div>',
        unsafe_allow_html=True,
    )


def empty_state(title: str, copy: str) -> None:
    st.markdown(f'<div class="empty"><strong>{e(title)}</strong>{e(copy)}</div>', unsafe_allow_html=True)


def hero(kicker: str, title: str, copy: str) -> None:
    st.markdown(
        f'<div class="hero"><div class="hero-kicker">{e(kicker)}</div><h1>{e(title)}</h1><p>{e(copy)}</p></div>',
        unsafe_allow_html=True,
    )


def page_header(title: str, subtitle: str) -> None:
    st.markdown(f'<div class="section-title">{e(title)}</div><div class="section-subtitle">{e(subtitle)}</div>', unsafe_allow_html=True)


def csv_terms(value: str) -> list[str]:
    return [term.strip().lstrip("#") for term in re.split(r"[,\n|]", value or "") if term.strip()]


def pretty_datetime(value: str | None, local_tz: str = "Asia/Jakarta") -> str:
    if not value:
        return "Sekarang"
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        parsed = parsed.astimezone(ZoneInfo(local_tz))
        return parsed.strftime("%d %b %Y · %H:%M")
    except (ValueError, TypeError):
        return str(value)


def status_label(status: str) -> str:
    return {
        "queued": "Menunggu",
        "processing": "Mengunggah",
        "published": "Terbit",
        "failed": "Gagal",
        "draft": "Draft",
    }.get(status, status.title())


def configured_ollama() -> tuple[str, str, str]:
    return (
        str(st.session_state.get("ollama_key_input", "") or ""),
        str(st.session_state.get("ollama_model_input", ai_tools.DEFAULT_MODEL) or ai_tools.DEFAULT_MODEL),
        str(st.session_state.get("ollama_url_input", ai_tools.DEFAULT_OLLAMA_URL) or ai_tools.DEFAULT_OLLAMA_URL),
    )


# -------------------------------------------------------------------------
# Sidebar and OAuth
# -------------------------------------------------------------------------

def render_sidebar() -> tuple[dict[str, Any] | None, str]:
    configured = get_configured_client()
    with st.sidebar:
        st.markdown(
            '<div style="padding:.2rem .35rem 1.1rem"><div style="font-family:Space Grotesk;font-size:1.35rem;font-weight:700;color:#fff">◈ Orbit <span style="color:#8b7cff">Studio</span></div><div class="small-note" style="margin-top:.25rem">YouTube operations console</div></div>',
            unsafe_allow_html=True,
        )
        st.session_state["nav"] = st.radio(
            "Workspace",
            NAV_ITEMS,
            index=NAV_ITEMS.index(st.session_state.get("nav", "Dashboard")),
            label_visibility="collapsed",
        )
        st.markdown("<div style='height:.55rem'></div>", unsafe_allow_html=True)
        channels = storage.list_channels()
        active_id = st.session_state.get("active_channel_id", "")
        active = next((channel for channel in channels if channel["id"] == active_id), None)
        if active:
            st.markdown(
                f'<div class="small-note">CHANNEL AKTIF</div><div style="padding:.45rem .05rem .8rem;color:#fff;font-weight:600">'
                f'<span class="status-dot"></span>{e(active["name"])}</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown('<div class="small-note" style="padding:.45rem .05rem .8rem">Belum ada channel aktif</div>', unsafe_allow_html=True)
        st.divider()
        with st.expander("Setup & koneksi", expanded=not bool(configured)):
            st.caption("OAuth Google dan Ollama Cloud disimpan aman di session. Untuk deployment, gunakan Streamlit secrets.")
            predefined_client = get_predefined_client()
            if st.button("Gunakan OAuth predefined · 1 klik", width="stretch", help="Memakai profil OAuth yang tertanam di app.py."):
                st.session_state["oauth_config_override"] = predefined_client
                st.session_state["oauth_redirect_uri_input"] = PREDEFINED_OAUTH_CONFIG["web"]["redirect_uris"][0]
                st.session_state["oauth_redirect_uri"] = PREDEFINED_OAUTH_CONFIG["web"]["redirect_uris"][0]
                st.rerun()
            st.caption("Profil OAuth predefined siap digunakan. Untuk keamanan, rotate client secret sebelum deployment publik.")
            uploaded_config = st.file_uploader(
                "Upload Google OAuth JSON",
                type=["json"],
                key="oauth_json_uploader",
                help="File credentials OAuth dari Google Cloud Console.",
            )
            if uploaded_config is not None:
                try:
                    parsed = json.loads(uploaded_config.getvalue().decode("utf-8"))
                    normalized = youtube_api.normalize_client_config(parsed)
                    if normalized:
                        st.session_state["oauth_config_override"] = normalized
                        configured = normalized
                        st.success("OAuth JSON siap digunakan.")
                    else:
                        st.error("Format OAuth JSON tidak valid.")
                except (UnicodeDecodeError, json.JSONDecodeError):
                    st.error("File JSON tidak dapat dibaca.")
            if st.session_state.get("oauth_config_override"):
                configured = st.session_state["oauth_config_override"]
            if not configured:
                st.text_input("Google client ID", key="oauth_client_id_input", placeholder="...apps.googleusercontent.com")
                st.text_input("Google client secret", key="oauth_client_secret_input", type="password")
                configured = youtube_api.manual_client_config(
                    st.session_state.get("oauth_client_id_input", ""),
                    st.session_state.get("oauth_client_secret_input", ""),
                )
            if "oauth_redirect_uri_input" not in st.session_state:
                st.session_state["oauth_redirect_uri_input"] = st.session_state.get("oauth_redirect_uri") or get_default_redirect_uri()
            redirect_uri = st.text_input(
                "Redirect URI terdaftar",
                key="oauth_redirect_uri_input",
                help="Harus sama persis dengan Authorized redirect URI di Google Cloud Console.",
            ).strip()
            st.session_state["oauth_redirect_uri"] = redirect_uri
            st.markdown("<div style='height:.45rem'></div>", unsafe_allow_html=True)
            st.text_input("Ollama Cloud API key", type="password", key="ollama_key_input", placeholder="Bearer key…")
            st.text_input("Ollama model", key="ollama_model_input", placeholder=ai_tools.DEFAULT_MODEL)
            st.text_input("Ollama base URL", key="ollama_url_input", placeholder=ai_tools.DEFAULT_OLLAMA_URL)
            st.selectbox("Timezone scheduler", TIMEZONES, key="timezone", index=TIMEZONES.index(st.session_state.get("timezone", "Asia/Jakarta")))
        with st.expander("Data & keamanan"):
            vault = storage.TokenVault(str(secret_value("TOKEN_ENCRYPTION_KEY", "") or "") or None)
            st.markdown(
                f'<div class="small-note">Database lokal: <code>data/youtube_studio.db</code><br>Token: terenkripsi ({e(vault.key_source)})</div>',
                unsafe_allow_html=True,
            )
            st.caption("Streamlit Cloud memiliki disk ephemeral. Untuk produksi multi-user, pindahkan storage ke Postgres/Supabase dan set TOKEN_ENCRYPTION_KEY.")
    return configured, redirect_uri


def save_connected_channel(tokens: dict[str, Any], client_config: dict[str, Any], success_label: str = "Channel terhubung") -> str:
    service = youtube_api.build_service(tokens, client_config)
    profile = youtube_api.channel_profile(service)
    vault = storage.TokenVault(str(secret_value("TOKEN_ENCRYPTION_KEY", "") or "") or None)
    channel_row_id = storage.upsert_channel(profile, tokens, vault)
    storage.touch_channel(channel_row_id)
    st.session_state["active_channel_id"] = channel_row_id
    st.session_state["services"].pop(channel_row_id, None)
    storage.log_event("success", success_label, {"channel": profile.get("name", "")})
    return channel_row_id


def handle_oauth_callback(client_config: dict[str, Any] | None, redirect_uri: str) -> None:
    try:
        query = st.query_params
        code = query.get("code")
        state = query.get("state")
    except Exception:
        return
    if not code or code in st.session_state.get("processed_oauth_codes", []):
        return
    if not client_config:
        st.error("Callback OAuth diterima, tetapi Google OAuth client belum dikonfigurasi.")
        return
    expected_state = st.session_state.get("oauth_state", "")
    if expected_state and state and state != expected_state:
        st.error("State OAuth tidak cocok. Silakan mulai koneksi ulang untuk keamanan.")
        return
    try:
        with st.spinner("Menghubungkan channel YouTube…"):
            tokens = youtube_api.exchange_code(client_config, redirect_uri, str(code), state or None)
            save_connected_channel(tokens, client_config, "Channel berhasil ditambahkan via OAuth")
        st.session_state["processed_oauth_codes"] = (st.session_state.get("processed_oauth_codes", []) + [code])[-10:]
        st.query_params.clear()
        st.success("Channel berhasil terhubung.")
        st.rerun()
    except Exception as exc:
        st.error(f"Gagal menyelesaikan OAuth: {exc}")


def service_for(channel_row_id: str, client_config: dict[str, Any] | None):
    if not client_config:
        raise RuntimeError("Google OAuth client belum dikonfigurasi.")
    services = st.session_state.setdefault("services", {})
    if channel_row_id not in services:
        vault = storage.TokenVault(str(secret_value("TOKEN_ENCRYPTION_KEY", "") or "") or None)
        token = storage.get_channel_token(channel_row_id, vault)
        services[channel_row_id] = youtube_api.build_service(token, client_config)
    storage.touch_channel(channel_row_id)
    return services[channel_row_id]


# -------------------------------------------------------------------------
# Upload worker
# -------------------------------------------------------------------------

def execute_job(job: dict[str, Any], client_config: dict[str, Any] | None, progress_bar=None) -> tuple[bool, str]:
    storage.update_job(job["id"], status="processing", error_message="")
    try:
        asset = storage.get_asset(job["asset_id"])
        if not asset or not Path(asset["path"]).exists():
            raise FileNotFoundError("File asset tidak ditemukan di storage lokal.")
        service = service_for(job["channel_id"], client_config)

        def on_progress(value: float) -> None:
            if progress_bar is not None:
                progress_bar.progress(max(0.0, min(1.0, value)))

        result = youtube_api.upload_video(
            service,
            asset["path"],
            job["title"],
            job["description"],
            tags=job.get("tags", []),
            category_id=job.get("category_id", "22"),
            privacy_status=job.get("privacy_status", "private"),
            made_for_kids=job.get("made_for_kids", False),
            progress_callback=on_progress,
        )
        storage.update_job(job["id"], status="published", youtube_video_id=result.get("video_id", ""), error_message="")
        storage.log_event("success", f"Video terbit: {job['title']}", {"job_id": job["id"], "video_id": result.get("video_id", "")})
        return True, result.get("url", "Video berhasil di-upload")
    except Exception as exc:
        message = str(exc)
        storage.update_job(job["id"], status="failed", error_message=message)
        storage.log_event("error", f"Upload gagal: {job.get('title', job['id'])}", {"job_id": job["id"], "error": message})
        return False, message


def process_due_jobs(client_config: dict[str, Any] | None, only_ids: list[str] | None = None) -> list[tuple[str, bool, str]]:
    due = storage.due_jobs()
    if only_ids is not None:
        due = [job for job in due if job["id"] in only_ids]
    results: list[tuple[str, bool, str]] = []
    for job in due:
        progress = st.progress(0, text=f"Menyiapkan {job['title'][:45]}…")
        ok, message = execute_job(job, client_config, progress)
        progress.empty()
        results.append((job["id"], ok, message))
    return results


# -------------------------------------------------------------------------
# Pages
# -------------------------------------------------------------------------

def render_dashboard(channels: list[dict[str, Any]], assets: list[dict[str, Any]], jobs: list[dict[str, Any]]) -> None:
    hero(
        "CONTROL CENTER",
        "Semua channel, satu ritme kerja.",
        "Rencanakan konten, siapkan metadata dengan AI, lalu kirim ke beberapa channel tanpa kehilangan konteks.",
    )
    queued = storage.count_jobs("queued")
    published = storage.count_jobs("published")
    failed = storage.count_jobs("failed")
    cols = st.columns(4)
    with cols[0]:
        metric_card("Connected channels", str(len(channels)), "OAuth tersimpan terenkripsi")
    with cols[1]:
        metric_card("Video library", str(len(assets)), "Asset siap diproses")
    with cols[2]:
        metric_card("Dalam antrean", str(queued), "Menunggu jadwal / publish")
    with cols[3]:
        metric_card("Published", str(published), f"{failed} job gagal perlu ditinjau" if failed else "Tidak ada kegagalan terbaru")

    st.markdown('<div class="section-title">Mulai cepat</div><div class="section-subtitle">Empat langkah dari file mentah sampai terbit.</div>', unsafe_allow_html=True)
    quick_cols = st.columns(4)
    quick = [
        ("01", "Hubungkan channel", "Tambah akun Google OAuth", "Channel manager"),
        ("02", "Upload video", "Bangun library asset", "Media studio"),
        ("03", "Poles SEO", "Judul, deskripsi, tag, keyword", "SEO lab"),
        ("04", "Atur jadwal", "Publish satu atau bulk", "Scheduler"),
    ]
    for col, (number, title, copy, destination) in zip(quick_cols, quick):
        with col:
            st.markdown(
                f'<div class="panel"><div class="pill pill-purple">{number}</div><div class="panel-title" style="margin-top:.7rem">{e(title)}</div><div class="panel-copy">{e(copy)}</div></div>',
                unsafe_allow_html=True,
            )
            if st.button("Buka", key=f"quick_{destination}", width="stretch"):
                st.session_state["nav"] = destination
                st.rerun()

    left, right = st.columns([1.45, 1])
    with left:
        page_header("Queue overview", "Jadwal terdekat dan status upload terakhir.")
        if jobs:
            rows = []
            for job in jobs[:8]:
                rows.append(
                    {
                        "Video": job.get("title", "")[:55],
                        "Channel": job.get("channel_name", "")[:24],
                        "Jadwal": pretty_datetime(job.get("scheduled_at"), st.session_state["timezone"]),
                        "Status": status_label(job.get("status", "")),
                    }
                )
            st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
        else:
            empty_state("Queue masih kosong", "Buat jadwal pertama dari Scheduler untuk mulai mengatur workflow.")
    with right:
        page_header("Channel pulse", "Snapshot channel yang tersambung.")
        if channels:
            for channel in channels[:4]:
                st.markdown(
                    f'<div class="channel-card"><div style="display:flex;gap:.7rem;align-items:center"><div class="channel-avatar">{e(initials(channel["name"]))}</div><div><div class="channel-name">{e(channel["name"])}</div><div class="channel-meta"><span class="status-dot"></span>{youtube_api.format_number(channel.get("subscribers", 0))} subscriber · {youtube_api.format_number(channel.get("video_count", 0))} video</div></div></div></div>',
                    unsafe_allow_html=True,
                )
        else:
            empty_state("Belum ada channel", "Tambahkan akun YouTube dari Channel manager.")

    page_header("Recent activity", "Log operasional dari OAuth, rendering, dan upload.")
    logs = storage.list_logs(8)
    if logs:
        for log in logs:
            level = log.get("level", "info")
            dot_class = "status-dot-danger" if level == "error" else "status-dot-warn" if level == "warning" else "status-dot"
            st.markdown(
                f'<div style="display:flex;justify-content:space-between;gap:1rem;border-bottom:1px solid var(--line);padding:.58rem 0"><div style="font-size:.8rem"><span class="status-dot {dot_class}"></span>{e(log.get("message", ""))}</div><div class="small-note">{e(pretty_datetime(log.get("created_at"), st.session_state["timezone"]))}</div></div>',
                unsafe_allow_html=True,
            )
    else:
        st.caption("Belum ada aktivitas. Sistem akan mencatat event penting di sini.")


def render_channel_manager(client_config: dict[str, Any] | None, redirect_uri: str, channels: list[dict[str, Any]]) -> None:
    hero(
        "CHANNEL MANAGER",
        "Akun terorganisir, siap bulk posting.",
        "Hubungkan beberapa channel dengan Google OAuth. Token disimpan terenkripsi dan tiap job akan memakai channel yang dipilih.",
    )
    left, right = st.columns([1.12, .88])
    with left:
        page_header("Tambah channel", "Gunakan OAuth redirect atau fallback authorization code.")
        if client_config:
            try:
                current_redirect = st.session_state.get("oauth_redirect_uri") or redirect_uri
                # Generate a fresh state on each render and keep the exact
                # value that is embedded in the link for callback validation.
                auth_url, state = youtube_api.authorization_url(client_config, current_redirect)
                st.session_state["oauth_state"] = state
                st.session_state["oauth_redirect_uri"] = current_redirect
                st.markdown('<div class="callout">Login aman via Google. Pastikan redirect URI di Google Cloud sama persis dengan yang tampil di Setup.</div>', unsafe_allow_html=True)
                st.link_button("Buka Google OAuth ↗", auth_url, width="stretch")
                st.caption(f"Redirect URI aktif: {current_redirect}")
            except Exception as exc:
                st.error(f"OAuth belum siap: {exc}")
        else:
            st.markdown('<div class="callout">Isi Google OAuth client ID dan secret di panel Setup sidebar, atau upload credentials JSON.</div>', unsafe_allow_html=True)
        with st.form("manual_oauth_form", clear_on_submit=False):
            st.markdown("**Fallback: paste authorization code**")
            code = st.text_input("Authorization code", type="password", placeholder="4/0A…", label_visibility="collapsed")
            submitted = st.form_submit_button("Hubungkan dengan code", width="stretch")
        if submitted:
            if not client_config:
                st.error("Google OAuth client belum dikonfigurasi.")
            elif not code.strip():
                st.warning("Authorization code masih kosong.")
            else:
                try:
                    with st.spinner("Memvalidasi akun YouTube…"):
                        tokens = youtube_api.exchange_code(client_config, redirect_uri, code)
                        save_connected_channel(tokens, client_config, "Channel berhasil ditambahkan via authorization code")
                    st.success("Channel berhasil terhubung.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Gagal menghubungkan channel: {exc}")
        with st.expander("Checklist Google Cloud Console"):
            st.markdown(
                "1. Enable **YouTube Data API v3**.  \n"
                "2. Buat OAuth Client ID tipe **Web application**.  \n"
                "3. Tambahkan URI di atas ke **Authorized redirect URIs**.  \n"
                "4. Jangan commit `client_secret` atau token ke Git."
            )
    with right:
        page_header("Security posture", "Hal yang perlu dipahami saat deploy di Streamlit Cloud.")
        st.markdown(
            '<div class="panel"><div class="panel-title">OAuth reference</div><div class="panel-copy">Flow callback dan manual code diadaptasi dari pola login pada repo referensi yang kamu berikan. Profil predefined tersedia untuk quick connect; rotate client secret sebelum deployment publik.</div><div style="margin-top:.7rem"><span class="pill">OAuth 2.0</span><span class="pill pill-purple">Encrypted token</span><span class="pill pill-muted">No stream key</span></div></div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="panel" style="margin-top:.7rem"><div class="panel-title">Bulk guardrail</div><div class="panel-copy">Job bulk dibuat sebagai antrean. Upload berjalan ketika kamu menekan Process due jobs; ini mencegah satu kesalahan metadata mem-publish ke semua channel tanpa review.</div></div>',
            unsafe_allow_html=True,
        )

    page_header("Daftar channel", f"{len(channels)} channel tersimpan · pilih channel aktif untuk analytics.")
    if not channels:
        empty_state("Belum ada channel tersambung", "Selesaikan OAuth di panel kiri untuk menambahkan channel pertama.")
        return
    for channel in channels:
        channel_id = channel["id"]
        is_active = st.session_state.get("active_channel_id") == channel_id
        row_cols = st.columns([.09, .42, .18, .16, .15])
        with row_cols[0]:
            st.markdown(f'<div class="channel-avatar">{e(initials(channel["name"]))}</div>', unsafe_allow_html=True)
        with row_cols[1]:
            st.markdown(
                f'<div class="channel-name">{e(channel["name"])}</div><div class="channel-meta"><span class="status-dot"></span>Connected · {e(channel.get("handle", ""))}</div>',
                unsafe_allow_html=True,
            )
        with row_cols[2]:
            st.markdown(f'<div class="small-note">SUBSCRIBER</div><div style="font-weight:700;color:#fff">{e(youtube_api.format_number(channel.get("subscribers", 0)))}</div>', unsafe_allow_html=True)
        with row_cols[3]:
            label = "Aktif" if is_active else "Pilih"
            if st.button(label, key=f"activate_{channel_id}", width="stretch", disabled=is_active):
                st.session_state["active_channel_id"] = channel_id
                st.rerun()
        with row_cols[4]:
            with st.popover("•••", width="stretch"):
                if st.button("Refresh profile", key=f"refresh_{channel_id}", width="stretch"):
                    try:
                        service = service_for(channel_id, client_config)
                        profile = youtube_api.channel_profile(service)
                        storage.update_channel_profile(channel_id, profile)
                        st.success("Profile diperbarui.")
                        st.rerun()
                    except Exception as exc:
                        st.error(str(exc))
                if st.button("Hapus channel", key=f"delete_{channel_id}", width="stretch"):
                    storage.delete_channel(channel_id)
                    st.session_state["services"].pop(channel_id, None)
                    if st.session_state.get("active_channel_id") == channel_id:
                        st.session_state["active_channel_id"] = ""
                    st.rerun()
        st.markdown("<hr style='margin:.25rem 0 .75rem'>", unsafe_allow_html=True)


def save_uploaded_files(uploaded_files: list[Any]) -> int:
    count = 0
    storage.ensure_directories()
    processed_keys = st.session_state.setdefault("processed_upload_keys", [])
    for uploaded in uploaded_files:
        unique_key = f"{uploaded.name}:{uploaded.size}"
        if unique_key in processed_keys:
            continue
        safe_name = Path(uploaded.name).name
        path = storage.UPLOAD_DIR / f"{uuid.uuid4().hex[:10]}_{safe_name}"
        path.write_bytes(uploaded.getbuffer())
        info = video_tools.probe_video(path)
        storage.add_asset(
            {
                "name": safe_name,
                "original_name": safe_name,
                "path": str(path),
                "size_bytes": uploaded.size,
                **info,
            }
        )
        processed_keys.append(unique_key)
        storage.log_event("success", f"Asset ditambahkan: {safe_name}", {"path": str(path)})
        count += 1
    st.session_state["processed_upload_keys"] = processed_keys[-100:]
    return count


def render_media_studio(assets: list[dict[str, Any]]) -> None:
    hero(
        "MEDIA STUDIO",
        "Satu sumber, dua format layar.",
        "Upload video, rapikan library, lalu render canvas 16:9 untuk long-form atau 9:16 untuk Shorts.",
    )
    left, right = st.columns([1.1, .9])
    with left:
        page_header("Tambah asset", "File disimpan di data/uploads pada instance ini.")
        uploaded_files = st.file_uploader(
            "Drop video di sini",
            type=["mp4", "mov", "mkv", "avi", "webm"],
            accept_multiple_files=True,
            key="media_uploader",
        )
        if uploaded_files and st.button("Simpan ke library", type="primary", width="stretch"):
            with st.spinner("Membaca metadata video…"):
                count = save_uploaded_files(uploaded_files)
            if count:
                st.success(f"{count} video masuk ke library.")
                st.rerun()
            else:
                st.info("File tersebut sudah ada di library.")
    with right:
        page_header("Format guidelines", "Preset YouTube yang aman untuk proses awal.")
        st.markdown(
            '<div class="panel"><div class="panel-title">16:9 · Long-form</div><div class="panel-copy">Canvas 1920 × 1080. Pilih Fit untuk menjaga seluruh frame, atau Crop untuk memenuhi canvas.</div><div style="margin-top:.6rem"><span class="pill pill-purple">1920×1080</span><span class="pill">H.264 + AAC</span></div></div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="panel" style="margin-top:.7rem"><div class="panel-title">9:16 · Shorts</div><div class="panel-copy">Canvas 1080 × 1920. Gunakan Crop to fill untuk frame vertikal yang memenuhi layar.</div><div style="margin-top:.6rem"><span class="pill pill-purple">1080×1920</span><span class="pill">≤ 60 detik disarankan</span></div></div>',
            unsafe_allow_html=True,
        )
        if not video_tools.ffmpeg_available():
            st.warning("FFmpeg belum terdeteksi di environment ini. Upload tetap bisa disimpan, tetapi render aktif setelah packages.txt dipasang.")

    page_header("Asset library", f"{len(assets)} video tersimpan.")
    if assets:
        rows = []
        for asset in assets:
            rows.append(
                {
                    "Asset": asset.get("name", "")[:50],
                    "Source": asset.get("source_ratio", "—"),
                    "Resolusi": f"{asset.get('width', 0)}×{asset.get('height', 0)}" if asset.get("width") else "—",
                    "Durasi": video_tools.format_duration(asset.get("duration_seconds", 0)),
                    "Ukuran": video_tools.format_bytes(asset.get("size_bytes", 0)),
                    "Dibuat": pretty_datetime(asset.get("created_at"), st.session_state["timezone"]),
                }
            )
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    else:
        empty_state("Library masih kosong", "Upload MP4, MOV, MKV, AVI, atau WEBM untuk mulai mengolah video.")
        return

    page_header("Aspect-ratio editor", "Render file baru tanpa menimpa original.")
    asset_ids = [asset["id"] for asset in assets]
    asset_map = {asset["id"]: asset for asset in assets}
    selected_id = st.selectbox("Pilih source video", asset_ids, format_func=lambda item: asset_map[item]["name"], key="editor_asset")
    editor_cols = st.columns([.7, .7, 1.1])
    with editor_cols[0]:
        target = st.radio("Target canvas", ["16:9", "9:16"], horizontal=True, key="editor_target")
    with editor_cols[1]:
        mode = st.selectbox("Mode frame", ["Fit + background", "Crop to fill"], key="editor_mode")
    with editor_cols[2]:
        background = st.color_picker("Warna background saat Fit", value="#0B1220", key="editor_background")
    if st.button("Render format baru", type="primary", width="stretch"):
        source = asset_map[selected_id]
        try:
            with st.spinner(f"Merender {target}… Proses bisa beberapa menit untuk video panjang."):
                output, info = video_tools.render_aspect_ratio(source["path"], target, mode, background)
                new_id = storage.add_asset(
                    {
                        "name": output.name,
                        "original_name": output.name,
                        "path": str(output),
                        "size_bytes": output.stat().st_size,
                        **info,
                    }
                )
                storage.log_event("success", f"Video dirender {target}: {output.name}", {"asset_id": new_id})
            st.success(f"Selesai: {output.name}")
            with open(output, "rb") as file_handle:
                st.download_button("Download hasil render", file_handle, file_name=output.name, mime="video/mp4")
        except Exception as exc:
            st.error(f"Render gagal: {exc}")


def metadata_state_defaults(generated: dict[str, Any] | None = None) -> None:
    generated = generated or {}
    if generated:
        st.session_state["meta_title"] = generated.get("title", "")
        st.session_state["meta_description"] = generated.get("description", "")
        st.session_state["meta_tags"] = ", ".join(generated.get("tags", []))
        st.session_state["meta_keywords"] = ", ".join(generated.get("keywords", []))
        st.session_state["meta_hashtags"] = ", ".join(generated.get("hashtags", []))


def render_seo_lab(client_config: dict[str, Any] | None, channels: list[dict[str, Any]]) -> None:
    hero(
        "SEO LAB",
        "Metadata yang membantu video ditemukan.",
        "Gunakan Ollama Cloud untuk menyusun title, description, tag, dan keyword. Semua output tetap bisa kamu review sebelum masuk antrean.",
    )
    api_key, model, base_url = configured_ollama()
    if api_key:
        st.markdown('<div class="callout">Ollama Cloud aktif · output akan diberi label sebagai draft AI dan tetap perlu review manusia.</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="callout">Mode fallback aktif. Isi API key Ollama Cloud di sidebar untuk generasi dan analisis yang lebih kontekstual.</div>', unsafe_allow_html=True)

    page_header("Metadata generator", "Brief singkat → paket metadata siap dipakai.")
    brief_cols = st.columns([1.2, .8, .8])
    with brief_cols[0]:
        topic = st.text_input("Topik video", placeholder="contoh: cara membuat thumbnail YouTube", key="seo_topic")
    with brief_cols[1]:
        niche = st.text_input("Niche", placeholder="creator economy", key="seo_niche")
    with brief_cols[2]:
        language = st.selectbox("Bahasa", ["Indonesia", "English", "Malay"], key="seo_language")
    detail_cols = st.columns([.8, .8, 1.2])
    with detail_cols[0]:
        tone = st.selectbox("Tone", ["Edukatif dan hangat", "Ringkas dan tajam", "Storytelling", "Profesional"], key="seo_tone")
    with detail_cols[1]:
        audience = st.text_input("Target penonton", value="Penonton umum", key="seo_audience")
    with detail_cols[2]:
        st.caption(f"Model: `{model}` · Endpoint: `{base_url}`")
    if st.button("Generate metadata", type="primary", width="stretch"):
        if not topic.strip():
            st.warning("Tulis topik video terlebih dahulu.")
        else:
            with st.spinner("Menyusun metadata SEO…"):
                generated = ai_tools.generate_metadata(topic, niche, language, tone, audience, api_key, model, base_url)
            st.session_state["generated_metadata"] = generated
            metadata_state_defaults(generated)
            st.success(f"Draft siap · source: {generated.get('source', 'unknown')}")

    if st.session_state.get("generated_metadata"):
        generated = st.session_state["generated_metadata"]
        display_cols = st.columns([1.02, .98])
        with display_cols[0]:
            page_header("Review & edit", "Field di bawah ini yang akan dipakai Scheduler.")
            st.text_input("Title", max_chars=100, key="meta_title")
            st.text_area("Description", height=220, max_chars=5000, key="meta_description")
            st.text_input("Tags · pisahkan dengan koma", key="meta_tags")
        with display_cols[1]:
            page_header("Search signals", "Keyword utama dan rekomendasi yang menyertai draft.")
            st.text_area("Keywords", height=120, key="meta_keywords")
            st.text_input("Hashtags", key="meta_hashtags")
            st.markdown(
                f'<div class="panel"><div class="panel-title">Catatan SEO</div><div class="panel-copy">{e(generated.get("seo_notes", "Review draft sebelum publish."))}</div><div style="margin-top:.65rem"><span class="pill pill-purple">{e(generated.get("source", "draft"))}</span><span class="pill">Title ≤ 100 karakter</span></div></div>',
                unsafe_allow_html=True,
            )
        if st.button("Gunakan draft di Scheduler →", width="stretch"):
            st.session_state["nav"] = "Scheduler"
            st.rerun()

    page_header("Keyword intelligence", "Padukan SERP sample YouTube dengan analisis intent.")
    keyword_cols = st.columns([1, .72, 1.1])
    with keyword_cols[0]:
        seed = st.text_input("Seed keyword", placeholder="contoh: editing video hp", key="keyword_seed")
    with keyword_cols[1]:
        search_channel_id = st.selectbox(
            "API channel (auth)",
            [""] + [channel["id"] for channel in channels],
            format_func=lambda item: "Tidak pakai channel" if item == "" else next((c["name"] for c in channels if c["id"] == item), item),
            key="keyword_channel",
        )
    with keyword_cols[2]:
        st.caption("SERP memakai quota YouTube Data API jika channel OAuth dipilih. Tanpa channel, AI tetap bisa membuat cluster ide.")
    if st.button("Analisis keyword", type="primary", width="stretch"):
        if not seed.strip():
            st.warning("Masukkan seed keyword.")
        else:
            serp = []
            serp_meta: dict[str, Any] = {}
            if search_channel_id:
                try:
                    service = service_for(search_channel_id, client_config)
                    serp_meta = youtube_api.keyword_search(service, seed, limit=10)
                    serp = serp_meta.get("results", [])
                except Exception as exc:
                    st.warning(f"SERP YouTube tidak tersedia: {exc}")
            with st.spinner("Mengelompokkan keyword dan intent…"):
                result = ai_tools.analyze_keywords(seed, niche if "niche" in locals() else "", language if "language" in locals() else "Indonesia", serp, api_key, model, base_url)
            result["serp_meta"] = serp_meta
            st.session_state["keyword_result"] = result
            storage.save_keyword_analysis(seed, niche if "niche" in locals() else "", language if "language" in locals() else "Indonesia", result)

    result = st.session_state.get("keyword_result")
    if result:
        summary_cols = st.columns(3)
        with summary_cols[0]:
            metric_card("Keyword ditemukan", str(len(result.get("keywords", []))), "Cluster dari seed keyword")
        with summary_cols[1]:
            serp_meta = result.get("serp_meta", {})
            metric_card("Estimasi hasil SERP", youtube_api.format_number(serp_meta.get("total_results", 0)), "Sample YouTube jika tersedia")
        with summary_cols[2]:
            metric_card("Source", str(result.get("source", "fallback")), "AI / heuristic fallback")
        st.markdown(f'<div class="callout">{e(result.get("summary", ""))}</div>', unsafe_allow_html=True)
        rows = []
        for item in result.get("keywords", []):
            rows.append(
                {
                    "Keyword": item.get("keyword", ""),
                    "Intent": item.get("intent", ""),
                    "Opportunity": int(item.get("opportunity", 0)),
                    "Competition": item.get("competition", ""),
                    "Reason": item.get("reason", "")[:100],
                }
            )
        if rows:
            st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
        angles = result.get("content_angles", [])
        if angles:
            st.markdown("**Content angles yang bisa diuji**")
            st.markdown("".join(f'<span class="pill pill-purple">{e(angle)}</span>' for angle in angles), unsafe_allow_html=True)
        if result.get("watchouts"):
            st.warning(" · ".join(result["watchouts"]))


def render_scheduler(client_config: dict[str, Any] | None, channels: list[dict[str, Any]], assets: list[dict[str, Any]]) -> None:
    hero(
        "SCHEDULER",
        "Publish satu kali atau ke banyak channel.",
        "Buat job per channel dengan metadata yang sama, pilih jadwal, lalu proses antrean saat waktunya tiba.",
    )
    jobs = storage.list_jobs(100)
    queued = len([job for job in jobs if job.get("status") == "queued"])
    processing = len([job for job in jobs if job.get("status") == "processing"])
    failed = len([job for job in jobs if job.get("status") == "failed"])
    metric_cols = st.columns(4)
    for col, label, value, helper in [
        (metric_cols[0], "Total jobs", len(jobs), "Semua channel"),
        (metric_cols[1], "Queued", queued, "Siap menunggu worker"),
        (metric_cols[2], "Processing", processing, "Sedang di-upload"),
        (metric_cols[3], "Failed", failed, "Perlu retry / review"),
    ]:
        with col:
            metric_card(label, str(value), helper)

    if not channels or not assets:
        left_message = "Hubungkan channel" if not channels else "Tambahkan asset video"
        empty_state("Scheduler belum siap", f"{left_message} terlebih dahulu untuk membuat job.")
    else:
        asset_map = {asset["id"]: asset for asset in assets}
        channel_map = {channel["id"]: channel for channel in channels}
        draft = st.session_state.get("generated_metadata", {})
        default_title = st.session_state.get("meta_title", draft.get("title", ""))
        default_description = st.session_state.get("meta_description", draft.get("description", ""))
        default_tags = st.session_state.get("meta_tags", ", ".join(draft.get("tags", [])))
        default_keywords = st.session_state.get("meta_keywords", ", ".join(draft.get("keywords", [])))
        with st.form("schedule_job_form", clear_on_submit=False):
            page_header("Buat job baru", "Satu baris untuk setiap channel yang kamu centang.")
            top_cols = st.columns([1.1, 1.1])
            with top_cols[0]:
                selected_asset = st.selectbox("Video source", list(asset_map), format_func=lambda item: asset_map[item]["name"], key="schedule_asset")
            with top_cols[1]:
                selected_channels = st.multiselect(
                    "Target channel · bulk",
                    list(channel_map),
                    format_func=lambda item: channel_map[item]["name"],
                    default=[st.session_state.get("active_channel_id")] if st.session_state.get("active_channel_id") in channel_map else [],
                    key="schedule_channels",
                )
            meta_cols = st.columns([1.05, .95])
            with meta_cols[0]:
                job_title = st.text_input("Title", value=default_title, max_chars=100, key="schedule_title")
                job_description = st.text_area("Description", value=default_description, height=150, max_chars=5000, key="schedule_description")
                job_tags = st.text_input("Tags · koma", value=default_tags, key="schedule_tags")
                job_keywords = st.text_input("Internal keywords · koma", value=default_keywords, key="schedule_keywords")
            with meta_cols[1]:
                category = st.selectbox("Kategori", list(CATEGORIES), format_func=lambda item: CATEGORIES[item], index=0, key="schedule_category")
                privacy = st.selectbox("Visibility", ["private", "unlisted", "public"], index=0, key="schedule_privacy")
                made_for_kids = st.checkbox("Made for kids", key="schedule_kids")
                execution = st.radio("Eksekusi", ["Masukkan antrean", "Upload sekarang"], key="schedule_execution")
                schedule_mode = st.radio("Waktu publish", ["Sekarang / saat worker jalan", "Jadwalkan"], key="schedule_mode")
                selected_date = st.date_input("Tanggal", value=date.today(), disabled=schedule_mode != "Jadwalkan", key="schedule_date")
                selected_time = st.time_input("Jam", value=time(9, 0), disabled=schedule_mode != "Jadwalkan", key="schedule_time")
            submitted = st.form_submit_button("Buat job", type="primary", width="stretch")
        if submitted:
            if not selected_channels:
                st.warning("Pilih minimal satu channel.")
            elif not job_title.strip():
                st.warning("Title wajib diisi.")
            else:
                scheduled_at = None
                if schedule_mode == "Jadwalkan" and execution != "Upload sekarang":
                    local_dt = datetime.combine(selected_date, selected_time).replace(tzinfo=ZoneInfo(st.session_state["timezone"]))
                    scheduled_at = local_dt.astimezone(timezone.utc).replace(microsecond=0).isoformat()
                created_ids = []
                for target_channel in selected_channels:
                    created_ids.append(
                        storage.create_job(
                            {
                                "asset_id": selected_asset,
                                "channel_id": target_channel,
                                "title": job_title.strip(),
                                "description": job_description,
                                "tags": csv_terms(job_tags),
                                "keywords": csv_terms(job_keywords),
                                "category_id": category,
                                "privacy_status": privacy,
                                "made_for_kids": made_for_kids,
                                "scheduled_at": scheduled_at,
                            }
                        )
                    )
                st.session_state["last_created_jobs"] = created_ids
                storage.log_event("success", f"{len(created_ids)} job dibuat", {"job_ids": created_ids})
                st.success(f"{len(created_ids)} job masuk ke antrean.")
                if execution == "Upload sekarang":
                    with st.spinner(f"Memproses {len(created_ids)} upload…"):
                        results = process_due_jobs(client_config, created_ids)
                    for _, ok, message in results:
                        if ok:
                            st.success(message)
                        else:
                            st.error(message)
                    jobs = storage.list_jobs(100)

    st.markdown("<div style='height:.6rem'></div>", unsafe_allow_html=True)
    action_cols = st.columns([1, 1, 2])
    with action_cols[0]:
        if st.button("Process due jobs", type="primary", width="stretch", disabled=not bool(client_config)):
            with st.spinner("Memproses job yang sudah jatuh tempo…"):
                results = process_due_jobs(client_config)
            if not results:
                st.info("Tidak ada job due saat ini.")
            for _, ok, message in results:
                (st.success if ok else st.error)(message)
            st.rerun()
    with action_cols[1]:
        if st.button("Refresh queue", width="stretch"):
            st.rerun()
    with action_cols[2]:
        st.markdown('<div class="small-note" style="padding:.55rem 0">Scheduler Streamlit bersifat request-driven: untuk otomasi 24/7, ping aplikasi dengan cron/monitor eksternal atau pindahkan worker ke background service.</div>', unsafe_allow_html=True)

    page_header("Job queue", "Review status, jadwal, dan error sebelum retry.")
    if not jobs:
        empty_state("Belum ada job", "Buat job dari form di atas.")
        return
    rows = []
    for job in jobs:
        rows.append(
            {
                "ID": job.get("id", "").replace("job_", "")[:8],
                "Video": job.get("title", "")[:45],
                "Channel": job.get("channel_name", "")[:24],
                "Jadwal": pretty_datetime(job.get("scheduled_at"), st.session_state["timezone"]),
                "Status": status_label(job.get("status", "")),
                "Error": job.get("error_message", "")[:60],
            }
        )
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    for job in jobs[:20]:
        if job.get("status") == "failed":
            cols = st.columns([.75, .15, .1])
            with cols[0]:
                st.markdown(f'<div class="small-note"><b style="color:#fff">{e(job.get("title", ""))}</b> · {e(job.get("error_message", "")[:180])}</div>', unsafe_allow_html=True)
            with cols[1]:
                if st.button("Retry", key=f"retry_{job['id']}", width="stretch"):
                    storage.update_job(job["id"], status="queued", error_message="")
                    st.rerun()
            with cols[2]:
                if st.button("Hapus", key=f"remove_{job['id']}", width="stretch"):
                    storage.delete_job(job["id"])
                    st.rerun()


def render_analytics(client_config: dict[str, Any] | None, channels: list[dict[str, Any]]) -> None:
    hero(
        "ANALYTICS",
        "Baca sinyal, bukan sekadar angka.",
        "Pantau snapshot channel, video terbaru, dan riwayat riset keyword untuk menentukan eksperimen berikutnya.",
    )
    total_views = sum(int(channel.get("total_views") or 0) for channel in channels)
    total_subscribers = sum(int(channel.get("subscribers") or 0) for channel in channels)
    metric_cols = st.columns(4)
    for col, label, value, helper in [
        (metric_cols[0], "Channels", len(channels), "Channel tersambung"),
        (metric_cols[1], "Subscribers", youtube_api.format_number(total_subscribers), "Snapshot terakhir"),
        (metric_cols[2], "Total views", youtube_api.format_number(total_views), "Gabungan channel"),
        (metric_cols[3], "Keyword reports", len(storage.list_keyword_analyses(100)), "Laporan tersimpan"),
    ]:
        with col:
            metric_card(label, str(value), helper)

    if channels:
        channel_map = {channel["id"]: channel for channel in channels}
        selected_id = st.selectbox("Channel untuk detail", list(channel_map), format_func=lambda item: channel_map[item]["name"], key="analytics_channel")
        selected = channel_map[selected_id]
        col_left, col_right = st.columns([1.25, .75])
        with col_left:
            page_header("Latest uploads", "Diambil dari YouTube Data API saat tombol refresh dipakai.")
            if st.button("Refresh data channel", width="stretch"):
                try:
                    service = service_for(selected_id, client_config)
                    profile = youtube_api.channel_profile(service)
                    storage.update_channel_profile(selected_id, profile)
                    videos = youtube_api.channel_videos(service, selected["channel_id"], 12)
                    st.session_state["analytics_videos"] = videos
                    st.success("Data channel diperbarui.")
                except Exception as exc:
                    st.error(f"Tidak dapat mengambil data: {exc}")
            videos = st.session_state.get("analytics_videos", [])
            if videos:
                frame = pd.DataFrame(
                    [
                        {
                            "Video": video["title"][:60],
                            "Views": video["views"],
                            "Likes": video["likes"],
                            "Comments": video["comments"],
                            "Published": pretty_datetime(video["published_at"], st.session_state["timezone"]),
                        }
                        for video in videos
                    ]
                )
                st.dataframe(frame, hide_index=True, width="stretch")
                st.bar_chart(frame.set_index("Video")["Views"], height=260)
            else:
                empty_state("Belum ada snapshot", "Klik Refresh data channel untuk mengambil upload terbaru.")
        with col_right:
            page_header("Channel health", "Indikator sederhana untuk membaca momentum.")
            st.markdown(
                f'<div class="panel"><div class="panel-title">{e(selected["name"])}</div><div class="panel-copy">{e(selected.get("description", "")[:180] or "Tidak ada deskripsi channel.")}</div><div style="margin-top:1rem"><div class="small-note">SUBSCRIBERS</div><div style="font-family:Space Grotesk;font-size:1.65rem;font-weight:700;color:#fff">{e(youtube_api.format_number(selected.get("subscribers", 0)))}</div><div class="small-note" style="margin-top:.65rem">VIDEO COUNT</div><div style="font-family:Space Grotesk;font-size:1.35rem;font-weight:700;color:#fff">{e(youtube_api.format_number(selected.get("video_count", 0)))}</div></div></div>',
                unsafe_allow_html=True,
            )
    else:
        empty_state("Hubungkan channel untuk analytics", "Keyword reports tetap dapat dilihat setelah kamu menjalankan analisis di SEO Lab.")

    page_header("Keyword report history", "Riwayat analisis tersimpan lokal untuk perbandingan antar eksperimen.")
    history = storage.list_keyword_analyses(20)
    if history:
        rows = []
        for item in history:
            payload = item.get("payload", {})
            rows.append(
                {
                    "Seed": item.get("seed", ""),
                    "Niche": item.get("niche", ""),
                    "Keywords": len(payload.get("keywords", [])),
                    "Source": payload.get("source", ""),
                    "Dibuat": pretty_datetime(item.get("created_at"), st.session_state["timezone"]),
                }
            )
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    else:
        st.caption("Belum ada laporan keyword. Jalankan analisis dari SEO Lab.")


# -------------------------------------------------------------------------
# App entrypoint
# -------------------------------------------------------------------------

def main() -> None:
    storage.init_db()
    init_state()
    client_config, redirect_uri = render_sidebar()
    handle_oauth_callback(client_config, redirect_uri)
    channels = storage.list_channels()
    assets = storage.list_assets()
    jobs = storage.list_jobs(100)

    if st.session_state.get("nav") == "Dashboard":
        render_dashboard(channels, assets, jobs)
    elif st.session_state.get("nav") == "Channel manager":
        render_channel_manager(client_config, redirect_uri, channels)
    elif st.session_state.get("nav") == "Media studio":
        render_media_studio(assets)
    elif st.session_state.get("nav") == "SEO lab":
        render_seo_lab(client_config, channels)
    elif st.session_state.get("nav") == "Scheduler":
        render_scheduler(client_config, channels, assets)
    elif st.session_state.get("nav") == "Analytics":
        render_analytics(client_config, channels)


if __name__ == "__main__":
    main()
