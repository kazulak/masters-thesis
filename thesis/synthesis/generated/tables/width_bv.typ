// Generated; edit synthesis code, not this file.
#text(size: 10pt, weight: "bold", "BV — job-to-state comparison")
#v(5pt)
#{
  set text(size: 8pt)
  table(
    columns: (1fr,1fr,1fr,1fr,1fr,1fr,),
    inset: 4pt,
    stroke: 0.35pt,
    table.header(repeat: true, "Total qubits", "UPMEM (s)", "QuEST P8 (s)", "QuEST P1 (s)", "NumPy P1 (s)", "P8 / UPMEM"),
    "8", "0.3700", "0.0143", "3.543e-04", "0.0109", "0.0386",
    "12", "0.4877", "0.0162", "7.652e-04", "0.0162", "0.0332",
    "16", "0.7271", "0.0170", "0.0073", "0.0253", "0.0234",
    "18", "0.9515", "0.0211", "0.0310", "0.0507", "0.0222",
    "20", "1.5920", "0.0640", "—", "—", "0.0402",
    "22", "4.1395", "0.2199", "—", "—", "0.0531",
    "24", "14.3251", "1.0561", "—", "—", "0.0737",
    "26", "—", "4.6757", "—", "—", "unsupported",
  )
}
#v(4pt)
#text(size: 8pt, "UPMEM D64/T24, greedy path; QuEST single precision. Dash in CPU anchor columns means not planned. Unsupported UPMEM endpoint is retained, not replaced by zero time.")
