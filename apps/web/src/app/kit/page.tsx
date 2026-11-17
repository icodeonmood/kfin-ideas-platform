import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { isProductionLike } from "@/server/config";

import { KitDemo } from "./kit-demo";

export const metadata: Metadata = { title: "Components" };
export const dynamic = "force-dynamic";

/**
 * The component kit (lane D): every shared component in its states, with synthetic content, so e2e and axe cover
 * them before screens use them and other lanes can see them working. Dev and test only; it does not exist in UAT or
 * production.
 */
export default function Kit() {
  if (isProductionLike()) notFound();
  return <KitDemo />;
}
