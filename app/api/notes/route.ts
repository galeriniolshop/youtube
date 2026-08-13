import { NextResponse } from "next/server";
import { readNotes, writeNotes } from "@/lib/store";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function GET() {
  const note = await readNotes();
  return NextResponse.json(note, {
    headers: { "Cache-Control": "no-store" },
  });
}

export async function PUT(request: Request) {
  let body: { text?: unknown };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Payload tidak valid." }, { status: 400 });
  }
  if (typeof body.text !== "string") {
    return NextResponse.json({ error: "Teks catatan wajib berupa string." }, { status: 400 });
  }
  if (body.text.length > 400_000) {
    return NextResponse.json({ error: "Catatan terlalu panjang (maks 400 KB)." }, { status: 413 });
  }
  const note = await writeNotes(body.text);
  return NextResponse.json(note, {
    headers: { "Cache-Control": "no-store" },
  });
}
