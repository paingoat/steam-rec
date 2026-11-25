import type { Metadata } from "next";
import Link from "next/link";
import { DATASET, METRICS, MODELS, NOTES, PIPELINE, RUN } from "@/lib/report";

export const metadata: Metadata = { title: "About" };

const COLS = [
  { key: "recall10", label: "Recall@10" },
  { key: "ndcg10", label: "NDCG@10" },
  { key: "recall20", label: "Recall@20" },
  { key: "ndcg20", label: "NDCG@20" },
  { key: "coverage", label: "Catalog cov@20", pct: true },
  { key: "eligible", label: "Eligible users", pct: true },
] as const;

type Col = (typeof COLS)[number]["key"];

const best = (key: Col) => Math.max(...METRICS.map((m) => m[key]));

// Giới thiệu project: dữ liệu, pipeline, model và kết quả benchmark (dùng khi thuyết trình)
export default function AboutPage() {
  return (
    <div className="w-full px-6 py-10 lg:px-10">
      <h1 className="text-2xl font-semibold">How the recommendations are made</h1>
      <p className="mt-2 max-w-[760px] text-[13px] leading-relaxed text-muted">
        A batch recommender built on the Kaggle &quot;Game Recommendations on Steam&quot; dataset. Data flows through a
        Bronze → Silver → Gold lake, three models are trained with Spark, and each user&apos;s top-K is precomputed.
        This website only reads those precomputed results.
      </p>

      <section className="mt-8 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {DATASET.map((d) => (
          <div key={d.label} className="rounded-[4px] bg-bg-deep p-4">
            <div className="text-[12px] text-muted">{d.label}</div>
            <div className="mt-1 text-2xl font-semibold">{d.value}</div>
            <div className="mt-1 text-[12px] text-muted">{d.note}</div>
          </div>
        ))}
      </section>

      <h2 className="mt-12 text-xl font-semibold">Pipeline</h2>
      <ol className="mt-4 flex flex-wrap items-stretch gap-2">
        {PIPELINE.map((p, i) => (
          <li key={p.step} className="flex items-center gap-2">
            <div className="rounded-[4px] border border-border bg-bg-deep px-3 py-2">
              <div className="text-[13px] font-semibold">{p.step}</div>
              <div className="text-[11px] text-muted">{p.detail}</div>
            </div>
            {i < PIPELINE.length - 1 && <span className="text-muted">→</span>}
          </li>
        ))}
      </ol>

      <h2 className="mt-12 text-xl font-semibold">Models</h2>
      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        {MODELS.map((m) => (
          <div key={m.key} className="flex flex-col rounded-[4px] bg-bg-deep p-4">
            <div className="text-[15px] font-semibold">{m.name}</div>
            <p className="mt-2 text-[13px] leading-relaxed text-muted">{m.how}</p>
            <p className="mt-auto pt-3 text-[12px]">
              <span className="text-muted">Used in: </span>
              <span className="text-link">{m.usedIn}</span>
            </p>
          </div>
        ))}
      </div>

      <h2 className="mt-12 text-xl font-semibold">Test results</h2>
      <p className="mt-1 text-[12px] text-muted">
        Run <span className="font-mono">{RUN.id}</span> · {RUN.evalUsers.toLocaleString("en-US")} evaluation users ·{" "}
        {RUN.hardware}
      </p>
      <p className="mt-1 text-[12px] text-muted">
        Split: <span className="font-mono">{RUN.split}</span>
      </p>
      <div className="mt-4 overflow-x-auto rounded-[4px] bg-bg-deep">
        <table className="w-full min-w-[720px] text-[13px]">
          <thead>
            <tr className="border-b border-border text-left text-[12px] text-muted">
              <th className="px-4 py-3 font-normal">Model</th>
              {COLS.map((c) => (
                <th key={c.key} className="px-4 py-3 text-right font-normal">
                  {c.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {METRICS.map((m) => (
              <tr key={m.model} className="border-b border-border/50 last:border-0">
                <td className="px-4 py-3 font-semibold">{m.model}</td>
                {COLS.map((c) => {
                  const v = m[c.key];
                  const top = v === best(c.key);
                  return (
                    <td
                      key={c.key}
                      className={`px-4 py-3 text-right font-mono ${top ? "font-semibold text-positive" : "text-text"}`}
                    >
                      {"pct" in c ? `${(v * 100).toFixed(1)}%` : v.toFixed(4)}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-2 text-[11px] text-muted">Best value in each column is highlighted.</p>

      <ul className="mt-6 flex max-w-[900px] flex-col gap-2 text-[13px] leading-relaxed text-muted">
        {NOTES.map((n) => (
          <li key={n} className="flex gap-2">
            <span className="text-link">•</span>
            <span>{n}</span>
          </li>
        ))}
      </ul>

      <div className="mt-10 flex flex-wrap gap-3">
        <Link href="/discover" className="rounded-[3px] bg-accent px-4 py-2 text-[13px] text-white hover:bg-accent-hover">
          See your recommendations
        </Link>
        <Link href="/browse" className="rounded-[3px] bg-surface-2 px-4 py-2 text-[13px] hover:bg-accent">
          Browse by Tags
        </Link>
      </div>
    </div>
  );
}
