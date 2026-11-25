import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { GameImage } from "@/components/GameImage";
import { GameTile } from "@/components/GameTile";
import { Rating } from "@/components/Rating";
import { getGame, getSimilar, normTag, steamStoreUrl, USING_MOCK } from "@/lib/api";
import { formatPrice } from "@/lib/format";

const btn = "rounded-[3px] bg-surface-2 px-4 py-2 text-[13px] text-text hover:bg-accent";

async function load(params: PageProps<"/game/[app_id]">["params"]) {
  const raw = (await params).app_id;
  const id = Number(raw);
  if (!/^\d+$/.test(raw) || !Number.isSafeInteger(id)) return null;
  return getGame(id);
}

export async function generateMetadata({ params }: PageProps<"/game/[app_id]">): Promise<Metadata> {
  const game = await load(params);
  return { title: game?.title ?? "Game not found" };
}

// Trang chi tiết game (theo store page.png) + "Similar Titles" = tính năng [2]
export default async function GamePage({ params }: PageProps<"/game/[app_id]">) {
  const game = await load(params);
  if (!game) notFound();

  const similar = await getSimilar(game);
  const price = formatPrice(game.price_final);
  const topTags = game.tags.slice(0, 3).map(normTag).join(",");

  return (
    <div className="w-full px-6 py-8 lg:px-10">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <h1 className="text-2xl font-semibold">{game.title}</h1>
        <div className="flex gap-2">
          {topTags && (
            <Link href={`/browse?tags=${topTags}`} className={btn}>
              Browse these tags
            </Link>
          )}
          <a href={steamStoreUrl(game.app_id)} target="_blank" rel="noreferrer" className={btn}>
            View on Steam ↗
          </a>
        </div>
      </div>

      <div className="mt-5 grid gap-5 lg:grid-cols-[minmax(0,1fr)_340px]">
        {/* Cột trái: ảnh lớn + khung giá */}
        <div className="flex min-w-0 flex-col gap-5">
          <div className="overflow-hidden rounded-[4px] bg-bg-deep">
            <GameImage appId={game.app_id} title={game.title} variant="capsule" className="aspect-[616/353] w-full" />
          </div>

          <div className="flex flex-wrap items-center justify-between gap-4 rounded-[4px] bg-bg-deep px-5 py-4">
            <div>
              <div className="text-[15px] font-semibold">Buy {game.title}</div>
              <div className="text-[12px] text-muted">Price from the dataset snapshot, may differ from Steam today</div>
            </div>
            <div className="flex items-center gap-3">
              {price && <span className="rounded-[2px] bg-black/30 px-3 py-1.5 text-[15px] font-semibold">{price}</span>}
              <a
                href={steamStoreUrl(game.app_id)}
                target="_blank"
                rel="noreferrer"
                className="rounded-[3px] bg-accent px-4 py-2 text-[13px] text-white hover:bg-accent-hover"
              >
                View on Steam
              </a>
            </div>
          </div>
        </div>

        {/* Cột phải: header + reviews + tags */}
        <aside className="flex flex-col gap-4 self-start rounded-[4px] bg-bg-deep p-4">
          <GameImage appId={game.app_id} title={game.title} className="aspect-[460/215] w-full rounded-[3px]" />

          <dl className="grid grid-cols-[90px_1fr] gap-y-3 text-[12px]">
            <dt className="text-muted">Reviews</dt>
            <dd>
              <Rating rating={game.rating} positive={game.positive_ratio} />
            </dd>
            <dt className="text-muted">App ID</dt>
            <dd className="font-mono text-text">{game.app_id}</dd>
          </dl>

          {game.tags.length > 0 && (
            <div>
              <div className="text-[12px] text-muted">Popular user-defined tags</div>
              <div className="mt-2 flex flex-wrap gap-1">
                {game.tags.map((t) => (
                  <Link
                    key={t}
                    href={`/browse?tags=${normTag(t)}`}
                    className="rounded-[2px] bg-surface-2 px-2 py-0.5 text-[11px] text-muted hover:bg-accent hover:text-white"
                  >
                    {t}
                  </Link>
                ))}
              </div>
            </div>
          )}
        </aside>
      </div>

      <section id="similar" className="mt-12 scroll-mt-28">
        <div className="flex flex-wrap items-end justify-between gap-2">
          <div>
            <h2 className="text-xl font-semibold">Similar Titles</h2>
            <p className="mt-1 text-[13px] text-muted">
              Games whose tags best match this one (content-based, TF-IDF on tags).
            </p>
          </div>
          <div className="flex gap-2 text-[12px]">
            <span className="rounded-[2px] bg-surface px-2 py-1 font-mono text-muted">mode: {similar.mode}</span>
            {USING_MOCK && <span className="rounded-[2px] bg-[#5c4a1a] px-2 py-1 text-[#f2c94c]">Mock data</span>}
          </div>
        </div>

        {similar.items.length > 0 ? (
          <div className="mt-5 grid gap-5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
            {similar.items.map((item) => (
              <GameTile key={item.app_id} item={item} />
            ))}
          </div>
        ) : (
          <p className="mt-5 text-[13px] text-muted">This game has no tags, so we can&apos;t find similar titles.</p>
        )}
      </section>
    </div>
  );
}
