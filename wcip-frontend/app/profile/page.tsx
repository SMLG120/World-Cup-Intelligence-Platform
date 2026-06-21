"use client";

import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { useAuth } from "@/lib/auth-context";
import { useSimulations } from "@/lib/queries";
import { RequireAuth } from "@/components/require-auth";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between py-2.5 border-b border-line/60">
      <span className="kicker self-center">{label}</span>
      <span className="text-sm text-fg">{value}</span>
    </div>
  );
}

function stableDate(value: string) {
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toISOString().slice(0, 10);
}

function ProfileInner() {
  const { user, logout } = useAuth();
  const router = useRouter();
  const { data } = useSimulations(1, Boolean(user));

  if (!user) return null;

  const signOut = () => { logout(); router.push("/"); };

  return (
    <div className="max-w-2xl space-y-6">
      <header>
        <p className="kicker mb-2">Account</p>
        <h1 className="display text-4xl">{user.full_name ?? "Profile"}</h1>
      </header>

      <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
        <Card>
          <CardHeader className="flex items-center justify-between">
            <span className="kicker">Details</span>
            {user.role === "admin" && <Badge className="text-pitch border-pitch/40">admin</Badge>}
          </CardHeader>
          <CardBody>
            <Row label="Email" value={user.email} />
            <Row label="Name" value={user.full_name ?? "—"} />
            <Row label="Role" value={user.role} />
            <Row label="Saved simulations" value={String(data?.total ?? 0)} />
            <Row label="Member since" value={stableDate(user.created_at)} />
          </CardBody>
        </Card>
      </motion.div>

      <div className="flex gap-3">
        <Button variant="danger" onClick={signOut}>Sign out</Button>
      </div>

      <p className="text-xs text-muted">
        Profile editing and OAuth account linking are the next backend additions
        — this view reflects the data the API exposes today.
      </p>
    </div>
  );
}

export default function ProfilePage() {
  return <RequireAuth><ProfileInner /></RequireAuth>;
}
