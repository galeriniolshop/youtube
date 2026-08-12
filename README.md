# Orbit Studio · YouTube operations console

Orbit Studio adalah aplikasi Streamlit untuk mengatur beberapa channel YouTube dari satu workspace: channel manager, library video, render 16:9/9:16, metadata SEO dengan Ollama Cloud, keyword intelligence, bulk queue, dan scheduler.

> **Status:** fondasi production-minded untuk deployment Streamlit Cloud. YouTube OAuth dan upload nyata aktif setelah kredensial Google dikonfigurasi. Tanpa kredensial, UI dan mode fallback SEO tetap dapat dicoba.

## Fitur

- **Channel manager** — tambah beberapa channel melalui Google OAuth 2.0 atau fallback authorization code. Token OAuth dienkripsi dengan Fernet.
- **Media studio** — upload multi-file, inspeksi metadata via FFmpeg, render:
  - 16:9 — 1920×1080 untuk long-form
  - 9:16 — 1080×1920 untuk Shorts
  - mode `Fit + background` atau `Crop to fill`
- **SEO lab** — buat title, description, tags, hashtags, dan keyword dengan Ollama Cloud. Ada fallback heuristic agar app tetap bisa dipreview tanpa key.
- **Keyword intelligence** — keyword cluster, search intent, opportunity score, dan optional sample SERP YouTube Data API. Volume tidak dikarang; hasil SERP ditandai sebagai estimasi sample.
- **Scheduler & bulk posting** — satu video dapat dibuat menjadi job untuk banyak channel. Privacy, kategori, made-for-kids, metadata, dan waktu bisa diatur per batch.
- **Analytics** — snapshot subscriber/view/video, recent uploads, chart views, serta histori laporan keyword.
- **Cloud-aware** — worker scheduler bersifat request-driven karena Streamlit Cloud dapat menidurkan app. Tombol `Process due jobs` memproses job jatuh tempo; otomasi 24/7 membutuhkan cron/monitor eksternal atau worker background terpisah.

## Jalankan lokal

```bash
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
# Ubuntu/Debian: sudo apt-get install ffmpeg
streamlit run app.py
```

Streamlit Cloud memakai `packages.txt` untuk memasang FFmpeg.

## Konfigurasi Google OAuth

1. Buka Google Cloud Console dan aktifkan **YouTube Data API v3**.
2. Buat **OAuth Client ID → Web application**.
3. Tambahkan URL aplikasi sebagai **Authorized redirect URI**. Nilai default app ditampilkan di sidebar; masukkan URL yang sama persis, tanpa path tambahan jika tidak digunakan.
4. Di sidebar Orbit Studio, upload file OAuth JSON atau isi client ID dan secret.
5. Untuk profil quick-connect bawaan, tambahkan `PREDEFINED_YOUTUBE_CLIENT_SECRET` ke Streamlit Cloud Secrets lalu tekan **Gunakan OAuth predefined · 1 klik**. Client ID dan redirect URI sudah disiapkan di `app.py`, sedangkan secret tidak pernah disimpan di repository.
6. Buka **Channel manager → Buka Google OAuth**. Setelah consent, callback akan menambahkan channel ke daftar.
7. Untuk deployment, pakai Streamlit secrets. Template tersedia di `.streamlit/secrets.toml.example`.

Pola callback dan manual code exchange dibuat kompatibel dengan pola login pada repo referensi:
<https://github.com/missquental/serverliveupdate1>

Perbedaannya: secret tidak di-hardcode, scope dibatasi pada upload/read-only YouTube, dan token disimpan terenkripsi.

## Ollama Cloud

Tambahkan ke Streamlit Cloud Secrets:

```toml
OLLAMA_API_KEY = "..."
OLLAMA_MODEL = "gpt-oss:20b"
OLLAMA_BASE_URL = "https://ollama.com/api"
```

Atau isi dari panel **Setup & koneksi**. Endpoint default memakai `POST https://ollama.com/api/chat` dengan header `Authorization: Bearer ...` dan respons JSON. Model dapat diganti dari sidebar sesuai model yang tersedia di akun Ollama.

## Token encryption

Buat key Fernet satu kali:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Simpan sebagai `TOKEN_ENCRYPTION_KEY` di Streamlit secrets. Saat lokal, app membuat key di `data/.token_key`; direktori `data/` di-ignore Git. Tanpa secret di Cloud, token dapat hilang ketika instance restart.

## Deploy ke Streamlit Cloud

1. Push repository ini ke GitHub.
2. Buat app baru, pilih file `app.py` sebagai main file.
3. `requirements.txt` dan `packages.txt` otomatis dipasang.
4. Tambahkan secrets dari template.
5. Daftarkan URL app di Google OAuth.
6. Setelah deploy, hubungkan channel, upload asset, buat metadata, lalu buat job.

### Catatan storage

SQLite dan file video berada di `data/` dan bersifat lokal/ephemeral di Streamlit Cloud. Untuk penggunaan multi-user atau volume besar, ganti repository `storage.py` dengan Postgres/Supabase dan object storage (S3/R2/GCS). Jangan menyimpan video besar permanen di filesystem Streamlit.

### Catatan scheduler

Streamlit bukan worker selalu hidup. `Process due jobs` sengaja eksplisit agar bulk publish tidak terjadi tanpa kontrol. Untuk scheduler otomatis, panggil endpoint/app dengan cron agar instance bangun lalu tambahkan worker eksternal yang mengeksekusi queue, atau pindahkan `execute_job` ke service background.

## Struktur utama

```text
app.py          # UI Streamlit, navigation, OAuth callback, queue worker
storage.py      # SQLite repository + Fernet token vault
youtube_api.py  # Google OAuth, channel, keyword SERP, resumable upload
ai_tools.py     # Ollama Cloud + fallback metadata/keyword analysis
video_tools.py  # ffprobe, FFmpeg aspect-ratio render
```
