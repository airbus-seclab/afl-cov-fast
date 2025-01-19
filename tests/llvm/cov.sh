#!/bin/bash
../../afl-cov-fast.py -m llvm --code-dir '.' --afl-fuzzing-dir 'output' --coverage-cmd './target.cov.out @@' --binary-path './target.cov.out' $@
