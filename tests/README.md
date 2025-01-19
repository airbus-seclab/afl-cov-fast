# afl-cov-fast

This folder contains simple tests for all backends supported by afl-cov-fast.
For an end-to-end example of how to run them, see the
[associated example](../examples/tests.md).

## Setup

The tests assume that the AFL++ repository has been cloned and built at the root
of the afl-cov-fast repository:

```bash
cd /path/to/afl-cov-fast
git clone -b dev https://github.com/AFLplusplus/AFLplusplus.git
cd AFLplusplus
make distrib
cd ../tests
```

## Target

A very simple target (in [`target.c`](target.c)) is used to run these tests: it
reads up to 4096 bytes from the file provided as argument and, if the 8 first
bytes are equal to `0xdeadbeef`, they jump to the `0xdeadbeef` address (which
should crash).

The corpus for this target only contains a dummy file: [`a.txt`](corpus/a.txt),
with some `A`s.

## Scripts

Each backend has a `Makefile` to easily build the target for fuzzing and, if
relevant, build it again with code-coverage options:

```bash
make
```

The `fuzz.sh` script can be used to run AFL++ on the built target. For example,
to run it for 120 seconds for a given backend:

```bash
./fuzz.sh -V 120
```

Once AFL++ has been run and the queue has been populated, coverage information
can be generated using the `cov.sh` script:

```bash
./cov.sh -j8
```
