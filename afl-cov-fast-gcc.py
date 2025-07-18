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
from typing import Iterable

from tqdm import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm

import utils


def create_folder_hierarchy(args: argparse.Namespace):
    # Create all required directories
    output_dir = utils.init_output_dir(args)
    (output_dir / "gcov").mkdir()
    (output_dir / "lcov").mkdir()
    (output_dir / "web").mkdir()


def perform_env_check(args: argparse.Namespace):
    if args.no_env_check:
        return

    commands = [args.lcov_path, args.genhtml_path]
    for cmd in commands:
        if not utils.command_exists(cmd):
            raise ValueError(f"{cmd} command not found")


async def generate_lcov_zero_coverage(args: argparse.Namespace):
    # Reset code coverage counters
    cmd = [
        args.lcov_path,
        "--no-checksum",
        "--zerocounters",
        "--directory",
        str(args.code_dir),
    ]
    await utils.run_cmd(cmd)

    # Run baseline lcov
    cmd = [
        args.lcov_path,
        "--no-checksum",
        "--capture",
        "--rc",
        "lcov_branch_coverage=1",
        "--initial",
        "--directory",
        str(args.code_dir),
        "--follow",
        "--output-file",
        str(args.output_dir / "lcov" / "trace.lcov_base"),
    ]
    await utils.run_cmd(cmd)


async def generate_coverage(
    args: argparse.Namespace, output_folder: pathlib.Path, input_file: pathlib.Path
):
    logging.info("Generating coverage for test case: %s", input_file)

    # We use environment variables to write coverage in the dedicated folder
    # to allow parallel runs
    env = {
        **os.environ,
        **utils.split_env_args(args.env),
        "GCOV_PREFIX": output_folder,
        "LD_PRELOAD": os.environ.get("AFL_PRELOAD", ""),
    }

    # Run the original binary
    cmd, stdin = utils.prepare_coverage_cmd(args.coverage_cmd, input_file)
    await utils.run_cmd(cmd, env=env, timeout=args.timeout, stdin=stdin)


async def coverage_worker(
    args: argparse.Namespace, queue: asyncio.Queue, pbar: tqdm
) -> pathlib.Path:
    # Create a folder for this worker
    gcov_dir = tempfile.mkdtemp(dir=args.output_dir / "gcov")
    gcov_dir = pathlib.Path(gcov_dir)
    logging.debug("Created worker at path %s", gcov_dir)

    # Run until the queue is empty
    consumed_items = 0
    while not queue.empty():
        path = await queue.get()
        consumed_items += 1
        await generate_coverage(args, gcov_dir, path)
        queue.task_done()
        pbar.update(1)

    # If this worker didn't consume anything from the queue, exit early to avoid
    # running lcov without any input file
    if consumed_items == 0:
        logging.debug(
            "Worker at %s didn't consume any queue item, exiting early", gcov_dir
        )
        shutil.rmtree(gcov_dir)
        return None

    # We now need to place the gcno files next to their gcda counterparts
    # To avoid copying them, we instead create symbolic links
    gcda_file_count = 0
    for gcda in gcov_dir.rglob("*.gcda"):
        # Count number of gcda files to make sure coverage information was
        # properly generated
        gcda_file_count += 1

        # Find gcno location based on gcda path
        gcno = gcda.relative_to(gcov_dir).with_suffix(".gcno")
        gcno = pathlib.Path("/") / gcno

        # Create symlink
        gcda.with_suffix(".gcno").symlink_to(gcno)

    # Make sure coverage information was generated
    if not args.no_env_check and gcda_file_count == 0:
        raise RuntimeError(
            "No coverage information generated during run, did you compile with `--coverage`?"
        )

    # We can now run lcov from the main directory to generate a unique
    # coverage file for this execution
    output_file = args.output_dir / "lcov" / (gcov_dir.stem + ".lcov")
    lcov_cmd = [
        args.lcov_path,
        "--no-checksum",
        "--capture",
        "--rc",
        "lcov_branch_coverage=1",
        "--directory",
        str(gcov_dir),
        "--follow",
        "--output-file",
        str(output_file),
    ]
    await utils.run_cmd(lcov_cmd)

    # Cleanup if necessary and return the generated output file
    if not args.keep_intermediate:
        shutil.rmtree(gcov_dir)
    return output_file


async def merge_tracefiles(
    args: argparse.Namespace, input_files: Iterable[pathlib.Path]
) -> pathlib.Path:
    # The input_files array might contain some "None" values if some spawned
    # workers did not get any input and aborted early
    input_files = [path for path in input_files if path is not None]

    # Make sure there is at least one file left
    if not args.no_env_check and not input_files:
        raise RuntimeError("No coverage file generated, is the AFL++ queue empty?")

    # Create command line with all input file paths
    output_file = args.output_dir / "lcov" / f"trace.lcov_total"
    cmd = [
        args.lcov_path,
        "--output-file",
        str(output_file),
        "-a",
        str(args.output_dir / "lcov" / "trace.lcov_base"),
    ]
    for path in input_files:
        cmd += ["-a", str(path)]

    # Actually run command
    logging.info("Merging %d tracefiles into %s", len(input_files), str(output_file))
    await utils.run_cmd(cmd)

    # Cleanup and return generated file
    if not args.keep_intermediate:
        for path in input_files:
            path.unlink()
    return output_file


async def generate_report(args: argparse.Namespace, input_file: pathlib.Path):
    cmd = [
        args.genhtml_path,
        "--prefix",
        str(args.code_dir),
        "--highlight",
        "--ignore-errors",
        "source",
        "--legend",
        "--function-coverage",
        str(input_file),
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

    # Init lcov
    tqdm.write("Initializing coverage engine")
    await generate_lcov_zero_coverage(args)

    # When running the target, a .gcda file is created or, if it already exists,
    # updated with the new coverage
    # To handle multiprocessing, we create a queue with all the input files to
    # process, and then create 1 worker per job that will have its own output
    # folder
    queue_files = asyncio.Queue()
    for path in utils.get_queue_files(args):
        queue_files.put_nowait(path)

    # Create workers
    with logging_redirect_tqdm():
        pbar = tqdm(total=queue_files.qsize(), desc="Generating coverage")
        tasks = []
        for i in range(args.jobs):
            tasks.append(asyncio.create_task(coverage_worker(args, queue_files, pbar)))

        # Wait until all the workers are done
        try:
            partial_trace_files = await asyncio.gather(*tasks)
        except Exception as e:
            for task in tasks:
                if not task.done():
                    task.cancel()
            raise e
        finally:
            pbar.close()

    # Merge all trace files
    tqdm.write("Merging coverage")
    trace_file = await merge_tracefiles(args, partial_trace_files)

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
        "--genhtml-path",
        help="Path to the genhtml binary",
        default="genhtml",
    )
    parser.add_argument(
        "--lcov-path",
        help="Path to the lcov binary",
        default="lcov",
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
