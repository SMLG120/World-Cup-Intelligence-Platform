import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  turbopack: {
    root: __dirname,
  },
  async rewrites() {
    // Proxy /backend/* to the FastAPI service so the browser avoids CORS in dev.
    const base = process.env.BACKEND_INTERNAL_URL || "http://localhost:8000";
    return [{ source: "/backend/:path*", destination: `${base}/:path*` }];
  },
};
export default nextConfig;
