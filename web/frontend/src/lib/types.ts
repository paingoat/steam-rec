// Khớp với output của steam_rec.serving.demo.Demo (xem docs/web-demo.md)

export type Model = "als" | "cb" | "popularity";

export interface RecItem {
  rank: number;
  app_id: number;
  title: string;
  score: number;
  rating: string;
  tags: string[]; // tối đa 5
  source: string; // ví dụ "popularity-backfill"
}

export interface RecResult {
  mode: string; // "precomputed:als", "fallback:popularity (...)", "cold-start:tags", ...
  items: RecItem[];
  user_id?: number;
  run_id?: string;
  unknown_tags?: string[];
}

export interface UserCheck {
  user_id: number;
  known: boolean; // có top-K precomputed hay không
}
