// Generated; edit synthesis code, not this file.
#text(size: 10pt, weight: "bold", "HS — job-to-state comparison")
#v(5pt)
#{
  set text(size: 8pt)
  table(
    columns: (1fr,1fr,1fr,1fr,1fr,1fr,),
    inset: 4pt,
    stroke: 0.35pt,
    table.header(repeat: true, "Total qubits", "UPMEM (s)", "QuEST P8 (s)", "QuEST P1 (s)", "NumPy P1 (s)", "P8 / UPMEM"),
    "8", "0.5978", "0.0171", "6.683e-04", "0.0242", "0.0286",
    "12", "0.8585", "0.0156", "0.0017", "0.0371", "0.0182",
    "16", "1.2453", "0.0194", "0.0190", "0.0527", "0.0156",
    "18", "1.5854", "0.0549", "0.0823", "0.0826", "0.0346",
    "20", "2.3432", "0.1018", "—", "—", "0.0435",
    "22", "5.0338", "0.4970", "—", "—", "0.0987",
    "24", "15.5465", "2.8025", "—", "—", "0.1803",
    "26", "—", "12.6520", "—", "—", "unsupported",
  )
}
#v(4pt)
#text(size: 8pt, "UPMEM D64/T24, greedy path; QuEST single precision. Dash in CPU anchor columns means not planned. Unsupported UPMEM endpoint is retained, not replaced by zero time.")
