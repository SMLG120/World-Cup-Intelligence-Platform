"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { Skeleton } from "@/components/ui/skeleton";

interface Props {
  children: React.ReactNode;
  admin?: boolean;
}

export function RequireAuth({ children, admin = false }: Props) {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !user) router.replace("/login");
  }, [user, loading, router]);

  if (loading || !user) {
    return (
      <div className="space-y-4 py-8">
        <Skeleton className="h-10 w-48" />
        <Skeleton className="h-64" />
      </div>
    );
  }

  if (admin && user.role !== "admin") {
    return (
      <div className="py-16 text-center">
        <h1 className="display text-3xl mb-2">Admins only</h1>
        <p className="text-muted text-sm">This area requires an administrator account.</p>
      </div>
    );
  }

  return <>{children}</>;
}
