/**
 * The 1% Club mark, "Spark" (docs/BRAND.md section 4, DEC-029 and DEC-052): the % sign with its slash drawn as a
 * rising spark. The zeros take the surrounding text colour (currentColor), so the same mark works on Zed and on
 * white; the slash and dot are always spark (#F46835, F-ICONS.mark: rings stroke 14, dot r9). Below 32 px tall the small
 * cut is used: heavier zeros, no ember (kept until the product lead confirms dropping it).
 *
 * The parts carry classes (mark-zero, mark-spark, mark-ember) so a brand page can animate the spark rising; the
 * geometry and colours never change (BRAND.md section 4).
 *
 * Decorative by default (aria-hidden), because it always sits next to the visible name "1% Club". Pass a label
 * only where the mark stands alone.
 */
const SPARK = "#F46835";

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
          <circle
            className="mark-zero"
            cx="52"
            cy="58"
            r="34"
            fill="none"
            stroke="currentColor"
            strokeWidth="14"
          />
          <circle
            className="mark-zero"
            cx="148"
            cy="184"
            r="34"
            fill="none"
            stroke="currentColor"
            strokeWidth="14"
          />
          <polygon className="mark-spark" points="34,236 146.9,27.2 169.1,40.8" fill={SPARK} />
          <circle className="mark-ember" cx="171.6" cy="11.8" r="9" fill={SPARK} />
        </>
      )}
    </svg>
  );
}
