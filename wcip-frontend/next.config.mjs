/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    // Proxy /backend/* to the FastAPI service so the browser avoids CORS in dev.
    const base = process.env.BACKEND_INTERNAL_URL || "http://localhost:8000";
    return [{ source: "/backend/:path*", destination: `${base}/:path*` }];
  },
};
export default nextConfig;
