"use client";

import Link from "next/link";
import { BarChart3, Bot, Braces, Database, ListOrdered, Trophy } from "lucide-react";
import { motion } from "framer-motion";
import { Button } from "@/components/ui/button";
import { DataFreshnessCard } from "@/components/DataFreshnessCard";

const TOOLS = [
  {
    title: "Elo Ratings",
    icon: BarChart3,
    href: "/teams",
    copy: "Elo estimates national team strength and updates from match results, giving every matchup a live football-strength signal.",
  },
  {
    title: "FIFA Rankings",
    icon: ListOrdered,
    href: "/teams",
    copy: "FIFA rankings are used as one official team-strength signal alongside model and simulation inputs.",
  },
  {
    title: "Squad Data",
    icon: Database,
    href: "/teams",
    copy: "Squad and player features come from the FIFA squad PDF, including caps, goals, position, club, height, and coach data.",
  },
  {
    title: "Machine Learning",
    icon: Bot,
    href: "/models",
    copy: "Logistic Regression, Random Forest, XGBoost, LightGBM, and CatBoost generate machine-learning predictions.",
  },
  {
    title: "Statistical Simulation",
    icon: Braces,
    href: "/predict",
    copy: "Poisson score modeling and Monte Carlo simulations project match scores and tournament outcomes.",
  },
  {
    title: "Bracket Simulation",
    icon: Trophy,
    href: "/wc2026/bracket",
    copy: "The app simulates the group stage, Round of 32, Round of 16, quarter-finals, semi-finals, third-place match, final, and champion.",
  },
];

export default function LandingPage() {
  return (
    <div className="space-y-12 py-10 sm:py-16">
      <section className="grid gap-8 lg:grid-cols-[1.2fr_0.8fr] lg:items-end">
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          className="max-w-4xl"
        >
          <p className="kicker mb-4">World Cup prediction and bracket intelligence</p>
          <h1 className="display text-5xl text-fg sm:text-7xl">
            World Cup 2026 Intelligence Platform
          </h1>
          <p className="mt-6 max-w-3xl text-base leading-relaxed text-muted sm:text-lg">
            Predict the tournament with Elo ratings, FIFA rankings, squad data,
            machine learning, statistical simulations, and full bracket projections.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link href="/wc2026/bracket">
              <Button size="lg">
                <Trophy className="h-4 w-4" />
                Open Bracket
              </Button>
            </Link>
            <Link href="/predict">
              <Button size="lg" variant="outline">
                <BarChart3 className="h-4 w-4" />
                Run Prediction
              </Button>
            </Link>
            <Link href="/teams">
              <Button size="lg" variant="outline">
                <Database className="h-4 w-4" />
                Explore Teams
              </Button>
            </Link>
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.08 }}
        >
          <DataFreshnessCard />
        </motion.div>
      </section>

      <section>
        <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
          <div>
            <p className="kicker mb-2">Prediction tools</p>
            <h2 className="display text-3xl text-fg">How the platform makes projections</h2>
          </div>
          <Link href="/wc2026">
            <Button variant="outline" size="sm">Tournament overview</Button>
          </Link>
        </div>
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {TOOLS.map((tool, index) => {
            const Icon = tool.icon;
            return (
              <motion.div
                key={tool.title}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.12 + index * 0.04 }}
              >
                <Link
                  href={tool.href}
                  className="block h-full rounded-lg border border-line bg-surface/60 p-5 transition-colors hover:border-pitch/50 hover:bg-elevated/70"
                >
                  <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-md border border-line text-pitch">
                    <Icon className="h-5 w-5" aria-hidden />
                  </div>
                  <h3 className="display text-xl text-fg">{tool.title}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-muted">{tool.copy}</p>
                </Link>
              </motion.div>
            );
          })}
        </div>
      </section>
    </div>
  );
}
