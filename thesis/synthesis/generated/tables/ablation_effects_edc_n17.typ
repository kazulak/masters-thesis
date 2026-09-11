// Generated; edit synthesis code, not this file.
#text(size: 10pt, weight: "bold", "EDC 17 — isolated transitions")
#v(5pt)
#{
  set text(size: 8pt)
  table(
    columns: (1fr,1fr,1fr,1fr,),
    inset: 4pt,
    stroke: 0.35pt,
    table.header(repeat: true, "Comparison", "Time ratio", "Descriptive 95% interval", "Time reduction (%)"),
    "tasklets", "4.3430", "[4.2725, 4.4317]", "76.97",
    "dpus", "1.6194", "[1.5921, 1.6544]", "38.25",
    "complex_fusion", "1.5430", "[1.5301, 1.5536]", "35.19",
    "dag_concurrency", "0.8280", "[0.8199, 0.8412]", "-20.77",
    "matched_combined_executor", "8.9854", "[8.9719, 9.0772]", "88.87",
  )
}
#v(4pt)
#text(size: 8pt, "Ratio <1 and negative time reduction are regressions. Combined A0/A4 is a directly observed contrast.")
