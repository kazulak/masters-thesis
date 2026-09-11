// Generated; edit synthesis code, not this file.
#text(size: 10pt, weight: "bold", "P6 offline search cost")
#v(5pt)
#{
  set text(size: 8pt)
  table(
    columns: (1fr,1fr,1fr,1fr,1fr,),
    inset: 4pt,
    stroke: 0.35pt,
    table.header(repeat: true, "Cell", "Method", "Proposals", "Eligible paths", "Search wall (s)"),
    "BB84 / 1dpu_t8", "F", "128", "128", "8.1153",
    "BB84 / 1dpu_t8", "U", "128", "128", "8.1369",
    "BB84 / 4dpu_t8", "F", "128", "128", "7.9246",
    "BB84 / 4dpu_t8", "U", "128", "128", "7.8890",
    "BV / 1dpu_t8", "F", "128", "109", "19.2481",
    "BV / 1dpu_t8", "U", "128", "109", "18.8847",
    "BV / 4dpu_t8", "F", "128", "114", "20.4016",
    "BV / 4dpu_t8", "U", "128", "115", "17.8061",
    "EDC / 1dpu_t8", "F", "128", "101", "11.4151",
    "EDC / 1dpu_t8", "U", "128", "103", "11.5482",
    "EDC / 4dpu_t8", "F", "128", "104", "16.1830",
    "EDC / 4dpu_t8", "U", "128", "107", "9.3349",
    "HS / 1dpu_t8", "F", "128", "112", "220.8628",
    "HS / 1dpu_t8", "U", "128", "114", "146.6173",
    "HS / 4dpu_t8", "F", "128", "112", "160.4915",
    "HS / 4dpu_t8", "U", "128", "114", "163.2594",
    "QRNG / 1dpu_t8", "F", "128", "128", "8.1469",
    "QRNG / 1dpu_t8", "U", "128", "128", "8.1538",
    "QRNG / 4dpu_t8", "F", "128", "128", "8.0248",
    "QRNG / 4dpu_t8", "U", "128", "128", "7.9588",
    "XOR / 1dpu_t8", "F", "128", "99", "11.0211",
    "XOR / 1dpu_t8", "U", "128", "95", "9.5858",
    "XOR / 4dpu_t8", "F", "128", "100", "9.9003",
    "XOR / 4dpu_t8", "U", "128", "97", "9.6461",
  )
}
#v(4pt)
#text(size: 8pt, "Offline search cost is separate from physical execution. One paired search-seed schedule, not repeated optimizer trials.")
