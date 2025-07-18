#!/usr/bin/env python3

"""
Copyright (C) 2025 Airbus

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

import os
import sys
import shutil
import asyncio
import logging
import pathlib
import argparse
import tempfile

from tqdm import tqdm
from tqdm.asyncio import tqdm_asyncio
from tqdm.contrib.logging import logging_redirect_tqdm

import utils


def create_folder_hierarchy(args: argparse.Namespace):
    # Create all required directories
    output_dir = utils.init_output_dir(args)
    (output_dir / "profraw").mkdir()
    (output_dir / "lcov").mkdir()
    (output_dir / "web").mkdir()


def perform_env_check(args: argparse.Namespace):
    if args.no_env_check:
        return

    # The user can either provide a path to the LLVM binaries, or try to find
    # them in the PATH
    if args.llvm_path:
        # If a path was provided, make sure it points to a directory and the
        # directory contains the required tools
        if not args.llvm_path.is_dir():
            raise ValueError(f"{args.llvm_path} directory not found")

        paths = [args.llvm_path / "llvm-profdata", args.llvm_path / "llvm-cov"]
        for path in paths:
            if not path.is_file():
                raise ValueError(f"{path} file not found")
    else:
        # Check if the required tools are available in the PATH, and if not give
        # some helpful advice
        if not utils.command_exists("llvm-profdata"):
            raise ValueError(
                "llvm-profdata command not found, try specifying `--llvm-path`"
            )
        if not utils.command_exists("llvm-cov"):
            raise ValueError("llvm-cov command not found, try specifying `--llvm-path`")

    # Check non-llvm tool availability
    commands = [args.genhtml_path]
    for cmd in commands:
        if not utils.command_exists(cmd):
            raise ValueError(f"{cmd} command not found")


async def generate_coverage(
    args: argparse.Namespace, input_file: pathlib.Path, semaphore: asyncio.Semaphore
) -> pathlib.Path:
    async with semaphore:
        logging.info("Generating coverage for test case: %s", input_file)

        # Create a new folder for this run
        profraw_dir = tempfile.mkdtemp(dir=args.output_dir / "profraw")
        profraw_dir = pathlib.Path(profraw_dir)

        # We use environment variables to write coverage in the dedicated folder
        # to allow parallel runs
        output_file = profraw_dir / "default-%p.profraw"
        env = {
            **os.environ,
            **utils.split_env_args(args.env),
            "LLVM_PROFILE_FILE": str(output_file),
            "LD_PRELOAD": os.environ.get("AFL_PRELOAD", ""),
        }

        # Run the original binary
        cmd, stdin = utils.prepare_coverage_cmd(args.coverage_cmd, input_file)
        await utils.run_cmd(cmd, env=env, timeout=args.timeout, stdin=stdin)

        # Make sure the output file was properly generated
        if not args.no_env_check and not list(profraw_dir.glob("*.profraw")):
            raise RuntimeError(
                "No coverage information generated during run, did you compile with `-fprofile-instr-generate -fcoverage-mapping`?"
            )

        return output_file


async def merge_tracefiles(args: argparse.Namespace) -> pathlib.Path:
    # Get path to llvm commands
    llvm_profdata = "llvm-profdata"
    llvm_cov = "llvm-cov"
    if args.llvm_path:
        llvm_profdata = args.llvm_path / llvm_profdata
        llvm_cov = args.llvm_path / llvm_cov

    # Merge all profraw files
    profdata_file = args.output_dir / "lcov" / "default.profdata"
    cmd = [
        str(llvm_profdata),
        "merge",
        "-sparse",
        str(args.output_dir / "profraw"),
        "-o",
        str(profdata_file),
    ]
    await utils.run_cmd(cmd)

    # Cleanup profraw files (if necessary)
    if not args.keep_intermediate:
        for path in (args.output_dir / "profraw").iterdir():
            if path.is_dir():
                shutil.rmtree(path)

    # Export coverage as an lcov file
    output_file = args.output_dir / "lcov" / "trace.lcov_total"
    cmd = [
        str(llvm_cov),
        "export",
        "--instr-profile",
        str(profdata_file),
        "--format",
        "lcov",
        str(args.binary_path),
    ]
    await utils.run_cmd(cmd, redirect_stdout=output_file)
    return output_file


async def generate_report(args: argparse.Namespace, output_file: pathlib.Path):
    cmd = [
        args.genhtml_path,
        "--prefix",
        str(args.code_dir),
        "--highlight",
        "--ignore-errors",
        "source",
        "--legend",
        "--function-coverage",
        str(args.output_dir / "lcov" / "trace.lcov_total"),
        "--output-directory",
        str(args.output_dir / "web"),
    ]
    await utils.run_cmd(cmd)


async def run(args: argparse.Namespace):
    loop = asyncio.get_event_loop()
    if args.jobs <= 0:
        raise ValueError("Number of jobs must be greater than 0")

    # Setup logging
    logging.basicConfig(
        level=args.log_level,
        format="[%(asctime)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    logging.getLogger().setLevel(args.log_level)

    # Check environment is properly configured
    perform_env_check(args)

    # Create the output folder and all subfolders
    create_folder_hierarchy(args)

    # Collect all input files
    queue_files = utils.get_queue_files(args)

    # Create a task for each file for which to collect coverage and use a
    # semaphore to limit the number of simultaneous jobs
    semaphore = asyncio.Semaphore(args.jobs)
    tasks = [
        asyncio.create_task(generate_coverage(args, input_file, semaphore))
        for input_file in queue_files
    ]

    # Run the tasks and re-raise any exception
    try:
        if args.no_progress:
            await asyncio.gather(*tasks)
        else:
            with logging_redirect_tqdm():
                await tqdm_asyncio.gather(*tasks, desc="Generating coverage")
    except Exception as e:
        for task in tasks:
            if not task.done():
                task.cancel()
        raise e

    # Merge all trace files
    tqdm.write("Merging coverage")
    trace_file = await merge_tracefiles(args)

    # Generate HTML output
    tqdm.write("Generating HTML report")
    await generate_report(args, trace_file)


def parse_args(argv: list) -> argparse.Namespace:
    parser = utils.common_args_parser()
    parser.add_argument(
        "-c",
        "--code-dir",
        required=True,
        type=pathlib.Path,
        help="Directory where the code lives (compiled with code coverage support; e.g. './src')",
    )
    parser.add_argument(
        "-b",
        "--binary-path",
        required=True,
        type=pathlib.Path,
        help="Path to the target binary (e.g. './a.out')",
    )
    parser.add_argument(
        "--genhtml-path",
        help="Path to the genhtml binary",
        default="genhtml",
    )
    parser.add_argument(
        "--llvm-path",
        type=pathlib.Path,
        help="Path to the llvm directory (e.g. '/usr/lib/llvm-14/bin')",
        default=None,
    )
    args = parser.parse_args(argv)
    utils.normalize_user_paths(args)
    return args


def main(argv: list):
    args = parse_args(argv)
    asyncio.run(run(args))


if __name__ == "__main__":
    # Allow running this file directly instead of calling afl-cov-fast.py with
    # the -m option
    main(sys.argv[1:])
