// Generated; edit synthesis code, not this file.
#text(size: 10pt, weight: "bold", "Completed investigations and negative findings")
#v(5pt)
#{
  set text(size: 8pt)
  table(
    columns: (1fr,1fr,1fr,),
    inset: 4pt,
    stroke: 0.35pt,
    table.header(repeat: true, "Investigation", "Recorded outcome", "Disposition / qualification"),
    "semantic pipeline", "Exact complete pre-measurement statevector via circuit/TN/DAG", "retained; reported historical finding; not raw-data recomputation",
    "gemm lowering", "Binary contraction to B,M,K,N geometry", "retained; reported historical finding; not raw-data recomputation",
    "complex lanes", "RR-II + i(RI+IR)", "retained; reported historical finding; not raw-data recomputation",
    "sequential", "Greedy D1/T1 WRAM-panel; same-DAG CPU reference", "baseline; reported historical finding; not raw-data recomputation",
    "scalar panel", "approximately 1.154x kernel; 1.0452x inclusive", "microcase; reported historical finding; not raw-data recomputation",
    "tasklets", "Original T1->T8 6.77x kernel, 3.27x total", "retained; reported historical finding; not raw-data recomputation",
    "dpus", "Original D1->D4 T8 3.67x kernel, 1.51x total", "retained; reported historical finding; not raw-data recomputation",
    "resource general", "T1..24 builds; non-power-of-two routes qualified", "retained; reported historical finding; not raw-data recomputation",
    "circuit sensitivity", "Host request-wave overhead across Stress18, HS18, GHZ18", "finding; reported historical finding; not raw-data recomputation",
    "host attribution", "Separated request construction, staging, native and transfer work", "finding; reported historical finding; not raw-data recomputation",
    "payload initial", "1.9..6.8 percent improvement; failed specified >=10 percent gate", "rejected; unverified context transcription; do not use as a new measured numeric claim",
    "templates", "84..87 percent record-construction reduction", "adopted; unverified context transcription; do not use as a new measured numeric claim",
    "native constructor", "C prepared-stage slower without eliminating boundary work", "rejected; reported historical finding; not raw-data recomputation",
    "packed envelope probe", "2.75..9.20x host-only synthetic probe", "prototype; unverified context transcription; do not use as a new measured numeric claim",
    "packed transport", "5.90..30.65 percent session-inclusive time reduction", "adopted; reported historical finding; not raw-data recomputation",
    "prepared waves", "Persistent host plus packed-wave ABI-v5", "retained; reported historical finding; not raw-data recomputation",
    "complex fusion", "1.9034x inclusive fresh development confirmation", "retained when admitted; reported historical finding; not raw-data recomputation",
    "outer k1", "0.985619x inclusive; interval spans one", "not adopted; reported historical finding; not raw-data recomputation",
    "dag", "1.214213x six-cell inclusive; 1.431726x selected confirmation", "retained; reported historical finding; not raw-data recomputation",
    "residency", "Stress16 D1 0.959855x inclusive", "not adopted; reported historical finding; not raw-data recomputation",
    "slicing", "Stress16 D2 .608676x; D4 .780553x; EDC14 D4 1.125244x", "mixed; reported historical finding; not raw-data recomputation",
    "composed tasklets", "Stress16 D1T1->D1T16 4.501040x inclusive", "accepted; reported historical finding; not raw-data recomputation",
    "composed dpus", "Stress16 D1T8->D4T8 1.530679x inclusive", "accepted; reported historical finding; not raw-data recomputation",
    "int8", "180 accepted attempts; same-policy CPU replay matched", "optional; reported historical finding; not raw-data recomputation",
    "int8 error", "Stress18 relative L2 about 8.316 percent", "negative quality result; reported historical finding; not raw-data recomputation",
    "int8 topology", "HS18/Stress18 best tested D4 f32 -> D2 int8", "interaction; reported historical finding; not raw-data recomputation",
    "pilot path", "Training 2.2314x; EDC16 2.2976x; BV18 .9963x", "noncanonical; unverified context transcription; do not use as a new measured numeric claim",
    "p6 cost", "5-term launch-aware score; final integer weights [1,2,1,1,5]", "accepted; reported historical finding; not raw-data recomputation",
    "p6 reranking", "F/R 1.039030x overall inclusive", "useful; reported historical finding; not raw-data recomputation",
    "p6 generation", "R/U 1.001343x CI [.994836,1.008509]; same path 8/12", "unresolved added benefit; reported historical finding; not raw-data recomputation",
    "p6 regression", "HS18 D4 G/U .687613x; U about 45.43 percent more time", "negative result; reported historical finding; not raw-data recomputation",
    "cpu context", "Historical NumPy/TN/QuEST roles distinct; new W adds matched CPU data", "new evidence required; reported historical finding; not raw-data recomputation",
  )
}
#v(4pt)
#text(size: 8pt, "Historical narratives are not recomputed raw observations. Chat-context transcriptions are explicitly unverified numeric context. Do not multiply these heterogeneous studies into a cumulative speedup.")
