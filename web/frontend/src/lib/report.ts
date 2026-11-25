// Số liệu chép từ reports/benchmark.md và reports/eda.md (run full trên Colab).
// Khi có run mới thì cập nhật file này cho khớp report.

export const RUN = {
  id: "20261111T030116Z-3ef4284-e0820c90",
  hardware: "Colab CPU High-RAM · 8 vCPU · 54.8 GB RAM · Spark local[*] (single machine)",
  evalUsers: 100_000,
};

export const DATASET = [
  { label: "Reviews", value: "41.2M", note: "Kaggle Game Recommendations on Steam v28" },
  { label: "Users", value: "14.3M", note: "13.78M with at least one review" },
  { label: "Games", value: "50.9k", note: "441 distinct tags, 11.5 tags/game" },
  { label: "After k-core 3/5", value: "3.30M × 32.7k", note: "users × games, 17.1M train interactions" },
];

export const PIPELINE = [
  { step: "Kaggle v28", detail: "raw CSV/JSON" },
  { step: "Bronze", detail: "immutable + SHA-256 manifest" },
  { step: "Silver", detail: "clean, dedup, DQ report" },
  { step: "Gold", detail: "k-core, time-based split" },
  { step: "Models", detail: "Popularity · ALS · CB" },
  { step: "Top-K", detail: "precomputed per user" },
  { step: "Demo bundle", detail: "~65 MB on HF Hub" },
  { step: "This website", detail: "FastAPI + Next.js" },
];

export const MODELS = [
  {
    key: "popularity",
    name: "Popularity",
    how: "Ranks games by number of positive reviews, masking what the user already reviewed.",
    usedIn: "Fallback for unknown users and when no tag is picked",
  },
  {
    key: "als",
    name: "ALS (implicit)",
    how: "Spark MLlib matrix factorization on positive reviews, confidence 1 + log1p(hours). Rank 32, α = 5, λ = 0.1, 10 iterations.",
    usedIn: "Recommended for You (default model)",
  },
  {
    key: "cb",
    name: "Content-based (TF-IDF)",
    how: "TF-IDF over tags + description, item-kNN from the user's history. Cold-start: cosine between chosen tags and game tags.",
    usedIn: "Recommended for You, Similar Titles, Browse by Tags",
  },
];

// Test metrics, K = 20 (và K = 10), đánh giá một lần trên test
export const METRICS = [
  { model: "Popularity", recall10: 0.033, ndcg10: 0.0166, recall20: 0.0633, ndcg20: 0.0242, coverage: 0.001, eligible: 1.0 },
  { model: "ALS", recall10: 0.0689, ndcg10: 0.0359, recall20: 0.1091, ndcg20: 0.046, coverage: 0.025, eligible: 1.0 },
  { model: "CB TF-IDF", recall10: 0.0101, ndcg10: 0.006, recall20: 0.0133, ndcg20: 0.0068, coverage: 0.792, eligible: 0.718 },
];

export const NOTES = [
  "Same 100k evaluation users, same per-user time-based split (leave-last-out), same mask and catalog for all three models. Hyper-parameters chosen on validation; test was run once.",
  "ALS is the most accurate: about 1.7× the Recall@20 of popularity.",
  "CB is limited by the data: many of the most popular games have empty tags and description in v28, so CB can fill a full top-K for only 72% of users. In exchange it has by far the widest catalog coverage (79% vs 2.5% for ALS).",
  "Everything ran on one machine (not a cluster). Full ALS fit took about 22 minutes per configuration.",
];
