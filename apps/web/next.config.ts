import type { NextConfig } from "next";

/*
 * Security headers for every page. The microphone is allowed for this site's own origin on every page, never for
 * another origin or anything the site embeds (DEC-128, amending DEC-096's /share-only rule): a Permissions-Policy is
 * fixed when the document loads, and the app's links and router.push are client-side routes that keep the first
 * page's document, so a person who lands on Home and goes on to Share a problem, or speaks into Home's own box
 * (WF-02) or an answer on S-R3, keeps the policy the first page had. The camera and location stay switched off for
 * this site and anything it embeds. Kept in this file (not imported) so the config loads on its own.
 */
export type Header = { key: string; value: string };
export type HeaderRule = { source: string; headers: Header[] };

export const PERMISSIONS_POLICY = "camera=(), microphone=(self), geolocation=(), interest-cohort=()";

const base: Header[] = [
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "same-origin" },
];

/** One rule for every path: Next.js would apply every matching rule in order, a later value winning for a key. */
export function headerRules(): HeaderRule[] {
  return [
    { source: "/:path*", headers: [...base, { key: "Permissions-Policy", value: PERMISSIONS_POLICY }] },
  ];
}

const nextConfig: NextConfig = {
  // `next dev` would otherwise write apps/web/AGENTS.md, an instructions file for coding agents, into every
  // checkout and worktree; this repo's agent guidance lives in CLAUDE.md (BLD-A169).
  agentRules: false,
  output: "standalone",
  poweredByHeader: false,
  reactStrictMode: true,
  serverExternalPackages: ["pg"],
  experimental: {
    // The proxy buffers request bodies and silently truncates past this size (default 10 MB). Files on the 1% Club
    // are up to 25 MB (rules/thresholds.md `files`, BLD-E007; the schema caps it there, BLD-C108), research files up
    // to 20 MB; uploads larger than the limit are refused by Content-Length first.
    proxyClientMaxBodySize: "26mb",
  },
  async headers() {
    return headerRules(); // the microphone for this site only, on every page (DEC-128)
  },
};

export default nextConfig;
