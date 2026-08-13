import { promises as fs } from "fs";
import path from "path";

export type NoteRecord = {
  text: string;
  updatedAt: string;
  bytes: number;
};

const EMPTY: NoteRecord = { text: "", updatedAt: "", bytes: 0 };

function encode(text: string, updatedAt = new Date().toISOString()): NoteRecord {
  return {
    text,
    updatedAt,
    bytes: Buffer.byteLength(text, "utf8"),
  };
}

function localPath() {
  if (process.env.VERCEL) {
    return path.join("/tmp", "catatan-personal.json");
  }
  return path.join(process.cwd(), "data", "notes.json");
}

function upstashConfig() {
  const url = process.env.UPSTASH_REDIS_REST_URL || process.env.KV_REST_API_URL || "";
  const token = process.env.UPSTASH_REDIS_REST_TOKEN || process.env.KV_REST_API_TOKEN || "";
  return url && token ? { url: url.replace(/\/$/, ""), token } : null;
}

async function redisGet(key: string): Promise<NoteRecord | null> {
  const cfg = upstashConfig();
  if (!cfg) return null;
  const res = await fetch(`${cfg.url}/get/${encodeURIComponent(key)}`, {
    headers: { Authorization: `Bearer ${cfg.token}` },
    cache: "no-store",
  });
  if (!res.ok) return null;
  const payload = (await res.json()) as { result?: string | null };
  if (!payload.result) return null;
  try {
    return JSON.parse(payload.result) as NoteRecord;
  } catch {
    return encode(payload.result);
  }
}

async function redisSet(key: string, record: NoteRecord): Promise<boolean> {
  const cfg = upstashConfig();
  if (!cfg) return false;
  const res = await fetch(`${cfg.url}/set/${encodeURIComponent(key)}`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${cfg.token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(record),
  });
  return res.ok;
}

async function fileGet(): Promise<NoteRecord> {
  try {
    const raw = await fs.readFile(localPath(), "utf8");
    const parsed = JSON.parse(raw) as Partial<NoteRecord>;
    const text = typeof parsed.text === "string" ? parsed.text : "";
    return encode(text, parsed.updatedAt || new Date().toISOString());
  } catch {
    return { ...EMPTY };
  }
}

async function fileSet(record: NoteRecord): Promise<void> {
  const target = localPath();
  await fs.mkdir(path.dirname(target), { recursive: true });
  await fs.writeFile(target, JSON.stringify(record), "utf8");
}

export async function readNotes(): Promise<NoteRecord> {
  const remote = await redisGet("catatan-personal");
  if (remote) return encode(remote.text || "", remote.updatedAt);
  return fileGet();
}

export async function writeNotes(text: string): Promise<NoteRecord> {
  const record = encode(text ?? "");
  const savedRemote = await redisSet("catatan-personal", record);
  if (!savedRemote) {
    await fileSet(record);
  }
  return record;
}
