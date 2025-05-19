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
import shlex
import shutil
import asyncio
import logging
import pathlib
import argparse
import itertools
from typing import Optional, Iterable, Union


def normalize_user_paths(args: argparse.Namespace):
    # Normalize all paths in arguments provided on the command line
    for k, v in vars(args).items():
        if isinstance(v, pathlib.Path):
            v = v.expanduser().resolve()
            setattr(args, k, v)


def command_exists(cmd: Union[str, pathlib.Path]) -> bool:
    return shutil.which(cmd) is not None


def init_output_dir(args: argparse.Namespace) -> pathlib.Path:
    # Handle already existing output directories
    args.output_dir = args.output_dir or args.afl_fuzzing_dir / "cov"
    if args.output_dir.exists():
        if args.overwrite:
            logging.warning("Deleting previous output directory %s", args.output_dir)
            shutil.rmtree(args.output_dir)
        else:
            raise RuntimeError(f"Output directory {args.output_dir} already exists")

    # Create output directory
    args.output_dir.mkdir()
    return args.output_dir


def get_queue_files(args: argparse.Namespace) -> Iterable[pathlib.Path]:
    # Check if the user provided the top-level folder or a folder of a single
    # instance (e.g. output vs output/default)
    logging.info("Collecting queue files")
    if (args.afl_fuzzing_dir / "queue").is_dir():
        return args.afl_fuzzing_dir.glob("queue/id:*")
    else:
        return args.afl_fuzzing_dir.glob("*/queue/id:*")


def prepare_coverage_cmd(coverage_cmd: str, input_file: pathlib.Path):
    cmd = coverage_cmd.replace("@@", "AFL_FILE")
    if "AFL_FILE" in cmd:
        cmd = cmd.replace("AFL_FILE", str(input_file))
        stdin = None
    else:
        with open(input_file, "rb") as f:
            stdin = f.read()
    return cmd, stdin


async def run_cmd(
    cmd: Union[str, list],
    env: Optional[dict] = None,
    timeout: Optional[int] = None,
    stdin: Optional[bytes] = None,
    redirect_stdout: Optional[pathlib.Path] = None,
):
    if isinstance(cmd, str):
        cmd = shlex.split(cmd)

    logging.debug("Running '%s' (stdin: %s, env: %s)", cmd, stdin, env)
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        env=env,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(stdin),
            timeout=timeout,
        )

        logging.debug("%s:\nstdout %s\nstderr: %s", cmd, stdout, stderr)

        if redirect_stdout:
            with open(redirect_stdout, "wb") as f:
                f.write(stdout)

        if stderr and proc.returncode != 0:
            logging.warn(
                "%s: retcode %d stderr %s", cmd, proc.returncode, stderr.decode("utf-8")
            )

    except asyncio.exceptions.TimeoutError:
        logging.warn("%s: timeout", cmd)
        try:
            proc.kill()
        except OSError:
            # Ignore 'no such process' error
            pass


def common_args_parser(*args, **kwargs) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(*args, **kwargs)
    parser.add_argument(
        "-e",
        "--coverage-cmd",
        required=True,
        help="Set command to exec (including args, and assumes code coverage support; e.g. './a.out @@')",
    )
    parser.add_argument(
        "-d",
        "--afl-fuzzing-dir",
        required=True,
        type=pathlib.Path,
        help="top level AFL fuzzing directory (e.g. './output' or './output/default')",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        type=pathlib.Path,
        help="Output folder in which to write results (default: <afl-fuzzing-dir>/cov)",
        default=None,
    )
    parser.add_argument(
        "-O",
        "--overwrite",
        action="store_true",
        help="Overwrite output folder if it already exists (default: False)",
        default=False,
    )
    parser.add_argument(
        "-k",
        "--keep-intermediate",
        action="store_true",
        help="Keep intermediate files (default: False)",
        default=False,
    )
    parser.add_argument(
        "-t",
        "--timeout",
        type=float,
        help="Timeout for target program run (in seconds, default: no timeout)",
        default=None,
    )
    parser.add_argument(
        "-j",
        "--jobs",
        type=int,
        help="Maximum number of concurrent jobs (default: 1)",
        default=1,
    )
    parser.add_argument(
        "-l",
        "--log-level",
        help="Tool output log level (default: WARNING)",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="WARNING",
    )
    parser.add_argument(
        "--no-progress",
        action="store_true",
        help="Disable progress bar output (default: False)",
        default=False,
    )
    parser.add_argument(
        "--no-env-check",
        action="store_true",
        help="Disable environment checks (e.g. commands are available and coverage files were properly generated, default: False)",
        default=False,
    )
    return parser
