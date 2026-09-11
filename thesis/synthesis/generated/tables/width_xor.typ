// Generated; edit synthesis code, not this file.
#text(size: 10pt, weight: "bold", "XOR — job-to-state comparison")
#v(5pt)
#{
  set text(size: 8pt)
  table(
    columns: (1fr,1fr,1fr,1fr,1fr,1fr,),
    inset: 4pt,
    stroke: 0.35pt,
    table.header(repeat: true, "Total qubits", "UPMEM (s)", "QuEST P8 (s)", "QuEST P1 (s)", "NumPy P1 (s)", "P8 / UPMEM"),
    "8", "0.3335", "0.0146", "3.190e-04", "0.0089", "0.0439",
    "12", "0.4768", "0.0144", "6.263e-04", "0.0138", "0.0303",
    "16", "0.7739", "0.0170", "0.0052", "0.0229", "0.0219",
    "18", "1.5956", "0.0189", "0.0218", "0.0554", "0.0118",
    "20", "4.5400", "0.0593", "—", "—", "0.0131",
    "22", "16.3340", "0.1669", "—", "—", "0.0102",
    "24", "65.8722", "0.7508", "—", "—", "0.0114",
    "26", "—", "3.2700", "—", "—", "unsupported",
  )
}
#v(4pt)
#text(size: 8pt, "UPMEM D64/T24, greedy path; QuEST single precision. Dash in CPU anchor columns means not planned. Unsupported UPMEM endpoint is retained, not replaced by zero time.")
