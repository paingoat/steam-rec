import type { Metadata } from "next";
import Link from "next/link";
import { BrowseRow } from "@/components/BrowseRow";
import { TagFilter } from "@/components/TagFilter";
import { getGenres, getTags, normTag, prettyTag, recommendByTags, searchGames, USING_MOCK } from "@/lib/api";

export const metadata: Metadata = { title: "Browse" };

// Ô "Top Categories" như browse.png; nền gradient thay cho ảnh ghép
const CATEGORIES = [
  { tag: "action", bg: "from-[#5b3a29] to-[#2b1d17]" },
  { tag: "rpg", bg: "from-[#2f3f6b] to-[#1a2140]" },
  { tag: "free_to_play", bg: "from-[#2b5f86] to-[#173247]" },
  { tag: "anime", bg: "from-[#2f6b45] to-[#173a25]" },
  { tag: "co_op", bg: "from-[#8a5a24] to-[#4a2f12]" },
  { tag: "racing", bg: "from-[#7a2f5c] to-[#3d1730]" },
];

function first(v: string | string[] | undefined) {
  return (Array.isArray(v) ? v[0] : v) ?? "";
}

// Khám phá theo tag (cold-start) + tìm game theo tên (?q= từ ô search)
export default async function BrowsePage({ searchParams }: PageProps<"/browse">) {
  const sp = await searchParams;
  const q = first(sp.q).trim();
  const selected = [...new Set(first(sp.tags).split(",").map(normTag).filter(Boolean))];

  const [vocab, genres, rec, found] = await Promise.all([
    getTags(),
    getGenres(),
    q ? null : recommendByTags(selected),
    q ? searchGames(q) : null,
  ]);

  return (
    <div className="w-full px-6 py-10 lg:px-10">
      <h2 className="text-xl font-semibold">Top Categories</h2>
      <div className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-3 xl:grid-cols-6">
        {CATEGORIES.map((c) => (
          <Link
            key={c.tag}
            href={`/browse?tags=${c.tag}`}
            className={`grid aspect-[4/3] place-items-center rounded-[4px] bg-gradient-to-br ${c.bg} text-lg font-semibold text-white shadow-[0_6px_18px_rgba(0,0,0,0.35)] transition-transform hover:scale-[1.03]`}
          >
            {prettyTag(c.tag)}
          </Link>
        ))}
      </div>

      <h2 className="mt-12 text-xl font-semibold">Browse by Tags</h2>
      <div className="mt-4 grid gap-5 lg:grid-cols-[260px_minmax(0,1fr)]">
        <TagFilter vocab={vocab} genres={genres} selected={selected} />

        <div className="flex min-w-0 flex-col gap-3">
          <div className="flex flex-wrap items-center gap-2 rounded-[4px] bg-bg-deep px-4 py-3 text-[13px]">
            {found ? (
              <span>
                {found.length} result{found.length === 1 ? "" : "s"} for <span className="text-link">&quot;{q}&quot;</span>
              </span>
            ) : selected.length ? (
              <span>
                Top picks for{" "}
                <span className="text-link">{selected.map(prettyTag).join(" + ")}</span>
              </span>
            ) : (
              <span>Pick a few tags on the left to get recommendations. Showing the most popular games for now.</span>
            )}
            <span className="ml-auto flex gap-2 text-[12px]">
              {rec && <span className="rounded-[2px] bg-surface px-2 py-1 font-mono text-muted">mode: {rec.mode}</span>}
              {USING_MOCK && <span className="rounded-[2px] bg-[#5c4a1a] px-2 py-1 text-[#f2c94c]">Mock data</span>}
            </span>
          </div>

          {rec?.unknown_tags && rec.unknown_tags.length > 0 && (
            <p className="rounded-[3px] border border-[#5c4a1a] bg-[#2a2414] px-4 py-2 text-[12px] text-[#f2c94c]">
              Ignored unknown tags: {rec.unknown_tags.map(prettyTag).join(", ")}
            </p>
          )}

          {found?.map((g) => <BrowseRow key={g.app_id} game={g} />)}
          {rec?.items.map((item) => <BrowseRow key={item.app_id} game={item} rank={item.rank} />)}
          {found?.length === 0 && (
            <p className="px-1 py-6 text-[13px] text-muted">No game in the catalog matches this name.</p>
          )}
        </div>
      </div>
    </div>
  );
}
