// Generated; edit synthesis code, not this file.
#text(size: 10pt, weight: "bold", "BB84 — job-to-state comparison")
#v(5pt)
#{
  set text(size: 8pt)
  table(
    columns: (1fr,1fr,1fr,1fr,1fr,1fr,),
    inset: 4pt,
    stroke: 0.35pt,
    table.header(repeat: true, "Total qubits", "UPMEM (s)", "QuEST P8 (s)", "QuEST P1 (s)", "NumPy P1 (s)", "P8 / UPMEM"),
    "8", "0.2699", "0.0141", "2.482e-04", "0.0061", "0.0521",
    "12", "0.3148", "0.0152", "4.465e-04", "0.0090", "0.0482",
    "16", "0.5347", "0.0152", "0.0037", "0.0153", "0.0285",
    "18", "0.6509", "0.0202", "0.0147", "0.0422", "0.0311",
    "20", "1.2803", "0.0531", "—", "—", "0.0415",
    "22", "3.6933", "0.1218", "—", "—", "0.0330",
    "24", "14.0164", "0.5252", "—", "—", "0.0375",
    "26", "—", "2.1579", "—", "—", "unsupported",
  )
}
#v(4pt)
#text(size: 8pt, "UPMEM D64/T24, greedy path; QuEST single precision. Dash in CPU anchor columns means not planned. Unsupported UPMEM endpoint is retained, not replaced by zero time.")
