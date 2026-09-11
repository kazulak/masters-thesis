/* Capacity inspection only: reserves one named rank briefly, launches no kernel. */
#include <dpu.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
int main(int argc, char **argv) {
    if (argc != 2 || strcmp(argv[1], "--allow-physical") != 0) return 2;
    struct dpu_set_t set;
    dpu_error_t e = dpu_alloc_ranks(1, "backend=hw,rankPath=/dev/dpu_rank1", &set);
    if (e != DPU_OK) { fprintf(stderr, "rank allocation failed: %s\n", dpu_error_to_string(e)); return 3; }
    uint32_t nr=0, nd=0;
    dpu_error_t a=dpu_get_nr_ranks(set,&nr), b=dpu_get_nr_dpus(set,&nd);
    dpu_error_t f=dpu_free(set);
    if (a != DPU_OK || b != DPU_OK || f != DPU_OK || nr != 1 || nd < 4 || nd > 64) return 4;
    printf("{\"rank_path\":\"/dev/dpu_rank1\",\"rank_count\":%u,\"dpu_capacity\":%u,\"released\":true}\n", nr, nd);
    return 0;
}
