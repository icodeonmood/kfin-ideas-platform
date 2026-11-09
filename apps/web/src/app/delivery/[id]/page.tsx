import type { Metadata } from "next";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";

import { can } from "@/lib/rbac";
import { currentUser } from "@/server/auth/current";
import { deliveryDetail } from "@/server/delivery";

import { DeliveryView } from "./delivery-view";

export const metadata: Metadata = { title: "Delivery" };
export const dynamic = "force-dynamic";

/** One delivery (§4.8 to §4.11), for the people working on it: the pack, the steps and the results. */
export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const me = await currentUser();
  if (!me) redirect("/sign-in");
  if (!can(me.roles, "work_delivery")) redirect("/");
  const { id } = await params;
  let data;
  try {
    data = await deliveryDetail(me, id);
  } catch {
    return (
      <>
        <p className="notice">We can&apos;t load this delivery just now. Please try again in a minute.</p>
        <p>
          <Link href="/delivery">Back to Delivery</Link>
        </p>
      </>
    );
  }
  if (!data) notFound();
  return <DeliveryView d={data} />;
}
