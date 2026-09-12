#set text(size: 8pt)
#table(
  columns: (88mm, 24mm, 24mm, 24mm), align: (left, right, right, right),
  inset: (x: 3pt, y: 4pt), stroke: none,
  table.header(repeat: true, table.hline(stroke: 0.6pt),
    text("Attempt scope"), text("Planned"), text("Issued / successful"), text("Not issued"),
    table.hline(stroke: 0.4pt)),
  text("Qualification: physical UPMEM"), text("108"), text("108"), text("0"),
  text("Qualification: QuEST CPU"), text("32"), text("32"), text("0"),
  text("Qualification: UPMEM simulator"), text("108"), text("108"), text("0"),
  text("Calibration: physical UPMEM"), text("2,674"), text("2,674"), text("0"),
  text("Final: UPMEM float32"), text("312"), text("276"), text("36"),
  text("Final: UPMEM int8"), text("312"), text("276"), text("36"),
  text("Final: NumPy same-DAG"), text("312"), text("276"), text("36"),
  text("Final: QuEST P1"), text("312"), text("312"), text("0"),
  text("Final: QuEST P8"), text("312"), text("312"), text("0"),
  text("Final: all five routes"), text("1,560"), text("1,452"), text("108"),
  text("Physical total / allocated ceiling"), text("3,406"), text("3,334"), text("72"),
  table.hline(stroke: 0.6pt),
)
#v(6pt)
#table(
  columns: (63mm, 25mm, 72mm), inset: (x: 3pt, y: 4pt), stroke: none,
  table.header(repeat: true, table.hline(stroke: 0.6pt),
    text("Other accounting"), text("Count"), text("Scope"),
    table.hline(stroke: 0.4pt)),
  text("Calibration / final configurations"), text("434 / 260"), text("Case/resource/route combinations; includes unsupported final routes"),
  text("Avoided duplicate calibration slots"), text("714"), text("Shared analysis memberships reuse the same observations"),
  text("Final R-path searches"), text("52"), text("46 selected + 6 no selected path"),
  text("Final search proposals"), text("6,656"), text("Separate from physical execution attempts"),
  text("Tiny R qualification searches"), text("4"), text("Separate qualification searches"),
  text("Retained archive copies"), text("2"), text("Receipt records distinct archive-A and archive-B locations"),
  text("Files per archive copy"), text("8,288"), text("Frozen retention receipt; each copy has this count"),
  table.hline(stroke: 0.6pt),
)
#v(3pt)
#text("Notes: Issued counts include warmups; published measurement medians exclude them. All issued calibration and final slots succeeded. The three R-dependent routes each have 36 unsupported, unissued slots (six cases × six blocks); both QuEST routes issued all 312 slots. Physical issues are 108 qualification + 2,674 calibration + 552 final = 3,334 ≤ 3,406; the 72 remaining physical final slots were not issued. CPU and simulator qualification are separate from the physical ceiling. Final-route rows sum to the final total; subtotal rows are not additional attempts. Counts are reconciled with frozen manifests, qualification.csv, calibration/final ledgers and retention.json. Archive file counts are receipt statements; this table does not claim a fresh byte-for-byte re-verification of both retained copies.")
#text(" Source: ")#link("https://github.com/kazulak/masters-thesis/tree/c7c6cac0b55bdff2f4c24b70397b36f89bedc45f/thesis/implementation/thesis_results/unified_final_v4")[accounting, manifests, ledgers and retention at c7c6cac].
