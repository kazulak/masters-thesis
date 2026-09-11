// Generated; edit synthesis code, not this file.
#text(size: 10pt, weight: "bold", "EDC — job-to-state comparison")
#v(5pt)
#{
  set text(size: 8pt)
  table(
    columns: (1fr,1fr,1fr,1fr,1fr,1fr,),
    inset: 4pt,
    stroke: 0.35pt,
    table.header(repeat: true, "Total qubits", "UPMEM (s)", "QuEST P8 (s)", "QuEST P1 (s)", "NumPy P1 (s)", "P8 / UPMEM"),
    "7", "0.3912", "3.704e-04", "3.058e-04", "0.0080", "0.0009",
    "11", "0.4625", "0.0146", "4.519e-04", "0.0202", "0.0315",
    "15", "0.6456", "0.0164", "0.0020", "0.0272", "0.0253",
    "17", "1.5043", "0.0155", "0.0077", "0.0839", "0.0103",
    "19", "1.5132", "0.0379", "—", "—", "0.0251",
    "21", "2.8006", "0.0702", "—", "—", "0.0251",
    "23", "10.4968", "0.3026", "—", "—", "0.0288",
    "25", "—", "1.3248", "—", "—", "unsupported",
  )
}
#v(4pt)
#text(size: 8pt, "UPMEM D64/T24, greedy path; QuEST single precision. Dash in CPU anchor columns means not planned. Unsupported UPMEM endpoint is retained, not replaced by zero time.")
