"use client";

import Link from "next/link";
import { useActionState, useRef } from "react";
import { login, type LoginState } from "@/app/actions";

// Nút phẳng xanh, chữ xanh nhạt như nút "Sign in" / "Join Steam"
const btn =
  "inline-block rounded-[2px] bg-[#214b6b] px-4 py-[7px] text-[15px] text-[#67c1f5] hover:bg-[#3a8ac4] hover:text-white disabled:opacity-60";

export function LoginForm({ sampleUsers }: { sampleUsers: number[] }) {
  const [state, action, pending] = useActionState<LoginState, FormData>(login, {});
  const inputRef = useRef<HTMLInputElement>(null);

  return (
    <div className="mt-4 grid md:grid-cols-2">
      {/* Cột trái: đăng nhập */}
      <form action={action} className="flex flex-col pb-8 md:pr-4">
        <h1 className="text-[22px] leading-tight text-[#67c1f5]">Sign in</h1>
        <p className="text-xs text-white">To an existing Steam account</p>

        <label htmlFor="user_id" className="mt-5 text-xs text-[#c6d4df]">
          Steam account name
        </label>
        <input
          id="user_id"
          ref={inputRef}
          name="user_id"
          inputMode="numeric"
          autoComplete="off"
          autoFocus
          required
          className="mt-1 h-[30px] w-full max-w-[236px] rounded-[3px] border border-[#4b6f8c] bg-[#102233] px-1.5 text-[15px] text-white outline-none focus:border-[#67c1f5]"
        />
        {state.error && <p className="mt-2 text-xs text-[#d94126]">{state.error}</p>}

        <div className="mt-auto pt-10">
          <button disabled={pending} className={btn}>
            {pending ? "Signing in..." : "Sign in"}
          </button>
        </div>
      </form>

      {/* Cột phải: dùng thử (ứng với ô "Create" của Steam) */}
      <div className="flex flex-col border-[#3b5166] pb-8 md:border-l md:pl-4">
        <h2 className="text-[22px] leading-tight text-[#67c1f5]">Try it out</h2>
        <p className="text-xs text-white">No account needed</p>

        <p className="mt-5 max-w-[290px] text-xs leading-snug text-white">
          Pick a sample user to see their top-K recommendations, or choose a few tags you like to get
          recommendations right away without signing in.
        </p>
        <div className="mt-3 flex flex-wrap gap-1.5">
          {sampleUsers.map((id) => (
            <button
              key={id}
              type="button"
              onClick={() => {
                if (!inputRef.current) return;
                inputRef.current.value = String(id);
                inputRef.current.focus();
              }}
              className="rounded-[2px] bg-[#1b3b54] px-2 py-0.5 text-xs text-[#67c1f5] hover:bg-[#3a8ac4] hover:text-white"
            >
              {id}
            </button>
          ))}
        </div>

        <div className="mt-auto pt-10">
          <Link href="/browse" className={btn}>
            Browse by Tags
          </Link>
        </div>
      </div>
    </div>
  );
}
