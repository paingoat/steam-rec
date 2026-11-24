import type { UserCheck } from "./types";

// Khi backend FastAPI sẵn sàng, đặt NEXT_PUBLIC_API_URL (ví dụ http://localhost:8000).
// Chưa đặt thì dùng dữ liệu giả để dựng giao diện.
const API_URL = process.env.NEXT_PUBLIC_API_URL;

export const SAMPLE_USERS = [511, 615, 731, 11442391];

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`API ${path} -> ${res.status}`);
  return res.json() as Promise<T>;
}

export async function checkUser(userId: number): Promise<UserCheck> {
  if (!API_URL) return { user_id: userId, known: SAMPLE_USERS.includes(userId) };
  return get<UserCheck>(`/api/users/${userId}`);
}

export function steamHeader(appId: number): string {
  return `https://cdn.cloudflare.steamstatic.com/steam/apps/${appId}/header.jpg`;
}
