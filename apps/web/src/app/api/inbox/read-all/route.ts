import { inboxPost } from "@/server/inbox-route";

/** POST /api/inbox/read-all: "Mark all read" (S-H5). Returns every tab's count. */
export const POST = () => inboxPost(null, "read-all");
