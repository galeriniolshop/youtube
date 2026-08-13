# Catatan Personal

Klon Vercel dari [jossbanget.streamlit.app](https://jossbanget.streamlit.app/) — notepad sederhana yang menyimpan otomatis.

Aplikasi Streamlit aslinya hanya punya satu area teks, timestamp *terakhir disimpan*, ukuran file, dan refresh tiap 20 detik. Versi ini meniru alur itu, lalu dipasang sebagai Next.js agar bisa di-deploy ke Vercel.

## Yang ditiru

- Halaman centered, fokus ke textarea besar
- Autosave saat mengetik
- `Terakhir disimpan: YYYY-MM-DD HH:MM:SS`
- Sinkron ulang setiap 20 detik
- Ukuran file dalam bytes
- Footer: catatan disimpan permanen dan diperbarui tiap 20 detik

Tambahan kecil agar nyaman di web: salin, unduh `notes.txt`, bersihkan, dan cadangan `localStorage` jika server sempat kosong.

## Jalankan lokal

```bash
npm install
npm run dev
```

Buka `http://localhost:3000`.

## Deploy ke Vercel

1. Push repository ini ke GitHub.
2. Import project di [vercel.com/new](https://vercel.com/new).
3. Framework terdeteksi sebagai **Next.js**. Biarkan build command default.
4. Deploy. URL Vercel langsung bisa dipakai.

### Agar catatan benar-benar permanen di Vercel

Filesystem Vercel bersifat ephemeral. Tanpa store eksternal, catatan bisa hilang saat instance serverless berganti.

Tambahkan Upstash Redis (gratis) di Environment Variables:

```bash
UPSTASH_REDIS_REST_URL=...
UPSTASH_REDIS_REST_TOKEN=...
```

Vercel KV juga didukung lewat `KV_REST_API_URL` dan `KV_REST_API_TOKEN`.

Tanpa itu, app tetap jalan: ada cadangan di browser (`localStorage`) plus file sementara di server.

## API

- `GET /api/notes` — baca catatan bersama
- `PUT /api/notes` — `{ "text": "..." }` simpan catatan

## Orbit Studio (Streamlit, tetap di repo)

File Python `app.py`, `storage.py`, `youtube_api.py`, `ai_tools.py`, dan `video_tools.py` adalah konsol YouTube Streamlit yang sudah ada. Itu tidak dipakai Vercel. Untuk menjalankannya:

```bash
pip install -r requirements.txt
streamlit run app.py
```
