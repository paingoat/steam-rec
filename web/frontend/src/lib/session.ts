import { cookies } from "next/headers";

export const SESSION_COOKIE = "uid";

export async function getUserId(): Promise<number | null> {
  const raw = (await cookies()).get(SESSION_COOKIE)?.value;
  const id = raw ? Number(raw) : NaN;
  return Number.isSafeInteger(id) && id > 0 ? id : null;
}
