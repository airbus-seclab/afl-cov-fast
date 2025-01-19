#!/bin/bash
../../afl-cov-fast.py -m frida --afl-fuzzing-dir 'output' --afl-path '../../AFLplusplus' --coverage-cmd './target.out @@' $@
