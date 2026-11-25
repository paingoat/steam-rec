import type { GameDetail, Model, RecItem, RecResult } from "./types";

// Dữ liệu giả cùng format với Demo, chỉ dùng khi chưa đặt NEXT_PUBLIC_API_URL.
// app_id là game thật để ảnh header.jpg của Steam hiển thị được.
type Row = [app_id: number, title: string, rating: string, positive_ratio: number, price: number, tags: string[]];

const ROWS: Record<Model, Row[]> = {
  als: [
    [1245620, "ELDEN RING", "Very Positive", 92, 59.99, ["Souls-like", "Open World", "Dark Fantasy", "RPG", "Difficult"]],
    [374320, "DARK SOULS III", "Overwhelmingly Positive", 94, 59.99, ["Souls-like", "Dark Fantasy", "RPG", "Difficult", "Action"]],
    [814380, "Sekiro: Shadows Die Twice", "Overwhelmingly Positive", 95, 59.99, ["Souls-like", "Difficult", "Action", "Ninja", "Singleplayer"]],
    [1086940, "Baldur's Gate 3", "Overwhelmingly Positive", 96, 59.99, ["RPG", "Choices Matter", "Story Rich", "Turn-Based Combat", "Fantasy"]],
    [292030, "The Witcher 3: Wild Hunt", "Overwhelmingly Positive", 96, 39.99, ["Open World", "RPG", "Story Rich", "Fantasy", "Mature"]],
    [489830, "The Elder Scrolls V: Skyrim Special Edition", "Very Positive", 92, 39.99, ["Open World", "RPG", "Fantasy", "Moddable", "Adventure"]],
    [367520, "Hollow Knight", "Overwhelmingly Positive", 97, 14.99, ["Metroidvania", "Souls-like", "2D", "Difficult", "Platformer"]],
    [1091500, "Cyberpunk 2077", "Very Positive", 86, 59.99, ["Cyberpunk", "Open World", "RPG", "Sci-fi", "FPS"]],
    [413150, "Stardew Valley", "Overwhelmingly Positive", 98, 14.99, ["Farming Sim", "Life Sim", "Pixel Graphics", "Relaxing", "Co-op"]],
    [105600, "Terraria", "Overwhelmingly Positive", 97, 9.99, ["Sandbox", "Survival", "2D", "Crafting", "Adventure"]],
  ],
  cb: [
    [275850, "No Man's Sky", "Very Positive", 82, 59.99, ["Open World", "Survival", "Space", "Exploration", "Crafting"]],
    [108600, "Project Zomboid", "Very Positive", 93, 19.99, ["Survival", "Zombies", "Open World", "Sandbox", "Multiplayer"]],
    [892970, "Valheim", "Very Positive", 94, 19.99, ["Survival", "Open World", "Crafting", "Co-op", "Viking"]],
    [264710, "Subnautica", "Overwhelmingly Positive", 96, 29.99, ["Survival", "Underwater", "Open World", "Exploration", "Crafting"]],
    [242760, "The Forest", "Very Positive", 94, 19.99, ["Survival", "Horror", "Open World", "Crafting", "Co-op"]],
    [252490, "Rust", "Very Positive", 87, 39.99, ["Survival", "Crafting", "Multiplayer", "Open World", "PvP"]],
    [346110, "ARK: Survival Evolved", "Mostly Positive", 79, 29.99, ["Survival", "Dinosaurs", "Open World", "Crafting", "Multiplayer"]],
    [322330, "Don't Starve Together", "Overwhelmingly Positive", 95, 14.99, ["Survival", "Co-op", "Crafting", "Difficult", "2D"]],
    [251570, "7 Days to Die", "Very Positive", 88, 24.99, ["Survival", "Zombies", "Open World", "Crafting", "Voxel"]],
    [1623730, "Palworld", "Very Positive", 93, 29.99, ["Survival", "Open World", "Creature Collector", "Crafting", "Co-op"]],
  ],
  popularity: [
    [271590, "Grand Theft Auto V", "Very Positive", 86, 29.99, ["Open World", "Action", "Multiplayer", "Crime", "Third Person"]],
    [359550, "Tom Clancy's Rainbow Six Siege", "Very Positive", 85, 19.99, ["FPS", "PvP", "Tactical", "Multiplayer", "Shooter"]],
    [578080, "PUBG: BATTLEGROUNDS", "Mixed", 57, 0, ["Battle Royale", "Shooter", "Multiplayer", "PvP", "FPS"]],
    [945360, "Among Us", "Very Positive", 91, 4.99, ["Multiplayer", "Online Co-Op", "Social Deduction", "2D", "Casual"]],
    [252950, "Rocket League", "Very Positive", 86, 0, ["Soccer", "Sports", "Multiplayer", "Racing", "Competitive"]],
    [431960, "Wallpaper Engine", "Overwhelmingly Positive", 98, 3.99, ["Utilities", "Design & Illustration", "Animation", "Casual", "Indie"]],
    [1172470, "Apex Legends", "Mostly Positive", 70, 0, ["Free to Play", "Battle Royale", "Multiplayer", "FPS", "Shooter"]],
    [413150, "Stardew Valley", "Overwhelmingly Positive", 98, 14.99, ["Farming Sim", "Life Sim", "Pixel Graphics", "Relaxing", "Co-op"]],
    [105600, "Terraria", "Overwhelmingly Positive", 97, 9.99, ["Sandbox", "Survival", "2D", "Crafting", "Adventure"]],
    [1245620, "ELDEN RING", "Very Positive", 92, 59.99, ["Souls-like", "Open World", "Dark Fantasy", "RPG", "Difficult"]],
  ],
};

function items(model: Model, source: string): RecItem[] {
  return ROWS[model].map(([app_id, title, rating, positive_ratio, price_final, tags], i) => ({
    rank: i + 1,
    app_id,
    title,
    rating,
    positive_ratio,
    price_final,
    tags,
    score: Math.round((model === "popularity" ? 1 - i * 0.07 : 0.82 - i * 0.05) * 1e4) / 1e4,
    source,
  }));
}

export function mockForUser(userId: number, model: Model, known: boolean): RecResult {
  if (!known) {
    return {
      user_id: userId,
      mode: "fallback:popularity (user has no precomputed top-K)",
      items: items("popularity", "popularity"),
    };
  }
  return { user_id: userId, mode: `precomputed:${model}`, run_id: "mock", items: items(model, model) };
}

// Catalog giả = mọi game xuất hiện trong ROWS (không trùng app_id)
const CATALOG = new Map<number, GameDetail>();
for (const rows of Object.values(ROWS)) {
  for (const [app_id, title, rating, positive_ratio, price_final, tags] of rows) {
    CATALOG.set(app_id, { app_id, title, rating, positive_ratio, price_final, tags });
  }
}

export const mockCatalog = (): GameDetail[] => [...CATALOG.values()];

export function mockGame(appId: number): GameDetail | null {
  return CATALOG.get(appId) ?? null;
}

// Giống for_new_user(tags) nhưng chấm điểm bằng độ trùng tag trên catalog giả
export function mockForTags(tags: string[], exclude?: number, k = 10): RecResult {
  const norm = (t: string) => t.trim().toLowerCase().replace(/[ -]/g, "_");
  const want = new Set(tags.map(norm));
  const scored = mockCatalog()
    .filter((g) => g.app_id !== exclude)
    .map((g) => {
      const hit = g.tags.filter((t) => want.has(norm(t))).length;
      return { g, score: hit / Math.sqrt(want.size * g.tags.length || 1) };
    })
    .filter((x) => x.score > 0)
    .sort((a, b) => b.score - a.score || b.g.positive_ratio - a.g.positive_ratio)
    .slice(0, k);
  const known = new Set(mockCatalog().flatMap((g) => g.tags.map(norm)));
  return {
    mode: scored.length ? "cold-start:tags" : "fallback:popularity (no known tags)",
    unknown_tags: tags.filter((t) => !known.has(norm(t))),
    items: (scored.length ? scored : items("popularity", "popularity").map((i) => ({ g: mockGame(i.app_id)!, score: i.score })))
      .slice(0, k)
      .map(({ g, score }, i) => ({
        rank: i + 1,
        app_id: g.app_id,
        title: g.title,
        rating: g.rating,
        positive_ratio: g.positive_ratio,
        price_final: g.price_final,
        tags: g.tags.slice(0, 5),
        score: Math.round(score * 1e4) / 1e4,
        source: scored.length ? "cb-tags" : "popularity",
      })),
  };
}
