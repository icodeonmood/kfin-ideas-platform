import { PRIVACY_NOTICE } from "@/content/privacy-notice";
import { safeNext } from "@/server/auth/session";
import { privacyNoticeVersion } from "@/server/config";

import { AcceptNotice } from "./accept";

export const dynamic = "force-dynamic";

export default async function PrivacyNotice({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | undefined>>;
}) {
  const next = safeNext((await searchParams).next);
  const version = privacyNoticeVersion();
  if (version !== PRIVACY_NOTICE.version) {
    // §9.1: no launch without the notice. Never show a notice that is not the configured version.
    throw new Error("PRIVACY_NOTICE_VERSION has no matching notice text");
  }
  return (
    <article aria-labelledby="notice-title">
      <h1 id="notice-title">{PRIVACY_NOTICE.title}</h1>
      <p className="muted">
        Version {PRIVACY_NOTICE.version}
        {PRIVACY_NOTICE.draft ? " (draft, awaiting Legal sign-off)" : ""}
      </p>
      {PRIVACY_NOTICE.sections.map((section) => (
        <section key={section.heading}>
          <h2>{section.heading}</h2>
          {section.paragraphs.map((p) => (
            <p key={p}>{p}</p>
          ))}
        </section>
      ))}
      <AcceptNotice version={version} next={next} />
    </article>
  );
}
