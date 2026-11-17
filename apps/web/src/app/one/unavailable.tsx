import { Empty } from "@/components/ui/empty";

import { LOAD_FAILED } from "./rules";

/**
 * S-ONE's error state (BLD-E041): the dashboard could not be read. Says so in its place, with one way on: "Try
 * again" reads the page afresh (F-COPY.states/3). Plain links, so it needs no script.
 */
export function OneUnavailable() {
  return (
    <div className="on">
      <nav aria-label="Breadcrumb" className="on-crumb">
        <ol role="list">
          <li>
            <a href="/my-ideas">My ideas</a>
          </li>
          <li aria-current="page">
            <span aria-hidden="true" className="on-sep">
              /
            </span>
            Your One dashboard
          </li>
        </ol>
      </nav>
      <h1 className="d1 on-h1-quiet">Your One dashboard</h1>
      <div className="card on-fail">
        <Empty
          title={LOAD_FAILED}
          action={
            <a href="/one" className="btn btn-secondary">
              Try again
            </a>
          }
        />
      </div>
    </div>
  );
}
