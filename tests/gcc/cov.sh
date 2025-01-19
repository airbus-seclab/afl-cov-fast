#!/bin/bash
../../afl-cov-fast.py -m gcc --code-dir '.' --afl-fuzzing-dir 'output' --coverage-cmd './target.cov.out @@' $@
