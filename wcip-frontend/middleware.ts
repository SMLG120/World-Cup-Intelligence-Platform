import { NextResponse } from "next/server";

// Auth tokens live in localStorage (client-side), so route protection is
// enforced in the page components (redirect to /login when no user). This
// middleware adds baseline security headers to every response.
export function middleware() {
  const res = NextResponse.next();
  res.headers.set("X-Content-Type-Options", "nosniff");
  res.headers.set("X-Frame-Options", "DENY");
  res.headers.set("Referrer-Policy", "strict-origin-when-cross-origin");
  res.headers.set("Permissions-Policy", "camera=(), microphone=(), geolocation=()");
  return res;
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
