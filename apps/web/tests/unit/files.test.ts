import { afterEach, describe, expect, it, vi } from "vitest";

import { can, decide } from "@/lib/rbac";
import { BANNERS, switchesFor, UNGUARDED_WRITES } from "@/lib/killswitch-routes";

// The worker and the switch table are mocked: these tests are about what the web side adds (lane C, A-API.files).
const workerFetch = vi.fn();
vi.mock("@/server/worker", () => ({ workerFetch: (...args: unknown[]) => workerFetch(...args) }));
const states = vi.fn();
vi.mock("@/server/killswitch", () => ({
  switchStates: () => states(),
  isOn: (s: Map<string, string>, name: string) => s.get(name) === "on",
}));

const { addFile, addLink, hideFile, viewFile, viewHeaders, tooBig } = await import("@/server/files");

import type { CurrentUser } from "@/server/auth/current";

const ME_ID = "6f1c2a4e-1b2c-4d5e-8f90-123456789abc";
const me = { id: ME_ID } as unknown as CurrentUser;
const CONFIG = {
  limit_mb: 25,
  types: ["pdf", "png"],
  help_text: "PDF, images or a whole folder, up to 25 MB each.",
};
const json = (body: unknown, status = 200, headers: Record<string, string> = {}) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json", ...headers } });

afterEach(() => {
  workerFetch.mockReset();
  states.mockReset();
});

describe("A-API.files routes, policy and switches", () => {
  it("lists every files route, for everyone signed in; the worker decides each file", () => {
    for (const [method, path] of [
      ["GET", "/api/config/uploads"],
      ["POST", "/api/files"],
      ["POST", "/api/links"],
      ["GET", "/api/files/ATT-2026-000001"],
      ["GET", "/api/files/ATT-2026-000001/view"],
      ["POST", "/api/files/ATT-2026-000001/retry"],
      ["DELETE", "/api/files/ATT-2026-000001"],
      ["POST", "/api/files/ATT-2026-000001/hide"],
    ] as const) {
      expect(decide(new Set(["contributor"]), method, path).kind, `${method} ${path}`).toBe("allow");
    }
    expect(can(new Set(["contributor"]), "open_attachments")).toBe(true);
  });

  it("pauses uploads with attachments.upload and submissions, links with submissions, opening with attachments.open", () => {
    expect(switchesFor("POST", "/api/files").sort()).toEqual(["attachments.upload", "submissions"]);
    expect(switchesFor("POST", "/api/files/ATT-2026-000001/retry").sort()).toEqual([
      "attachments.upload",
      "submissions",
    ]);
    expect(switchesFor("POST", "/api/links")).toEqual(["submissions"]);
    expect(switchesFor("GET", "/api/files/ATT-2026-000001/view")).toEqual(["attachments.open"]);
    expect(switchesFor("GET", "/api/files/ATT-2026-000001")).toEqual([]);
    expect(switchesFor("GET", "/api/config/uploads")).toEqual([]);
    // Removing a file only protects someone; "Hide it for me" checks files.blackout in its handler.
    expect(switchesFor("DELETE", "/api/files/ATT-2026-000001")).toEqual([]);
    expect(UNGUARDED_WRITES.some((re) => re.test("/api/files/ATT-2026-000001"))).toBe(true);
    expect(UNGUARDED_WRITES.some((re) => re.test("/api/files/ATT-2026-000001/hide"))).toBe(true);
    expect(UNGUARDED_WRITES.some((re) => re.test("/api/files"))).toBe(false);
  });
});

describe("A-API.files upload (POST /api/files)", () => {
  const upload = (body: BodyInit, headers: Record<string, string> = {}) =>
    new Request("http://web.test/api/files", { method: "POST", body, headers });

  it("refuses a body over the configured limit from its length, with limit_mb, before reading it", async () => {
    workerFetch.mockResolvedValueOnce(json(CONFIG));
    const res = await addFile(me, upload("x", { "content-length": String(26 * 1024 * 1024) }));
    expect(res.status).toBe(413);
    expect(await res.json()).toEqual({
      error: { limit_mb: 25, code: "too_big", message: "Too big. Files can be up to 25 MB." },
    });
    expect(workerFetch).toHaveBeenCalledTimes(1); // the config only; nothing was sent on
    expect((await tooBig(15).json()).error.message).toBe("Too big. Files can be up to 15 MB.");
  });

  it("passes the file, the person and the one target on to the worker, and its FileItem back", async () => {
    workerFetch.mockResolvedValueOnce(json(CONFIG));
    workerFetch.mockResolvedValueOnce(json({ id: "ATT-2026-000009", state: "checking" }, 201));
    const form = new FormData();
    form.set(
      "file",
      new File([new Uint8Array([37, 80, 68, 70])], "branch notes.pdf", { type: "application/pdf" }),
    );
    form.set("answer_id", "0b7d9d2e-3c1f-4c55-9a51-2f7b0f6f1a10");
    form.set("user_id", "someone-else"); // never taken from the browser
    const req = new Request("http://web.test/api/files", { method: "POST", body: form });
    const sized = new Request(req, {
      headers: { ...Object.fromEntries(req.headers), "content-length": "400" },
    });
    const res = await addFile(me, sized);
    expect(res.status).toBe(201);
    expect(await res.json()).toEqual({ id: "ATT-2026-000009", state: "checking" });
    const [path, init] = workerFetch.mock.calls[1] as [string, RequestInit];
    expect(path).toBe("/internal/files");
    const sent = init.body as FormData;
    expect(sent.get("user_id")).toBe(ME_ID);
    expect(sent.get("answer_id")).toBe("0b7d9d2e-3c1f-4c55-9a51-2f7b0f6f1a10");
    expect(sent.get("idea_id")).toBeNull();
    expect((sent.get("file") as File).name).toBe("branch notes.pdf");
  });

  it("DEC-124, BLD-C216: for: conversation beside idea_id goes on to the worker, which alone decides; without it, nothing", async () => {
    const send = async (fields: Record<string, string>) => {
      workerFetch.mockResolvedValueOnce(json(CONFIG));
      workerFetch.mockResolvedValueOnce(json({ id: "ATT-2026-000011", state: "checking" }, 201));
      const form = new FormData();
      form.set(
        "file",
        new File([new Uint8Array([37, 80, 68, 70])], "notes.pdf", { type: "application/pdf" }),
      );
      for (const [k, v] of Object.entries(fields)) form.set(k, v);
      const req = new Request("http://web.test/api/files", { method: "POST", body: form });
      await addFile(
        me,
        new Request(req, { headers: { ...Object.fromEntries(req.headers), "content-length": "400" } }),
      );
      const sent = (workerFetch.mock.calls.at(-1) as [string, RequestInit])[1].body as FormData;
      workerFetch.mockReset();
      return sent;
    };
    const convo = await send({ idea_id: "IDEA-2026-001481", for: "conversation" });
    expect(convo.get("idea_id")).toBe("IDEA-2026-001481");
    expect(convo.get("for")).toBe("conversation");
    // Any other value is the worker's to refuse (422); an empty one is not sent at all.
    expect((await send({ idea_id: "IDEA-2026-001481", for: "chat" })).get("for")).toBe("chat");
    expect((await send({ idea_id: "IDEA-2026-001481", for: "" })).get("for")).toBeNull();
    expect((await send({ draft_id: "6f1c2a8e-3b4d-4e5f-8a9b-0c1d2e3f4a5b" })).get("for")).toBeNull();
  });

  it("answers a missing file, or a worker it cannot reach, in the pack's shape without echoing anything", async () => {
    workerFetch.mockResolvedValueOnce(json(CONFIG));
    const empty = await addFile(me, upload(new FormData(), { "content-length": "10" }));
    expect(empty.status).toBe(400);
    expect((await empty.json()).error).toEqual({
      field: "file",
      code: "file_required",
      message: "Didn’t upload. Your other files are fine.",
    });
    workerFetch.mockRejectedValueOnce(new Error("down"));
    const down = await addFile(me, upload("x", { "content-length": "1" }));
    expect(down.status).toBe(502);
    expect((await down.json()).error.code).toBe("files_unavailable");
  });

  it("links go on as JSON with the signed-in person, never fetched here", async () => {
    workerFetch.mockResolvedValueOnce(
      json({ id: "ATT-2026-000010", link_scope: "internal", state: "ok" }, 201),
    );
    const res = await addLink(me, {
      url: "kfintech.sharepoint.com/x",
      idea_id: "IDEA-2026-000001",
      user_id: "x",
    });
    expect(res.status).toBe(201);
    const [path, init] = workerFetch.mock.calls[0] as [string, RequestInit];
    expect(path).toBe("/internal/links");
    expect(JSON.parse(String(init.body))).toEqual({
      user_id: ME_ID,
      url: "kfintech.sharepoint.com/x",
      idea_id: "IDEA-2026-000001",
    });
  });
});

describe("A-API.files view and Hide it for me", () => {
  it("serves images and PDFs in place and everything else as a download, never sniffed or run", () => {
    const pdf = viewHeaders("application/pdf", "branch notes.pdf");
    expect(pdf["Content-Disposition"]).toBe(
      `inline; filename="branch notes.pdf"; filename*=UTF-8''branch%20notes.pdf`,
    );
    expect(pdf["X-Content-Type-Options"]).toBe("nosniff");
    expect(pdf["Cache-Control"]).toBe("private, no-store");
    const html = viewHeaders("text/html; charset=utf-8", "notes.html");
    expect(html["Content-Disposition"]).toMatch(/^attachment;/);
    expect(html["Content-Security-Policy"]).toBe("sandbox; default-src 'none'");
    expect(viewHeaders("image/png", "SMS.png")["Content-Security-Policy"]).toBe(
      "sandbox; default-src 'none'",
    );
    expect(viewHeaders("image/png", "SMS.png")["Content-Disposition"]).toMatch(/^inline;/);
    expect(viewHeaders("", 'x"y.zip')["Content-Disposition"]).toBe(
      `attachment; filename="x_y.zip"; filename*=UTF-8''x%22y.zip`,
    );
  });

  it("streams the worker's copy with its name, and passes its 403 and 404 on as they are", async () => {
    workerFetch.mockResolvedValueOnce(
      new Response(new Uint8Array([1, 2, 3]), {
        status: 200,
        headers: { "Content-Type": "image/png", "X-File-Name": "SMS%20for%20folio.png" },
      }),
    );
    const ok = await viewFile(me, "ATT-2026-000001");
    expect(ok.status).toBe(200);
    expect(new Uint8Array(await ok.arrayBuffer())).toEqual(new Uint8Array([1, 2, 3]));
    expect(ok.headers.get("content-disposition")).toContain("SMS%20for%20folio.png");
    expect(workerFetch.mock.calls[0]![0]).toBe(`/internal/files/ATT-2026-000001/content?user_id=${ME_ID}`);

    const refused = { error: { code: "not_available", message: "" } };
    workerFetch.mockResolvedValueOnce(json(refused, 403));
    const no = await viewFile(me, "ATT-2026-000001");
    expect(no.status).toBe(403);
    expect(await no.json()).toEqual(refused);
  });

  it("answers not_available with the switch's notice while files.blackout is off", async () => {
    states.mockResolvedValueOnce(new Map([["files.blackout", "off"]]));
    const off = await hideFile(me, "ATT-2026-000001");
    expect(off.status).toBe(503);
    expect(await off.json()).toEqual({
      error: { code: "not_available", message: BANNERS["files.blackout"] },
    });
    expect(workerFetch).not.toHaveBeenCalled();
    states.mockResolvedValueOnce(new Map([["files.blackout", "on"]]));
    workerFetch.mockResolvedValueOnce(json({ error: { code: "not_available", message: "" } }, 503));
    expect((await hideFile(me, "ATT-2026-000001")).status).toBe(503);
  });
});
