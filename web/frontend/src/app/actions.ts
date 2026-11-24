"use server";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { SESSION_COOKIE } from "@/lib/session";

export interface LoginState {
  error?: string;
}

export async function login(_prev: LoginState, formData: FormData): Promise<LoginState> {
  const raw = String(formData.get("user_id") ?? "").trim();
  const id = Number(raw);
  if (!/^\d+$/.test(raw) || !Number.isSafeInteger(id) || id <= 0) {
    return { error: "Please enter your numeric Steam account ID (e.g. 11442391)." };
  }

  // User chưa có top-K vẫn được vào: backend trả popularity chung (fallback),
  // trang Discover sẽ hiện badge `mode` để báo việc này.
  (await cookies()).set(SESSION_COOKIE, String(id), {
    httpOnly: true,
    sameSite: "lax",
    path: "/",
    maxAge: 60 * 60 * 24 * 7,
  });
  redirect("/discover");
}

export async function logout() {
  (await cookies()).delete(SESSION_COOKIE);
  redirect("/login");
}
