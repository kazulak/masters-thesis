#set text(size: 8pt)
#table(
  columns: (27mm, 45mm, 43mm, 45mm),
  inset: (x: 3pt, y: 4pt), stroke: none,
  table.header(repeat: true, table.hline(stroke: 0.6pt),
    text("Mechanism"), text("Scope"), text("Measured effect"), text("Disposition / limit"),
    table.hline(stroke: 0.4pt)),
  text("WRAM panel"), text("M=N=K=32; D1/T8 microcase"), text("1.15× kernel; 1.05× session-inclusive"), text("Microcase; whole-circuit benefit unmeasured"),
  text("Outer-K1"), text("specialization experiment"), text("0.986× inclusive; interval spans 1"), text("not adopted"),
  text("Residency"), text("Stress16 D1; bounded resident pair"), text("0.96× inclusive"), text("not adopted; bounded pair only"),
  text("Slicing"), text("Stress16 D2; plus static scheduling"), text("0.609× inclusive"), text("Mixed evidence; this case slower"),
  text("Slicing"), text("Stress16 D4; plus static scheduling"), text("0.781× inclusive"), text("Mixed evidence; this case slower"),
  text("Slicing"), text("EDC14 D4; plus static scheduling"), text("1.13× inclusive"), text("Mixed evidence; selected development confirmation"),
  text("Complex launch fusion"), text("Current six families; A2/A3 prepared-call medians"), text("GM 1.69×; range 1.52–2.02×; 6/6 faster"), text("Retained when admitted; four real products remain"),
  text("Static DAG"), text("Current six families; A3/A4 prepared-call medians"), text("GM 1.02×; range 0.835–1.13×; 4/6 faster"), text("Retained scheduling role; measured effect is mixed"),
  table.hline(stroke: 0.6pt),
)
#v(3pt)
#text("Notes: Ratios above 1 favor the mechanism. The first six rows are historical-reported summaries, not raw-recomputed observations. Their timing boundaries differ; residency uses the bounded pair’s subprocess wall boundary and slicing uses session-inclusive execution. Slicing also changes static scheduling, so its contribution is not isolated. The WRAM result is a scalar-versus-panel microcase, not a full-job speedup. Current adjacent contrasts use ratios of medians across six primary families (EDC17, others18), seven measured blocks per configuration, float32 and greedy paths. These heterogeneous effects must not be multiplied into a combined speedup.")
#text(" Historical source: ")#link("https://github.com/kazulak/masters-thesis/blob/504e614c5064ba020e5f47f6d05202568faadd69/thesis/implementation/docs/upmem_kernel_schedule_system_v1.md")[composition record at 504e614].
#text(" Current source: ")#link("https://github.com/kazulak/masters-thesis/blob/c7c6cac0b55bdff2f4c24b70397b36f89bedc45f/thesis/implementation/thesis_results/unified_final_v4/readout/A.csv")[A.csv at c7c6cac].
