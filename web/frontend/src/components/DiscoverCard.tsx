import Link from "next/link";
import { formatPrice } from "@/lib/format";
import type { RecItem } from "@/lib/types";
import { GameImage } from "./GameImage";
import { Rating } from "./Rating";

const MODEL_LABEL: Record<string, string> = {
  als: "ALS (collaborative filtering)",
  cb: "Content-based (TF-IDF)",
  popularity: "Popularity",
  "popularity-backfill": "Popularity (backfill)",
};

const btn = "rounded-[3px] bg-surface-2 px-4 py-2 text-[13px] text-text hover:bg-accent";

// Một thẻ game trong Discovery Feed (theo discover.png)
export function DiscoverCard({ item }: { item: RecItem }) {
  const price = formatPrice(item.price_final);
  const href = `/game/${item.app_id}`;

  return (
    <article className="grid gap-5 rounded-[4px] bg-bg-deep p-4 shadow-[0_8px_24px_rgba(0,0,0,0.35)] md:grid-cols-[minmax(0,460px)_1fr]">
      <Link href={href} className="block overflow-hidden rounded-[3px]">
        <GameImage
          appId={item.app_id}
          title={item.title}
          className="aspect-[460/215] w-full transition-transform duration-300 hover:scale-[1.03]"
        />
      </Link>

      <div className="flex min-w-0 flex-col">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <Link href={href} className="block truncate text-xl font-semibold text-text hover:text-link">
              {item.title}
            </Link>
            <p className="mt-0.5 text-[13px] text-muted">
              Recommended by <span className="text-text">{MODEL_LABEL[item.source] ?? item.source}</span>
            </p>
          </div>
          <div className="shrink-0 text-right">
            <div className="text-2xl font-semibold text-muted">#{item.rank}</div>
            <div className="font-mono text-[11px] text-muted">score {item.score.toFixed(4)}</div>
          </div>
        </div>

        {item.tags.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-1">
            {item.tags.map((t) => (
              <span key={t} className="rounded-[2px] bg-surface-2 px-2 py-0.5 text-[11px] text-muted">
                {t}
              </span>
            ))}
          </div>
        )}

        <Rating rating={item.rating} positive={item.positive_ratio} className="mt-4 max-w-[260px]" />

        <div className="mt-auto flex flex-wrap items-center gap-3 pt-5">
          <Link href={`${href}#similar`} className={btn}>
            Find more like this
          </Link>
          <div className="ml-auto flex items-center gap-3">
            {price && <span className="text-[15px] font-semibold text-text">{price}</span>}
            <Link href={href} className={btn}>
              Visit Store Page
            </Link>
          </div>
        </div>
      </div>
    </article>
  );
}
