import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { getUserId } from "@/lib/session";
import { LoginForm } from "./LoginForm";

export const metadata: Metadata = { title: "Sign In" };

const MENU = [
  { href: "/login", label: "Your Store" },
  { href: "/browse", label: "Browse by Tags" },
  { href: "/about", label: "About" },
];

export default async function LoginPage() {
  if ((await getUserId()) !== null) redirect("/discover");

  return (
    <div className="flex flex-1 flex-col bg-[linear-gradient(180deg,#2a475e_0%,#1b2838_420px)] font-[Arial,Helvetica,sans-serif]">
      <div className="mx-auto w-full max-w-[940px] flex-1 px-4 pt-6 pb-24">
        {/* Thanh menu xanh kiểu Steam */}
        <nav className="flex h-[35px] bg-[linear-gradient(90deg,rgba(62,103,150,0.92)_11%,rgba(58,120,177,0.8)_25%,rgb(15,33,110)_100%)] shadow-[0_0_3px_rgba(0,0,0,0.4)]">
          {MENU.map((m) => (
            <Link
              key={m.href}
              href={m.href}
              className="flex items-center border-r border-black/20 px-4 text-[13px] text-[#e5e5e5] hover:bg-white/10 hover:text-white"
            >
              {m.label}
            </Link>
          ))}
          <form action="/browse" className="ml-auto flex items-center pr-1">
            <input
              name="q"
              placeholder="search"
              className="h-[27px] w-[200px] rounded-l-[3px] border border-r-0 border-[#1b3b54] bg-[#316282] px-2 text-[13px] italic text-white outline-none placeholder:text-[#0e1c25]"
            />
            <button
              aria-label="Search"
              className="grid h-[27px] w-[27px] place-items-center rounded-r-[3px] bg-[#67c1f5] text-[#0e1c25] hover:bg-white"
            >
              <svg viewBox="0 0 16 16" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="6.5" cy="6.5" r="4.5" />
                <path d="M10 10l4 4" />
              </svg>
            </button>
          </form>
        </nav>

        <LoginForm />
      </div>

    </div>
  );
}
