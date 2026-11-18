/**
 * The review side's countdowns (S-R1.rules/2, C-QCARD, S-R3) are the one rule every place uses (F-COPY.plurals/3,
 * BLD-A225): it lives in `lib/countdown.ts`, and the desk keeps importing it from here.
 */
export { countdown, countdownLabel, nextTickMs, officeDay } from "@/lib/countdown";
export type { Countdown, CountdownVariant } from "@/lib/countdown";
