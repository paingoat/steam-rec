import { mockCatalog, mockForTags, mockForUser, mockGame } from "./mock";
import type { GameDetail, Model, RecResult, UserCheck } from "./types";

// Khi backend FastAPI sẵn sàng, đặt NEXT_PUBLIC_API_URL (ví dụ http://localhost:8000).
// Chưa đặt thì dùng dữ liệu giả để dựng giao diện.
const API_URL = process.env.NEXT_PUBLIC_API_URL;
export const USING_MOCK = !API_URL;

export const SAMPLE_USERS = [511, 615, 731, 11442391];
export const MODELS: Model[] = ["als", "cb", "popularity"];

export function parseModel(raw: unknown): Model {
  return MODELS.includes(raw as Model) ? (raw as Model) : "als";
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`API ${path} -> ${res.status}`);
  return res.json() as Promise<T>;
}

export async function checkUser(userId: number): Promise<UserCheck> {
  if (!API_URL) return { user_id: userId, known: SAMPLE_USERS.includes(userId) };
  return get<UserCheck>(`/api/users/${userId}`);
}

// Tính năng [1]: top-K precomputed cho user (fallback popularity nếu user không có top-K)
export async function getRecommendations(userId: number, model: Model): Promise<RecResult> {
  if (!API_URL) return mockForUser(userId, model, SAMPLE_USERS.includes(userId));
  return get<RecResult>(`/api/recommend/${userId}?model=${model}`);
}

// Một game trong catalog; null nếu app_id không có
export async function getGame(appId: number): Promise<GameDetail | null> {
  if (!API_URL) return mockGame(appId);
  const res = await fetch(`${API_URL}/api/games/${appId}`, { cache: "no-store" });
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`API /api/games/${appId} -> ${res.status}`);
  return res.json() as Promise<GameDetail>;
}

// Tính năng [2]: tags của game -> for_new_user(tags), đã loại chính game đó
export async function getSimilar(game: GameDetail): Promise<RecResult> {
  if (!API_URL) return mockForTags(game.tags, game.app_id);
  return get<RecResult>(`/api/games/${game.app_id}/similar`);
}

// Cold-start theo tag người dùng chọn
export async function recommendByTags(tags: string[]): Promise<RecResult> {
  if (!API_URL) return mockForTags(tags);
  return get<RecResult>(`/api/recommend/tags?${tags.map((t) => `tags=${encodeURIComponent(t)}`).join("&")}`);
}

// demo.tag_vocab: tag đã chuẩn hóa (lowercase, "_" thay space/"-")
export async function getTags(): Promise<string[]> {
  if (!API_URL) {
    const all = mockCatalog().flatMap((g) => g.tags.map(normTag));
    return [...new Set(all)].sort();
  }
  return get<string[]>("/api/tags");
}

export function normTag(t: string): string {
  return t.trim().toLowerCase().replace(/[ -]/g, "_");
}

const UPPER = new Set(["rpg", "jrpg", "arpg", "crpg", "fps", "mmo", "mmorpg", "pvp", "pve", "vr", "rts", "moba", "2d", "3d", "4x"]);

// "open_world" -> "Open World", "rpg" -> "RPG", "co_op" -> "Co-op" để hiển thị
export function prettyTag(t: string): string {
  if (t === "co_op") return "Co-op";
  return t
    .split("_")
    .map((w) => (UPPER.has(w) ? w.toUpperCase() : w.charAt(0).toUpperCase() + w.slice(1)))
    .join(" ");
}

// Tìm game theo tên trong catalog (adapter của backend lọc demo.catalog)
export async function searchGames(q: string): Promise<GameDetail[]> {
  if (!API_URL) {
    const needle = q.trim().toLowerCase();
    return mockCatalog().filter((g) => g.title.toLowerCase().includes(needle));
  }
  return get<GameDetail[]>(`/api/games?q=${encodeURIComponent(q)}`);
}

export function steamStoreUrl(appId: number): string {
  return `https://store.steampowered.com/app/${appId}/`;
}

export function steamHeader(appId: number): string {
  return `https://cdn.cloudflare.steamstatic.com/steam/apps/${appId}/header.jpg`;
}
