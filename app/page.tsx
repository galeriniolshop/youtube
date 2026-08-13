"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

type NoteRecord = {
  text: string;
  updatedAt: string;
  bytes: number;
};

const REFRESH_MS = 20_000;
const SAVE_MS = 400;
const LOCAL_KEY = "catatan-personal:draft";

function formatStamp(value: string | Date) {
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
}

export default function Page() {
  const [text, setText] = useState("");
  const [lastSaved, setLastSaved] = useState<Date>(new Date());
  const [bytes, setBytes] = useState(0);
  const [status, setStatus] = useState("Menyiapkan catatan…");
  const [ready, setReady] = useState(false);
  const dirtyRef = useRef(false);
  const textRef = useRef("");
  const timerRef = useRef<number | null>(null);

  const persistLocal = (value: string) => {
    try {
      localStorage.setItem(LOCAL_KEY, value);
    } catch {
      /* ignore quota */
    }
  };

  const saveRemote = useCallback(async (value: string) => {
    const res = await fetch("/api/notes", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: value }),
    });
    if (!res.ok) throw new Error("Gagal menyimpan");
    const note = (await res.json()) as NoteRecord;
    setBytes(note.bytes);
    setLastSaved(note.updatedAt ? new Date(note.updatedAt) : new Date());
    setStatus("Tersimpan");
    dirtyRef.current = false;
    return note;
  }, []);

  const loadRemote = useCallback(async () => {
    const res = await fetch("/api/notes", { cache: "no-store" });
    if (!res.ok) throw new Error("Gagal memuat");
    return (await res.json()) as NoteRecord;
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const localDraft = (() => {
        try {
          return localStorage.getItem(LOCAL_KEY) ?? "";
        } catch {
          return "";
        }
      })();
      try {
        const remote = await loadRemote();
        if (cancelled) return;
        const next = remote.text || localDraft;
        setText(next);
        textRef.current = next;
        setBytes(remote.bytes || new Blob([next]).size);
        setLastSaved(remote.updatedAt ? new Date(remote.updatedAt) : new Date());
        if (!remote.text && localDraft) {
          await saveRemote(localDraft);
        }
        setStatus("Siap");
      } catch {
        if (cancelled) return;
        setText(localDraft);
        textRef.current = localDraft;
        setBytes(new Blob([localDraft]).size);
        setStatus("Mode lokal");
      } finally {
        if (!cancelled) setReady(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [loadRemote, saveRemote]);

  useEffect(() => {
    const id = window.setInterval(async () => {
      if (dirtyRef.current) return;
      try {
        const remote = await loadRemote();
        if (dirtyRef.current) return;
        if (remote.text !== textRef.current) {
          setText(remote.text);
          textRef.current = remote.text;
          persistLocal(remote.text);
          setBytes(remote.bytes);
          setLastSaved(remote.updatedAt ? new Date(remote.updatedAt) : new Date());
          setStatus("Diperbarui dari server");
        }
      } catch {
        /* keep local copy */
      }
    }, REFRESH_MS);
    return () => window.clearInterval(id);
  }, [loadRemote]);

  const scheduleSave = (value: string) => {
    if (timerRef.current) window.clearTimeout(timerRef.current);
    timerRef.current = window.setTimeout(async () => {
      try {
        await saveRemote(value);
      } catch {
        setStatus("Tersimpan di perangkat");
        setLastSaved(new Date());
        setBytes(new Blob([value]).size);
      }
    }, SAVE_MS);
  };

  const onChange = (value: string) => {
    dirtyRef.current = true;
    textRef.current = value;
    setText(value);
    persistLocal(value);
    setStatus("Menyimpan…");
    scheduleSave(value);
  };

  const clearNotes = async () => {
    if (!window.confirm("Bersihkan seluruh catatan?")) return;
    onChange("");
    try {
      await saveRemote("");
    } catch {
      setStatus("Dikosongkan di perangkat");
    }
  };

  const downloadNotes = () => {
    const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "notes.txt";
    link.click();
    URL.revokeObjectURL(url);
  };

  const copyNotes = async () => {
    await navigator.clipboard.writeText(text);
    setStatus("Disalin");
  };

  const words = useMemo(() => (text.trim() ? text.trim().split(/\s+/).length : 0), [text]);

  return (
    <main className="app">
      <div className="brand">
        <div className="brand-mark" aria-hidden>
          📝
        </div>
        <div>
          <h1>Catatan Personal</h1>
          <p>Ketik, tersimpan otomatis, dan disinkronkan setiap 20 detik.</p>
        </div>
      </div>

      <section className="sheet">
        <textarea
          className="editor"
          value={text}
          disabled={!ready}
          placeholder="Ketik catatan Anda di sini:"
          onChange={(event) => onChange(event.target.value)}
          spellCheck={false}
        />
        <div className="status">
          <span>
            Status: <b>{status}</b>
          </span>
          <span>
            {words} kata · {text.length} karakter
          </span>
        </div>
      </section>

      <div className="info">Terakhir disimpan: {formatStamp(lastSaved)}</div>

      <div className="toolbar">
        <button type="button" onClick={() => scheduleSave(text)}>
          Simpan sekarang
        </button>
        <button type="button" onClick={copyNotes} disabled={!text}>
          Salin
        </button>
        <button type="button" onClick={downloadNotes} disabled={!text}>
          Unduh notes.txt
        </button>
        <button type="button" className="danger" onClick={clearNotes} disabled={!text}>
          Bersihkan
        </button>
      </div>

      <hr className="rule" />
      <div className="foot">
        <span>📝 Catatan Anda disimpan secara permanen dan akan diperbarui setiap 20 detik</span>
        <span>Ukuran file: {bytes} bytes</span>
      </div>
    </main>
  );
}
