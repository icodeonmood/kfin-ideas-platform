/**
 * The 1% Club mark, "Spark" (docs/BRAND.md section 4, DEC-029 and DEC-052): the % sign with its slash drawn as a
 * rising spark. The zeros take the surrounding text colour (currentColor), so the same mark works on Zed and on
 * white; the spark is always Spark orange. Below 32 px tall the small cut is used: heavier zeros, no ember.
 *
 * Decorative by default (aria-hidden), because it always sits next to the visible name "1% Club". Pass a label
 * only where the mark stands alone.
 */
const SPARK = "#FF5B14";

export function SparkMark({
  height = 24,
  label,
  className,
}: {
  height?: number;
  label?: string;
  className?: string;
}) {
  const width = Math.round((height * 200) / 240);
  const small = height < 32;
  const a11y = label ? { role: "img", "aria-label": label } : { "aria-hidden": true as const };
  return (
    <svg
      className={className}
      width={width}
      height={height}
      viewBox="0 0 200 240"
      focusable="false"
      {...a11y}
    >
      {small ? (
        <>
          <circle cx="52" cy="58" r="32" fill="none" stroke="currentColor" strokeWidth="24" />
          <circle cx="148" cy="184" r="32" fill="none" stroke="currentColor" strokeWidth="24" />
          <polygon points="34,236 141,23.5 175,44.5" fill={SPARK} />
        </>
      ) : (
        <>
          <circle cx="52" cy="58" r="34" fill="none" stroke="currentColor" strokeWidth="12" />
          <circle cx="148" cy="184" r="34" fill="none" stroke="currentColor" strokeWidth="12" />
          <polygon points="34,236 146.9,27.2 169.1,40.8" fill={SPARK} />
          <circle cx="171.6" cy="11.8" r="7" fill={SPARK} />
        </>
      )}
    </svg>
  );
}
