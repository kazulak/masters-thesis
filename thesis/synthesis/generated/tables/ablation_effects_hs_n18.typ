// Generated; edit synthesis code, not this file.
#text(size: 10pt, weight: "bold", "HS 18 — isolated transitions")
#v(5pt)
#{
  set text(size: 8pt)
  table(
    columns: (1fr,1fr,1fr,1fr,),
    inset: 4pt,
    stroke: 0.35pt,
    table.header(repeat: true, "Comparison", "Time ratio", "Descriptive 95% interval", "Time reduction (%)"),
    "tasklets", "1.9628", "[1.8737, 2.1876]", "49.05",
    "dpus", "0.8662", "[0.7527, 0.9172]", "-15.44",
    "complex_fusion", "1.9819", "[1.9526, 2.0419]", "49.54",
    "dag_concurrency", "1.1230", "[1.1188, 1.1465]", "10.95",
    "matched_combined_executor", "3.7843", "[3.7739, 3.8814]", "73.57",
  )
}
#v(4pt)
#text(size: 8pt, "Ratio <1 and negative time reduction are regressions. Combined A0/A4 is a directly observed contrast.")
