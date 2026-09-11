// Generated; edit synthesis code, not this file.
#text(size: 10pt, weight: "bold", "QRNG — job-to-state comparison")
#v(5pt)
#{
  set text(size: 8pt)
  table(
    columns: (1fr,1fr,1fr,1fr,1fr,1fr,),
    inset: 4pt,
    stroke: 0.35pt,
    table.header(repeat: true, "Total qubits", "UPMEM (s)", "QuEST P8 (s)", "QuEST P1 (s)", "NumPy P1 (s)", "P8 / UPMEM"),
    "8", "0.2271", "0.0146", "2.377e-04", "0.0061", "0.0644",
    "12", "0.2636", "0.0152", "4.320e-04", "0.0089", "0.0577",
    "16", "0.5236", "0.0145", "0.0037", "0.0139", "0.0276",
    "18", "0.7000", "0.0192", "0.0154", "0.0396", "0.0274",
    "20", "1.3033", "0.0538", "—", "—", "0.0413",
    "22", "3.7326", "0.1291", "—", "—", "0.0346",
    "24", "14.1256", "0.5255", "—", "—", "0.0372",
    "26", "—", "2.2321", "—", "—", "unsupported",
  )
}
#v(4pt)
#text(size: 8pt, "UPMEM D64/T24, greedy path; QuEST single precision. Dash in CPU anchor columns means not planned. Unsupported UPMEM endpoint is retained, not replaced by zero time.")
