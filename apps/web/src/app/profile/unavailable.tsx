import { Empty } from "@/components/ui/empty";

import { LOAD_FAILED, TRY_AGAIN } from "./rules";

/**
 * S-H6's error state (BLD-E043): the profile could not be read. Says so in its place, with one way on: "Try again"
 * reads the page afresh (F-COPY.states/3). A plain link, so it needs no script.
 */
export function ProfileUnavailable() {
  return (
    <div className="pf">
      <h1 className="pf-t">Profile and settings</h1>
      <div className="pf-card pf-fail">
        <Empty
          title={LOAD_FAILED}
          action={
            <a href="/profile" className="btn btn-secondary">
              {TRY_AGAIN}
            </a>
          }
        />
      </div>
    </div>
  );
}
