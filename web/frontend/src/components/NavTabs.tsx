"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const TABS = [
  { href: "/discover", label: "Recommended for You" },
  { href: "/browse", label: "Browse by Tags" },
];

export function NavTabs() {
  const pathname = usePathname();
  return (
    <nav className="flex gap-1">
      {TABS.map((t) => {
        const active = pathname.startsWith(t.href);
        return (
          <Link
            key={t.href}
            href={t.href}
            className={`rounded px-4 py-1.5 text-sm transition-colors ${
              active ? "bg-accent text-white" : "text-text hover:bg-surface-2"
            }`}
          >
            {t.label}
          </Link>
        );
      })}
    </nav>
  );
}
