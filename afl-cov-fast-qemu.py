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
import glob
import shlex
import asyncio
import logging
import pathlib
import argparse
import tempfile
from typing import Iterable

from tqdm import tqdm
from tqdm.asyncio import tqdm_asyncio
from tqdm.contrib.logging import logging_redirect_tqdm

import utils


def create_folder_hierarchy(args: argparse.Namespace):
    # Create all required directories
    output_dir = utils.init_output_dir(args)
    (output_dir / "drcov").mkdir()


def perform_env_check(args: argparse.Namespace):
    if args.no_env_check:
        return

    path = args.afl_path / "afl-qemu-trace"
    if not path.is_file():
        raise ValueError(f"{path} file not found, did you compile AFL-QEMU?")

    path = args.afl_path / "qemu_mode/qemuafl/build/contrib/plugins/libdrcov.so"
    if not path.is_file():
        raise ValueError(f"{path} file not found, did you compile QEMU plugins?")

    if not utils.command_exists(args.drcov_merge_path):
        raise ValueError(
            f"{args.drcov_merge_path} command not found, did you build and install the submodule? If not, try specifying `--drcov-merge-path`"
        )


async def generate_coverage(
    args: argparse.Namespace, input_file: pathlib.Path, semaphore: asyncio.Semaphore
) -> pathlib.Path:
    async with semaphore:
        logging.info("Generating coverage for test case: %s", input_file)

        # Create a new folder for this run
        output_file = tempfile.mktemp(
            prefix="tmp", suffix=".drcov.trace", dir=args.output_dir / "drcov"
        )
        output_file = pathlib.Path(output_file)

        # We use environment variables to enable the trace plugin and write
        # coverage to the generated file path
        # Note: We keep the original environment variables as afl-qemu-trace
        # accepts many AFL_* and QEMU_* options through there
        plugin_path = (
            args.afl_path / "qemu_mode/qemuafl/build/contrib/plugins/libdrcov.so"
        )
        env = {
            **os.environ,
            **utils.split_env_args(args.env),
            "QEMU_PLUGIN": f"{plugin_path},arg=filename={output_file}",
        }

        # Run the original binary
        cmd, stdin = utils.prepare_coverage_cmd(args.coverage_cmd, input_file)
        cmd = [str(args.afl_path / "afl-qemu-trace"), "--"] + shlex.split(cmd)
        await utils.run_cmd(cmd, env=env, timeout=args.timeout, stdin=stdin)

        # Make sure the output file was properly generated
        if not args.no_env_check and not output_file.is_file():
            raise RuntimeError("No coverage information generated during run!")

        return output_file


async def merge_tracefiles(args: argparse.Namespace) -> pathlib.Path:
    # Merge all drcov files
    drcov_files_glob = str(args.output_dir / "drcov") + "/tmp*.drcov.trace"
    output_file = args.output_dir / "drcov" / "full.drcov.trace"

    cmd = [
        args.drcov_merge_path,
        "-o",
        str(output_file),
        drcov_files_glob,
    ]
    await utils.run_cmd(cmd)

    # Cleanup drcov files (if necessary)
    if not args.keep_intermediate:
        for path in glob.iglob(drcov_files_glob):
            pathlib.Path(path).unlink()

    return output_file


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


def parse_args(argv: list) -> argparse.Namespace:
    parser = utils.common_args_parser()
    parser.add_argument(
        "-a",
        "--afl-path",
        type=pathlib.Path,
        required=True,
        help="Path to the AFL++ folder (e.g. './AFLplusplus')",
    )
    parser.add_argument(
        "--drcov-merge-path",
        help="Path to the drcov-merge binary",
        default="drcov-merge",
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
