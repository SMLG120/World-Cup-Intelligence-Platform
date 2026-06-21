"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import { ApiError } from "@/lib/api";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/input";

function loginErrorMessage(err: unknown) {
  if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
    return "That email and password did not match an active account.";
  }
  if (err instanceof ApiError && err.status === 422) {
    return "Enter a valid email and password.";
  }
  return "We could not sign you in. Check that the backend is running and try again.";
}

export default function LoginPage() {
  const { login } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await login(email, password);
      router.push("/dashboard");
    } catch (err) {
      setError(loginErrorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="max-w-md mx-auto py-12">
      <h1 className="display text-3xl mb-1">Welcome back</h1>
      <p className="text-muted text-sm mb-6">Log in to save and share simulations.</p>
      <Card>
        <CardHeader><span className="kicker">Sign in</span></CardHeader>
        <CardBody>
          <form onSubmit={submit} className="space-y-4">
            <div>
              <Label htmlFor="email">Email</Label>
              <Input id="email" type="email" required value={email}
                onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" />
            </div>
            <div>
              <Label htmlFor="password">Password</Label>
              <Input id="password" type="password" required value={password}
                onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" />
            </div>
            {error && <p className="text-signal text-sm">{error}</p>}
            <Button type="submit" disabled={busy} className="w-full">
              {busy ? "Signing in…" : "Sign in"}
            </Button>
          </form>
        </CardBody>
      </Card>
      <p className="text-sm text-muted mt-4 text-center">
        No account?{" "}
        <Link href="/register" className="text-pitch hover:underline">Create one</Link>
      </p>
    </div>
  );
}
