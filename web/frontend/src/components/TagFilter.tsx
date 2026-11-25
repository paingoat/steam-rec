"use client";

import Link from "next/link";
import { useState } from "react";
import { prettyTag } from "@/lib/api";

// Tag hay dùng, hiện khi ô tìm tag đang trống (chỉ những tag có trong vocab)
const COMMON = [
  "action", "adventure", "rpg", "strategy", "simulation", "casual", "indie", "shooter", "fps", "open_world",
  "survival", "sandbox", "co_op", "multiplayer", "horror", "puzzle", "platformer", "racing", "sports", "anime",
];

function href(tags: string[]) {
  return tags.length ? `/browse?tags=${tags.join(",")}` : "/browse";
}

// Sidebar "Filters" của Browse: tìm tag trong tag_vocab, bấm để thêm/bỏ (trạng thái nằm trên URL)
export function TagFilter({ vocab, selected }: { vocab: string[]; selected: string[] }) {
  const [query, setQuery] = useState("");
  const q = query.trim().toLowerCase().replace(/[ -]/g, "_");
  const vocabSet = new Set(vocab);
  const list = q
    ? vocab.filter((t) => t.includes(q)).slice(0, 20)
    : COMMON.filter((t) => vocabSet.has(t));

  const toggle = (t: string) => href(selected.includes(t) ? selected.filter((s) => s !== t) : [...selected, t]);

  return (
    <aside className="self-start rounded-[4px] bg-bg-deep p-3 text-[13px]">
      <div className="flex items-center justify-between">
        <span className="text-[11px] uppercase tracking-wider text-muted">Filters</span>
        {selected.length > 0 && (
          <Link href="/browse" className="text-[11px] text-link hover:underline">
            Clear all
          </Link>
        )}
      </div>

      <input
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Search for a tag..."
        className="mt-3 h-8 w-full rounded-[3px] border border-border bg-input px-2 text-[13px] text-text outline-none placeholder:text-muted focus:border-accent"
      />

      {selected.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1">
          {selected.map((t) => (
            <Link
              key={t}
              href={toggle(t)}
              className="rounded-[2px] bg-accent px-2 py-0.5 text-[11px] text-white hover:bg-negative"
            >
              {prettyTag(t)} ×
            </Link>
          ))}
        </div>
      )}

      <div className="mt-4 border-t border-border pt-3 text-[12px] text-muted">
        {q ? `Tags matching "${query.trim()}"` : "Popular tags"}
      </div>
      <ul className="mt-2 flex flex-col">
        {list.map((t) => {
          const on = selected.includes(t);
          return (
            <li key={t}>
              <Link
                href={toggle(t)}
                className={`block rounded-[2px] px-2 py-1.5 ${on ? "bg-surface-2 text-text" : "text-muted hover:bg-surface hover:text-text"}`}
              >
                {on ? "✓ " : ""}
                {prettyTag(t)}
              </Link>
            </li>
          );
        })}
        {list.length === 0 && <li className="px-2 py-1.5 text-muted">No matching tag.</li>}
      </ul>
      <p className="mt-3 text-[11px] text-muted">{vocab.length} tags available</p>
    </aside>
  );
}
