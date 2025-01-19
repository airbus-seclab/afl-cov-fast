#!/bin/bash
../../afl-cov-fast.py -m qemu --afl-fuzzing-dir 'output' --afl-path '../../AFLplusplus' --coverage-cmd './target.out @@' $@
