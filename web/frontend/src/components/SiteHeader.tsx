import Link from "next/link";
import { logout } from "@/app/actions";
import { getUserId } from "@/lib/session";
import { NavTabs } from "./NavTabs";
import { SteamLogo } from "./SteamLogo";

export async function SiteHeader() {
  const userId = await getUserId();
  if (userId === null) return <ClassicHeader />;

  return (
    <header className="sticky top-0 z-20">
      <div className="bg-topbar">
        <div className="flex h-12 w-full items-center justify-between px-6">
          <Link href="/">
            <SteamLogo size="sm" />
          </Link>
          <div className="flex items-center gap-3 text-sm">
            <span className="rounded bg-surface px-3 py-1 text-muted">
              user_id <span className="font-mono text-text">{userId}</span>
            </span>
            <form action={logout}>
              <button className="text-muted hover:text-text">Sign out</button>
            </form>
          </div>
        </div>
      </div>
      <div className="border-b border-border bg-nav">
        <div className="flex h-11 w-full items-center px-6">
          <NavTabs />
        </div>
      </div>
    </header>
  );
}

// Header kiểu Steam cổ điển cho người chưa đăng nhập (trang /login, /browse)
function ClassicHeader() {
  return (
    <header className="bg-[#171a21] font-[Arial,Helvetica,sans-serif]">
      <div className="relative mx-auto flex h-[104px] max-w-[940px] items-center gap-10 px-4">
        <Link href="/">
          <SteamLogo />
        </Link>
        <nav className="flex gap-7 pt-1 text-sm uppercase tracking-wide text-[#dcdedf]">
          <Link href="/browse" className="hover:text-white">Store</Link>
          <Link href="/login" className="hover:text-white">Sign in</Link>
        </nav>
        <div className="absolute right-4 top-1.5 text-[11px] text-[#b8b6b4]">
          <Link href="/login" className="hover:text-white">login</Link>
        </div>
      </div>
    </header>
  );
}
