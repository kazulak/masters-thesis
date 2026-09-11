// Generated; edit synthesis code, not this file.
#text(size: 10pt, weight: "bold", "STRESS 16 L2 — isolated transitions")
#v(5pt)
#{
  set text(size: 8pt)
  table(
    columns: (1fr,1fr,1fr,1fr,),
    inset: 4pt,
    stroke: 0.35pt,
    table.header(repeat: true, "Comparison", "Time ratio", "Descriptive 95% interval", "Time reduction (%)"),
    "tasklets", "3.1339", "[3.0867, 3.2298]", "68.09",
    "dpus", "1.0660", "[1.0358, 1.1915]", "6.19",
    "complex_fusion", "1.8762", "[1.7571, 1.8928]", "46.70",
    "dag_concurrency", "0.9975", "[0.9700, 1.0172]", "-0.25",
    "matched_combined_executor", "6.2520", "[6.1966, 6.3208]", "84.01",
  )
}
#v(4pt)
#text(size: 8pt, "Ratio <1 and negative time reduction are regressions. Combined A0/A4 is a directly observed contrast.")
