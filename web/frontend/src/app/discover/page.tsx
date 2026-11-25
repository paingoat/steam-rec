import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { DiscoverCard } from "@/components/DiscoverCard";
import { getRecommendations, MODELS, parseModel, USING_MOCK } from "@/lib/api";
import { getUserId } from "@/lib/session";
import type { Model } from "@/lib/types";

export const metadata: Metadata = { title: "Discovery Feed" };

const MODEL_TAB: Record<Model, string> = { als: "ALS", cb: "Content-based", popularity: "Popularity" };

// Tính năng [1]: top-K game precomputed cho user đang đăng nhập
export default async function DiscoverPage({ searchParams }: PageProps<"/discover">) {
  const userId = await getUserId();
  if (userId === null) redirect("/login");

  const model = parseModel((await searchParams).model);
  const res = await getRecommendations(userId, model);
  const fallback = res.mode.startsWith("fallback");

  return (
    <div className="w-full px-6 py-10 lg:px-10">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">
            <span className="font-mono">{userId}</span>&apos;s Discovery Feed
          </h1>
          <p className="mt-1 text-[13px] text-muted">
            Recommendations just for you, based on the games you have reviewed.
          </p>
        </div>

        {/* Chọn model; user fallback chỉ có popularity nên ẩn */}
        {!fallback && (
          <div className="flex rounded-[3px] bg-surface p-1 text-[13px]">
            {MODELS.map((m) => (
              <Link
                key={m}
                href={`/discover?model=${m}`}
                className={`rounded-[2px] px-3 py-1.5 ${m === model ? "bg-accent text-white" : "text-muted hover:text-text"}`}
              >
                {MODEL_TAB[m]}
              </Link>
            ))}
          </div>
        )}
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-2 text-[12px]">
        <span className="rounded-[2px] bg-surface px-2 py-1 font-mono text-muted">mode: {res.mode}</span>
        {res.run_id && <span className="rounded-[2px] bg-surface px-2 py-1 font-mono text-muted">run: {res.run_id}</span>}
        {USING_MOCK && (
          <span className="rounded-[2px] bg-[#5c4a1a] px-2 py-1 text-[#f2c94c]">Mock data — backend not connected</span>
        )}
      </div>

      {fallback && (
        <p className="mt-4 rounded-[3px] border border-border bg-surface px-4 py-3 text-[13px] text-muted">
          We don&apos;t have a review history for this account yet, so here are the most popular games instead. Try{" "}
          <Link href="/browse" className="text-link hover:underline">
            Browse by Tags
          </Link>{" "}
          to get recommendations from the genres you like.
        </p>
      )}

      <div className="mt-8 flex flex-col gap-8">
        {res.items.map((item) => (
          <DiscoverCard key={item.app_id} item={item} />
        ))}
      </div>
    </div>
  );
}
