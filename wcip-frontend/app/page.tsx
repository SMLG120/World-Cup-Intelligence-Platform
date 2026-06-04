"use client";

import Link from "next/link";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { useAuth } from "@/lib/auth-context";
import { Button } from "@/components/ui/button";

export default function LandingPage() {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && user) router.replace("/dashboard");
  }, [user, loading, router]);

  return (
    <div className="py-16 sm:py-24">
      <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="kicker mb-4">
        Statistical simulation · educational analysis
      </motion.p>
      <motion.h1
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.05 }}
        className="display text-5xl sm:text-7xl max-w-3xl"
      >
        Predict the World Cup with <span className="text-pitch">Elo</span>, xG and{" "}
        <span className="text-signal">Monte Carlo</span>.
      </motion.h1>
      <motion.p
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.12 }}
        className="mt-6 max-w-xl text-muted leading-relaxed"
      >
        Simulate single matches or run tens of thousands of full tournaments.
        Adjust injuries, morale and form, then watch the champion probabilities
        shift. Every prediction explains its own reasoning.
      </motion.p>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.2 }}
        className="mt-8 flex flex-wrap gap-3"
      >
        <Link href="/register"><Button size="lg">Get started</Button></Link>
        <Link href="/simulate"><Button size="lg" variant="outline">Try a match</Button></Link>
      </motion.div>

      <div className="mt-20 grid gap-4 sm:grid-cols-3">
        {[
          { k: "Elo + Poisson", d: "Ratings drive expected goals and a full scoreline distribution." },
          { k: "Up to 50,000 sims", d: "Parallel Monte Carlo with confidence intervals on every stage." },
          { k: "Explainable", d: "Each prediction ranks the factors that produced it." },
        ].map((f, i) => (
          <motion.div
            key={f.k}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.25 + i * 0.06 }}
            className="rounded-lg border border-line p-5"
          >
            <div className="display text-lg text-pitch">{f.k}</div>
            <p className="text-sm text-muted mt-1">{f.d}</p>
          </motion.div>
        ))}
      </div>
    </div>
  );
}
