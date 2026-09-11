// Generated; edit synthesis code, not this file.
#text(size: 10pt, weight: "bold", "Software quantization characterization")
#v(5pt)
#{
  set text(size: 8pt)
  table(
    columns: (1fr,1fr,1fr,1fr,1fr,),
    inset: 4pt,
    stroke: 0.35pt,
    table.header(repeat: true, "Circuit", "Contractions", "L2 vs float32 (%)", "L2 vs complex128 (%)", "Logical compression"),
    "bell2", "3", "0", "1.711e-06", "2.3448",
    "stress4_l2", "29", "1.1378", "1.1378", "2.6628",
    "ghz18", "35", "0", "1.711e-06", "3.9936",
    "hs18_d1", "53", "0", "5.364e-05", "3.2626",
    "stress18_l2", "141", "8.3161", "8.3161", "3.9507",
  )
}
#v(4pt)
#text(size: 8pt, "These CSVs characterize software policy replay, not physical timing. Logical compression is not measured transfer reduction. The separate historical physical study established same-policy replay and workload-dependent error.")
