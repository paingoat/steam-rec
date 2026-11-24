import Link from "next/link";
import { formatPrice } from "@/lib/format";
import type { RecItem } from "@/lib/types";
import { GameImage } from "./GameImage";

// Thẻ game nhỏ dùng cho lưới "Similar Titles" và Browse
export function GameTile({ item }: { item: RecItem }) {
  const price = formatPrice(item.price_final);
  return (
    <Link
      href={`/game/${item.app_id}`}
      className="group flex flex-col overflow-hidden rounded-[4px] bg-bg-deep shadow-[0_6px_18px_rgba(0,0,0,0.3)] hover:bg-surface"
    >
      <GameImage appId={item.app_id} title={item.title} className="aspect-[460/215] w-full" />
      <div className="flex flex-1 flex-col p-3">
        <div className="truncate text-[15px] font-semibold text-text group-hover:text-link">{item.title}</div>
        <div className="mt-1 truncate text-[11px] text-muted">{item.tags.slice(0, 3).join(" · ")}</div>
        <div className="mt-auto flex items-center justify-between pt-3 text-[12px]">
          <span className="text-link">{item.rating}</span>
          {price && <span className="font-semibold text-text">{price}</span>}
        </div>
      </div>
    </Link>
  );
}
