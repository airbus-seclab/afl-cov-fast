#!/bin/bash
export AFL_SKIP_CPUFREQ=1
export AFL_I_DONT_CARE_ABOUT_MISSING_CRASHES=1
../../AFLplusplus/afl-fuzz -O -i ../corpus -o output $@ -- ./target.out @@
