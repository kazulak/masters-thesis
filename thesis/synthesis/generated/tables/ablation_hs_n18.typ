// Generated; edit synthesis code, not this file.
#text(size: 10pt, weight: "bold", "HS 18 — matched final executor")
#v(5pt)
#{
  set text(size: 8pt)
  table(
    columns: (1fr,1fr,1fr,1fr,1fr,1fr,),
    inset: 4pt,
    stroke: 0.35pt,
    table.header(repeat: true, "Arm", "D / T", "Schedule / fusion", "Prepared (s)", "Raw MAD (s)", "Job-to-state (s)"),
    "A0", "1 / 1", "serial / unfused", "4.0612", "0.0628", "4.2189",
    "A1", "1 / 8", "serial / unfused", "2.0691", "0.1378", "2.2246",
    "A2", "4 / 8", "serial / unfused", "2.3886", "0.0723", "2.5442",
    "A3", "4 / 8", "serial / fused", "1.2052", "0.0027", "1.3614",
    "A4", "4 / 8", "DAG / fused", "1.0732", "0.0057", "1.3639",
  )
}
#v(4pt)
#text(size: 8pt, "Seven measured blocks. All arms already use WRAM panels, packed waves, float32 and the same greedy path.")
