/**
 * The 1% Club mark, "Spark" (F-ICONS.mark; docs/BRAND.md section 4, DEC-029 and DEC-052): the % sign with its slash
 * drawn as a rising spark. The pack draws one mark and this draws it at every size, 22px tall in the sidebar
 * as on Landing: rings r34 at stroke 14, the slash polygon 34,236 146.9,27.2 169.1,40.8 and the ember dot r9 at
 * 171.6,11.8 (F-ICONS.mark/6: "Do not redraw…"; BLD-D022 dropped the small cut). The rings take the surrounding
 * text colour (currentColor), so the same mark works on ink and on white (F-ICONS.mark/3); the slash and dot are
 * always spark (#F46835). The favicon (`app/icon*`) and the email marks keep their own drawing.
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
    </svg>
  );
}
