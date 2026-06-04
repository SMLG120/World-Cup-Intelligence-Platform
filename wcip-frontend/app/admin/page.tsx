"use client";

import { motion } from "framer-motion";
import { useAdminAnalytics } from "@/lib/queries";
import { RequireAuth } from "@/components/require-auth";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

function Metric({ label, value, accent }: { label: string; value: number; accent?: boolean }) {
  return (
    <Card>
      <CardBody>
        <div className="kicker">{label}</div>
        <div className={`tnum text-4xl mt-1 ${accent ? "text-pitch" : "text-fg"}`}>
          {value.toLocaleString()}
        </div>
      </CardBody>
    </Card>
  );
}

const STATUS_COLOR: Record<string, string> = {
  completed: "bg-pitch", pending: "bg-sky", running: "bg-sky", failed: "bg-signal",
};

function AdminInner() {
  const { data, isLoading, isError } = useAdminAnalytics();

  return (
    <div className="space-y-8">
      <header>
        <p className="kicker mb-2">Operations</p>
        <h1 className="display text-4xl">Admin analytics</h1>
      </header>

      {isLoading ? (
        <div className="grid gap-4 sm:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-28" />)}
        </div>
      ) : isError || !data ? (
        <p className="text-signal text-sm">Couldn&apos;t load analytics.</p>
      ) : (
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-3">
            <Metric label="Registered users" value={data.users} accent />
            <Metric label="Total simulations" value={data.simulations} />
            <Metric
              label="Completed"
              value={data.simulations_by_status?.completed ?? 0}
            />
          </div>

          <Card>
            <CardHeader><span className="kicker">Simulations by status</span></CardHeader>
            <CardBody className="space-y-3">
              {Object.keys(data.simulations_by_status ?? {}).length === 0 ? (
                <p className="text-muted text-sm">No simulations recorded yet.</p>
              ) : (
                Object.entries(data.simulations_by_status).map(([status, count]) => {
                  const total = data.simulations || 1;
                  return (
                    <div key={status}>
                      <div className="flex justify-between text-xs mb-1">
                        <span className="uppercase tracking-wide text-muted">{status}</span>
                        <span className="tnum">{count}</span>
                      </div>
                      <div className="h-2 rounded-full bg-line overflow-hidden">
                        <motion.div
                          initial={{ width: 0 }}
                          animate={{ width: `${(count / total) * 100}%` }}
                          transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
                          className={`h-full ${STATUS_COLOR[status] ?? "bg-muted"}`}
                        />
                      </div>
                    </div>
                  );
                })
              )}
            </CardBody>
          </Card>
        </motion.div>
      )}
    </div>
  );
}

export default function AdminPage() {
  return <RequireAuth admin><AdminInner /></RequireAuth>;
}
