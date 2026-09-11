// Evaluation-only gate-stream bridge to pinned QuEST. No simulator algorithm here.
#include "quest/include/quest.h"
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <exception>
#include <omp.h>
#include <type_traits>

static double seconds() {
    return std::chrono::duration<double>(
        std::chrono::steady_clock::now().time_since_epoch()).count();
}
extern "C" int eval_precision_bytes() { return sizeof(qreal); }

// Opcodes: 0 H, 1 X, 2 RY, 3 RZ, 4 CX. 'out' is interleaved qreal complex.
// t = environment/allocation, gate evolution, output copy, teardown (seconds).
// deployment = actual multithreading, GPU, distributed flags.
extern "C" int eval_circuit(int n, int ng, const int *op, const int *a,
                            const int *b, const double *angle, int threads,
                            void *out, std::uint64_t out_bytes, double *t,
                            int *deployment) {
    static_assert(sizeof(qcomp) == 2*sizeof(qreal), "Unexpected complex layout");
    static_assert(std::is_trivially_copyable<qcomp>::value, "Complex not copyable");
    if (n < 1 || n > 28 || ng < 0 || ng > 100000 || threads < 1 ||
        !op || !a || !b || !angle || !out || !t || !deployment) return 2;
    auto count = std::uint64_t(1) << n;
    if (out_bytes != count*sizeof(qcomp)) return 3;
    for (int i=0; i<ng; ++i) {
        if (op[i] < 0 || op[i] > 4 || a[i] < 0 || a[i] >= n ||
            !std::isfinite(angle[i])) return 4;
        if (op[i] == 4 && (b[i] < 0 || b[i] >= n || a[i] == b[i])) return 4;
    }
    if (isQuESTEnvInit()) return 5;  // one independent lifecycle per attempt
    omp_set_dynamic(0);
    omp_set_num_threads(threads);
    bool env = false, allocated = false;
    Qureg q{};
    try {
        double s=seconds();
        initCustomQuESTEnv(0, 0, threads > 1 ? 1 : 0);
        env=true;
        q=createQureg(n);  // native QuEST automatic size-dependent CPU threading
        allocated=true;
        deployment[0]=q.isMultithreaded;
        deployment[1]=q.isGpuAccelerated;
        deployment[2]=q.isDistributed;
        if (q.isGpuAccelerated || q.isDistributed || q.isDensityMatrix ||
            q.numAmps != (qindex) count || q.cpuAmps == nullptr) {
            destroyQureg(q); finalizeQuESTEnv(); return 6;
        }
        t[0]=seconds()-s;
        s=seconds();
        for (int i=0; i<ng; ++i) {
            switch (op[i]) {
                case 0: applyHadamard(q,a[i]); break;
                case 1: applyPauliX(q,a[i]); break;
                case 2: applyRotateY(q,a[i],(qreal)angle[i]); break;
                case 3: applyRotateZ(q,a[i],(qreal)angle[i]); break;
                case 4: applyControlledPauliX(q,a[i],b[i]); break;
            }
        }
        t[1]=seconds()-s;
        s=seconds();
        std::memcpy(out, q.cpuAmps, count*sizeof(qcomp));
        t[2]=seconds()-s;
        s=seconds();
        destroyQureg(q); allocated=false;
        finalizeQuESTEnv(); env=false;
        t[3]=seconds()-s;
        return 0;
    } catch (const std::exception&) {
        if (allocated) destroyQureg(q);
        if (env) finalizeQuESTEnv();
        return 7;
    } catch (...) {
        if (allocated) destroyQureg(q);
        if (env) finalizeQuESTEnv();
        return 8;
    }
}
