"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { cn } from "@/lib/utils";

const LINKS = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/wc2026", label: "WC 2026" },
  { href: "/compare", label: "Compare" },
  { href: "/player-lab", label: "Lab" },
  { href: "/models", label: "Models" },
  { href: "/simulate", label: "Match" },
  { href: "/tournament", label: "Tournament" },
  { href: "/scenarios", label: "Scenarios" },
  { href: "/teams", label: "Teams" },
  { href: "/saved", label: "Saved" },
];

export function Nav() {
  const pathname = usePathname();
  const { user, logout, loading } = useAuth();

  return (
    <header className="sticky top-0 z-50 border-b border-line bg-ink/85 backdrop-blur-md">
      <div className="mx-auto max-w-6xl px-5 h-16 flex items-center gap-8">
        <Link href="/" className="flex items-center gap-2 shrink-0">
          <span className="h-3 w-3 rounded-full bg-pitch shadow-[0_0_12px_hsl(var(--pitch))]" />
          <span className="display text-lg tracking-tight">WCIP</span>
        </Link>

        <nav className="hidden md:flex items-center gap-1">
          {LINKS.map((l) => {
            const active = pathname === l.href;
            return (
              <Link
                key={l.href}
                href={l.href}
                className={cn(
                  "px-3 py-2 text-sm rounded-md transition-colors uppercase tracking-wide",
                  active ? "text-pitch" : "text-muted hover:text-fg",
                )}
              >
                {l.label}
              </Link>
            );
          })}
        </nav>

        <div className="ml-auto flex items-center gap-3">
          {loading ? null : user ? (
            <>
              {user.role === "admin" && (
                <Link href="/admin" className="hidden sm:inline text-xs uppercase tracking-wide text-muted hover:text-pitch">
                  Admin
                </Link>
              )}
              <Link href="/profile" className="hidden sm:inline text-xs text-muted tnum hover:text-fg">
                {user.email}
              </Link>
              <button
                onClick={logout}
                className="text-xs uppercase tracking-wide text-muted hover:text-signal transition-colors"
              >
                Sign out
              </button>
            </>
          ) : (
            <>
              <Link href="/login" className="text-sm text-muted hover:text-fg uppercase tracking-wide">
                Log in
              </Link>
              <Link
                href="/register"
                className="text-sm bg-pitch text-ink font-semibold px-4 py-2 rounded-md uppercase tracking-wide hover:brightness-110"
              >
                Sign up
              </Link>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
