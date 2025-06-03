# afl-cov-fast

afl-cov-fast is a tool to generate code coverage from AFL test cases. It aims to
efficiently generate a "zero coverage" report of functions and lines never
covered by a fuzzing campaign, both when code is available and in binary-only
mode.

It is a reimplementation of
[afl-cov](https://github.com/vanhauser-thc/afl-cov)'s "cover-corpus" mode with
additional support for binary-only targets (via the QEMU and Frida backends),
multiprocessing, and reduced Python overhead.

## Install

Start by cloning this repository and its submodules:

```bash
$ git clone --recursive https://github.com/airbus-seclab/afl-cov-fast.git
```

### Requirements

* Python 3.6 or newer;
* The Python `tqdm` package;
* `lcov` (for the `lcov` and `genhtml` commands);
* `llvm` (for the `llvm-profdata` command);
* `llvm-tools` (for the `llvm-cov` command).

#### Docker

A `Dockerfile` is provided with pre-installed dependencies. To use it, the
following commands can be used:

```bash
$ docker build -t afl-cov-fast .
$ docker run --rm -it -v "${PWD}:/workdir" -v "<path-to-your-fuzzed-project>:<absolute-path-to-your-fuzzed-project>" -u `id -u`:`id -g` --name afl-cov-fast afl-cov-fast
```

**Notes:**

* You have to mount your project with the same path in the docker container when
  in GCC mode so that paths to coverage files are properly resolved. In other
  cases, you can use an arbitrary folder (e.g. `/project`);
* AFL++ is purposefully not included in the Docker image so you can use your
  exact version when relying on the QEMU or Frida backend. This means that you
  will have to build the QEMU TCG plugin yourself (see below) if necessary.

#### Debian

When using Debian, dependencies can be installed with the following commands:

```bash
$ sudo apt update
$ sudo apt install python3 python3-tqdm lcov llvm-16 llvm-16-tools
```

**Notes:**

* The `lcov` dependency is only required for the GCC and LLVM backend;
* The `llvm-*` dependencies are only required for the LLVM backend.

#### venv

Alternatively, Python dependencies could be installed using `pip` in a virtual
environment like so:

```bash
$ python3 -m venv .env
$ source .env/bin/activate
$ pip3 install -r requirements.txt
```

### QEMU

For the QEMU backend, coverage is obtained using a QEMU TCG plugin. This is
supported natively by AFL++ since
[this commit](https://github.com/AFLplusplus/AFLplusplus/commit/a4017406dc02e49dbc3820e3eb5bee5e15d7fed1)
present in [v4.10c](https://github.com/AFLplusplus/AFLplusplus/releases/tag/v4.10c).

The QEMU plugins simply need to be compiled in AFL++:

```bash
$ cd <afl++-path>/qemu_mode
$ make -C qemuafl plugins
```

### drcov-merge

A custom utility is used to merge drcov files into a single "full" coverage file
(for the QEMU and Frida backend), which is included as a submodule of this
repository and must be built separately:

```bash
$ cargo install --path drcov-merge
```

## Usage

### Compilation

When source code is available (for the GCC or LLVM backend), the binary is
instrumented at compile time. Specific options must be added for coverage to be
exported when the target is run. These options are described below.

#### GCC

Compile the target with the `--coverage` option (equivalent to
`-fprofile-arcs -ftest-coverage`).

When run, the output binary will then output coverage information in `gcno` and
`gcda` files.

#### LLVM

Compile the target with the `-fprofile-instr-generate -fcoverage-mapping`
options.

When run, the output binary will then output coverage information in a `profraw`
file.

### Running

When running, the `coverage-command` is used to run the target binary and obtain
coverage. The `@@` and `AFL_FILE` strings in this command will be replaced with
the path to the input file. If none of them is present, the content of the input
file will be written to `stdin` instead.

#### GCC

Example usage:

```bash
$ afl-cov-fast.py -m gcc --code-dir 'src' --afl-fuzzing-dir 'output' --coverage-cmd './a.out @@' -j8
```

Then, simply open the `output/cov/web/index.html` file.

#### LLVM

Example usage:

```bash
$ afl-cov-fast.py -m llvm --code-dir 'src' --afl-fuzzing-dir 'output' --coverage-cmd './a.out @@' --binary-path 'a.out' -j8
```

Then, simply open the `output/cov/web/index.html` file.

#### QEMU

Example usage:

```bash
$ afl-cov-fast.py -m qemu --afl-fuzzing-dir 'output' --afl-path './AFLplusplus' --coverage-cmd './a.out @@' -j8
```

Then, load the aggregated coverage file in `output/cov/drcov/full.drcov.trace`
using [lighthouse](https://github.com/gaasedelen/lighthouse),
[Cartographer](https://github.com/nccgroup/Cartographer),
[lightkeeper](https://github.com/WorksButNotTested/lightkeeper), or
[CutterDRcov](https://github.com/rizinorg/CutterDRcov).

#### Frida

Example usage:

```bash
$ afl-cov-fast.py -m frida --afl-fuzzing-dir 'output' --afl-path './AFLplusplus' --coverage-cmd './a.out @@' -j8
```

Then, load the aggregated coverage file in `output/cov/drcov/full.drcov.trace`
using [lighthouse](https://github.com/gaasedelen/lighthouse),
[Cartographer](https://github.com/nccgroup/Cartographer),
[lightkeeper](https://github.com/WorksButNotTested/lightkeeper), or
[CutterDRcov](https://github.com/rizinorg/CutterDRcov).

## Examples

Practical usage examples are also provided in the [examples directory](./examples).

## Contributing

Issues and pull requests are welcome!

Notably, the following features could be added:

* Support for other backends (e.g.
  [Nyx](https://github.com/AFLplusplus/AFLplusplus/tree/dev/nyx_mode),
  [Unicorn](https://github.com/AFLplusplus/AFLplusplus/tree/dev/unicorn_mode)),
* Support for in-memory fuzzing instead of providing inputs from a file or
  stdin,
* Any other feature you might find useful.

## References

* <https://github.com/vanhauser-thc/afl-cov>
* <https://github.com/eqv/aflq_fast_cov>
* <https://github.com/novafacing/pyafl_qemu_trace>

## License

This project is licensed under the GPLv3 License. See the
[LICENSE file](LICENSE) for details.
