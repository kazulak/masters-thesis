#set text(size: 8pt)
#table(
  columns: (20mm, 29mm, 31mm, 39mm, 41mm),
  align: (left, right, right, left, left), inset: (x: 3pt, y: 4pt), stroke: none,
  table.header(repeat: true, table.hline(stroke: 0.6pt),
    text("Family"), text("Largest admitted width"), text("First tested no-path width"), text("Search status"), text("Recorded reason"),
    table.hline(stroke: 0.4pt)),
  text("BB84"), text("24"), text("26"), text("no_selected_R_path"), text("no_admitted_candidate"),
  text("BV"), text("24"), text("26"), text("no_selected_R_path"), text("no_admitted_candidate"),
  text("EDC"), text("23"), text("25"), text("no_selected_R_path"), text("no_admitted_candidate"),
  text("HS"), text("24"), text("26"), text("no_selected_R_path"), text("no_admitted_candidate"),
  text("QRNG"), text("24"), text("26"), text("no_selected_R_path"), text("no_admitted_candidate"),
  text("XOR"), text("24"), text("26"), text("no_selected_R_path"), text("no_admitted_candidate"),
  table.hline(stroke: 0.6pt),
)
#v(3pt)
#text("Notes: Width means qubits. The frontier is empirical: the largest tested width with a selected R path and the first tested width with none, under the frozen candidate search and admission procedure. All six no-path records have zero admitted candidates. Untested intermediate widths are not resolved by this table. The recorded reason does not identify an MRAM capacity limit or prove that no feasible contraction path exists. These are search/admission outcomes, not failed physical executions.")
#text(" Source: ")#link("https://github.com/kazulak/masters-thesis/blob/c7c6cac0b55bdff2f4c24b70397b36f89bedc45f/thesis/implementation/thesis_results/unified_final_v4/path_records.json")[path_records.json at c7c6cac], checked against cold_cost.csv.
