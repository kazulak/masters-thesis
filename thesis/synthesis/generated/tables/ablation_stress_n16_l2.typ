// Generated; edit synthesis code, not this file.
#text(size: 10pt, weight: "bold", "STRESS 16 L2 — matched final executor")
#v(5pt)
#{
  set text(size: 8pt)
  table(
    columns: (1fr,1fr,1fr,1fr,1fr,1fr,),
    inset: 4pt,
    stroke: 0.35pt,
    table.header(repeat: true, "Arm", "D / T", "Schedule / fusion", "Prepared (s)", "Raw MAD (s)", "Job-to-state (s)"),
    "A0", "1 / 1", "serial / unfused", "7.7890", "0.0065", "7.9271",
    "A1", "1 / 8", "serial / unfused", "2.4854", "0.0380", "2.6314",
    "A2", "4 / 8", "serial / unfused", "2.3315", "0.0303", "2.4712",
    "A3", "4 / 8", "serial / fused", "1.2427", "0.0223", "1.3814",
    "A4", "4 / 8", "DAG / fused", "1.2458", "0.0111", "1.5048",
  )
}
#v(4pt)
#text(size: 8pt, "Seven measured blocks. All arms already use WRAM panels, packed waves, float32 and the same greedy path.")
