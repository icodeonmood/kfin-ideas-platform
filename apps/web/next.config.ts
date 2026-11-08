import type { NextConfig } from "next";

const securityHeaders = [
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "same-origin" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=(), interest-cohort=()" },
];

const nextConfig: NextConfig = {
  output: "standalone",
  poweredByHeader: false,
  reactStrictMode: true,
  serverExternalPackages: ["pg"],
  experimental: {
    // The proxy buffers request bodies and silently truncates past this size (default 10 MB). Research files
    // are up to 20 MB (rules/thresholds.md); uploads larger than that are refused by Content-Length first.
    proxyClientMaxBodySize: "21mb",
  },
  async headers() {
    return [{ source: "/:path*", headers: securityHeaders }];
  },
};

export default nextConfig;
