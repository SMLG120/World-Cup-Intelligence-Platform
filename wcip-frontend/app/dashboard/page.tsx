"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { useTeams } from "@/lib/queries";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { WinnerPredictionsSection } from "@/components/winner-predictions-section";

export default function DashboardPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const { data: teams, isLoading } = useTeams();

  useEffect(() => {
    if (!loading && !user) router.replace("/login");
  }, [user, loading, router]);

  const top = teams?.slice(0, 6) ?? [];

  return (
    <div className="space-y-8">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="kicker mb-2">Dashboard</p>
          <h1 className="display text-4xl">
            {user?.full_name ? `Hello, ${user.full_name.split(" ")[0]}` : "Overview"}
          </h1>
        </div>
        <Link href="/saved">
          <Button variant="outline" size="sm">View Saved Simulations</Button>
        </Link>
      </header>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Link href="/simulate">
          <Card className="hover:border-pitch transition-colors h-full">
            <CardBody>
              <div className="display text-xl text-pitch">Simulate a match</div>
              <p className="text-sm text-muted mt-1">W/D/L, xG, and reasoning for any fixture.</p>
            </CardBody>
          </Card>
        </Link>
        <Link href="/tournament">
          <Card className="hover:border-pitch transition-colors h-full">
            <CardBody>
              <div className="display text-xl text-pitch">Run a tournament</div>
              <p className="text-sm text-muted mt-1">Monte Carlo champion probabilities.</p>
            </CardBody>
          </Card>
        </Link>
        <Link href="/teams">
          <Card className="hover:border-pitch transition-colors h-full">
            <CardBody>
              <div className="display text-xl text-pitch">Browse teams</div>
              <p className="text-sm text-muted mt-1">Ratings and rankings for the 2026 field.</p>
            </CardBody>
          </Card>
        </Link>
        <Link href="/saved">
          <Card className="hover:border-pitch transition-colors h-full">
            <CardBody>
              <div className="display text-xl text-pitch">Saved simulations</div>
              <p className="text-sm text-muted mt-1">Open, duplicate, compare, or delete past runs.</p>
            </CardBody>
          </Card>
        </Link>
      </div>

      <WinnerPredictionsSection compact />

      <Card>
        <CardHeader className="flex justify-between items-baseline">
          <span className="kicker">Top contenders by Elo</span>
          <Link href="/teams" className="text-xs text-muted hover:text-pitch uppercase tracking-wide">
            All teams →
          </Link>
        </CardHeader>
        <CardBody>
          {isLoading ? (
            <div className="space-y-2">{Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-10" />)}</div>
          ) : (
            <div className="space-y-1.5">
              {top.map((t, i) => (
                <motion.div
                  key={t.id}
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.04 }}
                  className="flex items-center justify-between rounded-md border border-line/60 px-3 py-2"
                >
                  <div className="flex items-center gap-3">
                    <span className="tnum text-muted w-5">{i + 1}</span>
                    <span className="font-medium">{t.name}</span>
                    <Badge>{t.confederation}</Badge>
                  </div>
                  <span className="tnum text-pitch">{Math.round(t.elo)}</span>
                </motion.div>
              ))}
            </div>
          )}
        </CardBody>
      </Card>
    </div>
  );
}
