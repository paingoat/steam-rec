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
  // Demo không trả 2 trường này; adapter của backend lấy thêm từ demo.catalog
  price_final?: number;
  positive_ratio?: number; // 0-100
}

export interface RecResult {
  mode: string; // "precomputed:als", "fallback:popularity (no history)" / "(history-masked)", "cold-start:tags", ...
  items: RecItem[];
  user_id?: number;
  run_id?: string;
  unknown_tags?: string[];
}

// Một dòng của demo.catalog (đủ tags, không cắt còn 5)
export interface GameDetail {
  app_id: number;
  title: string;
  rating: string;
  positive_ratio: number;
  price_final: number;
  tags: string[];
}

export interface UserCheck {
  user_id: number;
  known: boolean; // có top-K precomputed hay không
}
