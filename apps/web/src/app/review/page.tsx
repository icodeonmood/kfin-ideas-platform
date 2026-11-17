import { redirect } from "next/navigation";

/** The review desk moved to `/desk` (S-R1, P-REPO.screens route moves): old links, QR codes and emails land there. */
export default function ReviewMoved(): never {
  redirect("/desk");
}
