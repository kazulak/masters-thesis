// Generated; edit synthesis code, not this file.
#text(size: 10pt, weight: "bold", "EDC 17 — matched final executor")
#v(5pt)
#{
  set text(size: 8pt)
  table(
    columns: (1fr,1fr,1fr,1fr,1fr,1fr,),
    inset: 4pt,
    stroke: 0.35pt,
    table.header(repeat: true, "Arm", "D / T", "Schedule / fusion", "Prepared (s)", "Raw MAD (s)", "Job-to-state (s)"),
    "A0", "1 / 1", "serial / unfused", "17.0433", "0.0403", "17.1184",
    "A1", "1 / 8", "serial / unfused", "3.9243", "0.0579", "3.9989",
    "A2", "4 / 8", "serial / unfused", "2.4234", "0.0071", "2.4977",
    "A3", "4 / 8", "serial / fused", "1.5705", "0.0074", "1.6451",
    "A4", "4 / 8", "DAG / fused", "1.8968", "0.0148", "2.0384",
  )
}
#v(4pt)
#text(size: 8pt, "Seven measured blocks. All arms already use WRAM panels, packed waves, float32 and the same greedy path.")
