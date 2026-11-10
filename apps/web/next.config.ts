import type { NextConfig } from "next";

/*
 * Security headers for every page. The microphone is allowed only on the share pages, where a person can record a
 * voice note in quick capture (DEC-096); every other page keeps it, and the camera and location, switched off for
 * this site and anything it embeds. Kept in this file (not imported) so the config loads on its own.
 */
export type Header = { key: string; value: string };
export type HeaderRule = { source: string; headers: Header[] };

export const PERMISSIONS_POLICY = "camera=(), microphone=(), geolocation=(), interest-cohort=()";
export const PERMISSIONS_POLICY_SHARE = "camera=(), microphone=(self), geolocation=(), interest-cohort=()";

const base: Header[] = [
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "same-origin" },
];

/** Next.js applies every matching rule in order, and a later rule's value wins for the same key. */
export function headerRules(): HeaderRule[] {
  return [
    { source: "/:path*", headers: [...base, { key: "Permissions-Policy", value: PERMISSIONS_POLICY }] },
    { source: "/share/:path*", headers: [{ key: "Permissions-Policy", value: PERMISSIONS_POLICY_SHARE }] },
  ];
}

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
    return headerRules(); // the microphone only on /share (DEC-096)
  },
};

export default nextConfig;
