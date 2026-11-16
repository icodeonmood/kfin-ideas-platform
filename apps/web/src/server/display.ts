import { officeOrder, type OfficeData } from "@/lib/display";

import { publicOnes } from "./ones";

/**
 * The office screen's data (S-OFFICE, L-DISPLAY.office, A-API `GET /display/office`): the Ones everyone may see,
 * with their briefs and a headline figure, in induction order. The worker applies the `ones.public` switch, the
 * name consent and the public measures, so this screen never shows more than the Wall does.
 */
export async function officeScreen(): Promise<OfficeData> {
  const data = await publicOnes();
  if (data.paused) return { paused: true, ones: [] };
  return { paused: false, ones: officeOrder(data.ones) };
}
