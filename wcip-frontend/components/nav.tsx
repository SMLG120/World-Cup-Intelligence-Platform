"use client";

import Link from "next/link";
import { useState } from "react";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { cn } from "@/lib/utils";
import { AnimatePresence, motion } from "framer-motion";

const LINKS = [
  { href: "/world-cup", label: "WC 2026", group: "main" },
  { href: "/predict", label: "Predict", group: "main" },
  { href: "/compare", label: "Compare", group: "main" },
  { href: "/simulate", label: "Simulate", group: "main" },
  { href: "/scenarios", label: "Scenarios", group: "main" },
  { href: "/explain", label: "Explain", group: "analysis" },
  { href: "/models", label: "Models", group: "analysis" },
  { href: "/player-lab", label: "Lab", group: "analysis" },
  { href: "/teams", label: "Teams", group: "data" },
  { href: "/saved", label: "Saved", group: "data" },
];

export function Nav() {
  const pathname = usePathname();
  const { user, logout, loading } = useAuth();
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <header className="sticky top-0 z-50 border-b border-line bg-ink/85 backdrop-blur-md">
      <div className="mx-auto max-w-6xl px-5 h-16 flex items-center gap-6">
        {/* Logo */}
        <Link href="/" className="flex items-center gap-2 shrink-0" onClick={() => setMobileOpen(false)}>
          <span className="h-3 w-3 rounded-full bg-pitch shadow-[0_0_12px_hsl(var(--pitch))]" />
          <span className="display text-lg tracking-tight">WCIP</span>
        </Link>

        {/* Desktop nav */}
        <nav className="hidden md:flex items-center gap-0.5 flex-1 overflow-x-auto">
          {LINKS.map((l) => {
            const active = pathname === l.href || pathname.startsWith(l.href + "/");
            return (
              <Link
                key={l.href}
                href={l.href}
                className={cn(
                  "px-3 py-2 text-sm rounded-md transition-colors uppercase tracking-wide whitespace-nowrap",
                  active ? "text-pitch" : "text-muted hover:text-fg",
                )}
              >
                {l.label}
              </Link>
            );
          })}
        </nav>

        {/* Auth — desktop */}
        <div className="ml-auto hidden md:flex items-center gap-3 shrink-0">
          {loading ? null : user ? (
            <>
              {user.role === "admin" && (
                <Link href="/admin" className="text-xs uppercase tracking-wide text-muted hover:text-pitch transition-colors">
                  Admin
                </Link>
              )}
              <Link href="/profile" className="text-xs text-muted tnum hover:text-fg transition-colors">
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
              <Link href="/login" className="text-sm text-muted hover:text-fg uppercase tracking-wide transition-colors">
                Log in
              </Link>
              <Link
                href="/register"
                className="text-sm bg-pitch text-ink font-semibold px-4 py-2 rounded-md uppercase tracking-wide hover:brightness-110 transition-all"
              >
                Sign up
              </Link>
            </>
          )}
        </div>

        {/* Mobile hamburger */}
        <button
          className="md:hidden ml-auto p-2 text-muted hover:text-fg transition-colors"
          onClick={() => setMobileOpen((s) => !s)}
          aria-label="Toggle menu"
        >
          <div className="space-y-1.5">
            <span className={cn("block w-5 h-0.5 bg-current transition-all", mobileOpen && "rotate-45 translate-y-2")} />
            <span className={cn("block w-5 h-0.5 bg-current transition-all", mobileOpen && "opacity-0")} />
            <span className={cn("block w-5 h-0.5 bg-current transition-all", mobileOpen && "-rotate-45 -translate-y-2")} />
          </div>
        </button>
      </div>

      {/* Mobile menu */}
      <AnimatePresence>
        {mobileOpen && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="md:hidden overflow-hidden border-t border-line bg-ink/95 backdrop-blur-md"
          >
            <div className="px-5 py-4 space-y-1">
              {LINKS.map((l) => {
                const active = pathname === l.href;
                return (
                  <Link
                    key={l.href}
                    href={l.href}
                    onClick={() => setMobileOpen(false)}
                    className={cn(
                      "block px-3 py-2.5 rounded-md text-sm uppercase tracking-wide transition-colors",
                      active ? "text-pitch bg-pitch/10" : "text-muted hover:text-fg hover:bg-elevated",
                    )}
                  >
                    {l.label}
                  </Link>
                );
              })}

              <div className="pt-3 border-t border-line space-y-1">
                {loading ? null : user ? (
                  <>
                    <div className="px-3 py-1 text-xs text-muted tnum">{user.email}</div>
                    {user.role === "admin" && (
                      <Link
                        href="/admin"
                        onClick={() => setMobileOpen(false)}
                        className="block px-3 py-2.5 rounded-md text-sm text-muted hover:text-fg uppercase tracking-wide"
                      >
                        Admin
                      </Link>
                    )}
                    <button
                      onClick={() => { logout(); setMobileOpen(false); }}
                      className="block w-full text-left px-3 py-2.5 rounded-md text-sm text-muted hover:text-signal uppercase tracking-wide transition-colors"
                    >
                      Sign out
                    </button>
                  </>
                ) : (
                  <>
                    <Link
                      href="/login"
                      onClick={() => setMobileOpen(false)}
                      className="block px-3 py-2.5 rounded-md text-sm text-muted hover:text-fg uppercase tracking-wide"
                    >
                      Log in
                    </Link>
                    <Link
                      href="/register"
                      onClick={() => setMobileOpen(false)}
                      className="block px-3 py-2.5 rounded-md text-sm bg-pitch text-ink font-semibold uppercase tracking-wide text-center"
                    >
                      Sign up
                    </Link>
                  </>
                )}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </header>
  );
}
