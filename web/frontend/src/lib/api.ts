import { mockForUser } from "./mock";
import type { Model, RecResult, UserCheck } from "./types";

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

export function steamHeader(appId: number): string {
  return `https://cdn.cloudflare.steamstatic.com/steam/apps/${appId}/header.jpg`;
}
