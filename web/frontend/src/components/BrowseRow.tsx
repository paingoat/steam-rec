import Link from "next/link";
import { normTag } from "@/lib/api";
import { formatPrice } from "@/lib/format";
import { GameImage } from "./GameImage";
import { Rating } from "./Rating";

interface Game {
  app_id: number;
  title: string;
  rating: string;
  tags: string[];
  positive_ratio?: number;
  price_final?: number;
}

// Một dòng game trong danh sách Browse (theo browse.png)
export function BrowseRow({ game, rank }: { game: Game; rank?: number }) {
  const href = `/game/${game.app_id}`;
  const price = formatPrice(game.price_final);

  return (
    <article className="flex flex-col gap-4 rounded-[4px] bg-bg-deep p-3 shadow-[0_6px_18px_rgba(0,0,0,0.3)] sm:flex-row">
      <Link href={href} className="shrink-0 overflow-hidden rounded-[3px] sm:w-[230px]">
        <GameImage appId={game.app_id} title={game.title} className="aspect-[460/215] w-full" />
      </Link>

      <div className="flex min-w-0 flex-1 flex-col">
        <Link href={href} className="truncate text-[17px] font-semibold text-text hover:text-link">
          {rank !== undefined && <span className="mr-2 text-muted">#{rank}</span>}
          {game.title}
        </Link>
        <div className="mt-2 flex flex-wrap gap-1">
          {game.tags.slice(0, 5).map((t) => (
            <Link
              key={t}
              href={`/browse?tags=${normTag(t)}`}
              className="rounded-[2px] bg-surface-2 px-2 py-0.5 text-[11px] text-muted hover:bg-accent hover:text-white"
            >
              {t}
            </Link>
          ))}
        </div>
        <Rating rating={game.rating} positive={game.positive_ratio} className="mt-auto max-w-[240px] pt-3" />
      </div>

      <div className="flex items-end justify-end gap-3 sm:flex-col sm:items-end sm:justify-end">
        {price && <span className="text-[15px] font-semibold">{price}</span>}
        <Link href={href} className="rounded-[3px] bg-accent px-4 py-2 text-[13px] text-white hover:bg-accent-hover">
          View Game
        </Link>
      </div>
    </article>
  );
}
