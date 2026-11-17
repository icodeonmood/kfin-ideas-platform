/** S-H5 when the worker cannot be reached: the heading, and one plain line. */
export function InboxUnavailable() {
  return (
    <div className="ibx-down">
      <h1>Inbox</h1>
      <p role="status">We can&apos;t load your Inbox just now. Please try again in a minute.</p>
    </div>
  );
}
