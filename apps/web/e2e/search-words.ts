/**
 * DEC-110 checks shared by the S-07, S-R1 and S-H5 tests: a search's words are in no request URL (navigations and
 * fetches alike, raw or encoded) and in no address, and nothing new is kept in localStorage or a cookie. The words
 * live only in the tab's own page memory of the history entry.
 */
import type { Page } from "@playwright/test";

/** Every URL the page asks for from now on, navigations and fetches alike. */
export function watchRequestUrls(page: Page): string[] {
  const urls: string[] = [];
  page.on("request", (request) => urls.push(request.url()));
  return urls;
}

/** Whether a URL holds the words: as typed, percent-encoded, form-encoded or decoded, in any case. */
export function carrying(words: string): (url: string) => boolean {
  const forms = [words, encodeURIComponent(words), encodeURIComponent(words).replace(/%20/g, "+")].map((w) =>
    w.toLowerCase(),
  );
  return (url: string) => {
    let decoded = url;
    try {
      decoded = decodeURIComponent(url.replace(/\+/g, " "));
    } catch {
      // a URL that is not valid percent-encoding is checked as it is
    }
    const raw = url.toLowerCase();
    return forms.some((f) => raw.includes(f)) || decoded.toLowerCase().includes(words.toLowerCase());
  };
}

/** The names of what this site keeps in localStorage and in cookies, to compare before and after a search. */
export async function storageNames(page: Page): Promise<{ local: string[]; cookies: string[] }> {
  const local = await page.evaluate(() => Object.keys(window.localStorage).sort());
  const cookies = (await page.context().cookies()).map((c) => c.name).sort();
  return { local, cookies };
}

/** Whether any localStorage value or cookie value holds the words. */
export async function storageCarries(page: Page, words: string): Promise<boolean> {
  const has = carrying(words);
  const local = await page.evaluate(() => Object.values(window.localStorage));
  const cookies = (await page.context().cookies()).map((c) => c.value);
  return [...local, ...cookies].some((v) => has(v));
}
