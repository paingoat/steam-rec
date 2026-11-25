// Số liệu chép từ reports/benchmark.md, reports/eda.md và reports/eda_time_split.md (run full v2 trên Colab).
// Khi có run mới thì cập nhật file này cho khớp report.

export const RUN = {
  id: "20261125T045027Z-dbf308a-v2full",
  hardware: "Colab CPU High-RAM · 8 vCPU · Spark local[*] (single machine)",
  evalUsers: 100_000,
  split: "train < 2022-09-01 ≤ validation < 2022-11-01 ≤ test (ends 2022-12-31)",
};

export const DATASET = [
  { label: "Reviews", value: "41.2M", note: "Kaggle Game Recommendations on Steam v28" },
  { label: "Users", value: "14.3M", note: "13.78M with at least one review" },
  { label: "Games", value: "50.9k", note: "99.2% with tags after enrichment (HF + SteamSpy)" },
  { label: "Train after k-core 3/5", value: "3.00M × 30.7k", note: "users × games, 21.4M positive reviews before 2022-09-01" },
];

export const PIPELINE = [
  { step: "Kaggle v28", detail: "raw CSV/JSON" },
  { step: "Bronze", detail: "immutable + SHA-256 manifest" },
  { step: "Metadata", detail: "HF dataset + SteamSpy tags" },
  { step: "Silver", detail: "clean, dedup, DQ report" },
  { step: "Gold", detail: "global time split, k-core on train" },
  { step: "Models", detail: "Popularity · ALS · CB" },
  { step: "Top-K", detail: "precomputed per user" },
  { step: "Demo bundle", detail: "~113 MB on HF Hub" },
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
    how: "TF-IDF over tags + Steam genres/categories + description (tags filled from SteamSpy, descriptions from a public HF dataset when v28 has none), item-kNN from the user's history. Cold-start: cosine between chosen tags/genres and game tokens.",
    usedIn: "Recommended for You, Similar Titles, Browse by Tags / Genres",
  },
];

// Test metrics, K = 10 và K = 20, đánh giá một lần trên test (reports/benchmark.md, run v2)
export const METRICS = [
  { model: "Popularity", recall10: 0.0339, ndcg10: 0.0174, recall20: 0.0565, ndcg20: 0.0234, coverage: 0.002, eligible: 1.0 },
  { model: "ALS", recall10: 0.0781, ndcg10: 0.0428, recall20: 0.1243, ndcg20: 0.0552, coverage: 0.026, eligible: 1.0 },
  { model: "CB TF-IDF", recall10: 0.0278, ndcg10: 0.0153, recall20: 0.044, ndcg20: 0.0196, coverage: 0.657, eligible: 1.0 },
];

export const NOTES = [
  "One global time split for everyone: models learn only from reviews before 2022-09-01, are tuned on Sep–Oct 2022 and tested once on Nov–Dec 2022 (the Autumn and Winter sales). No future review of any user leaks into training.",
  "Each test user has all their positive reviews in the test window as targets (1.45 per user on average). Recall@K = hits / min(K, targets); NDCG uses the matching ideal ranking.",
  "23.8% of test targets are games that were not in the training data (mostly new releases). No collaborative model can recommend them, so they are reported separately and left out of the metrics.",
  "ALS is the most accurate: about 2.2× the Recall@20 of popularity. It was fit once on the training period (about 19 minutes on one machine).",
  "Enriched metadata fixed content-based coverage: CB now fills a full top-K for 100% of users (72% in the previous run) and covers 66% of the catalog vs 2.6% for ALS.",
  "Numbers are not directly comparable with the previous run (per-user leave-last-out split, one target per user).",
];
