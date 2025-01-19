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

import argparse
import importlib

import utils

AFL_COV_MODULES = {
    "gcc": importlib.import_module("afl-cov-fast-gcc"),
    "llvm": importlib.import_module("afl-cov-fast-llvm"),
    "qemu": importlib.import_module("afl-cov-fast-qemu"),
    "frida": importlib.import_module("afl-cov-fast-frida"),
}


def main():
    # Only parse the "mode" argument here, and disable the -h / --help option to
    # allow passing it to each module
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "-m",
        "--mode",
        required=True,
        help="Run mode (depending on the target binary compilation workflow)",
        choices=AFL_COV_MODULES.keys(),
    )
    args, remaining_args = parser.parse_known_args()

    # Get module to call based on user arguments
    try:
        module = AFL_COV_MODULES[args.mode.lower()]
    except KeyError:
        raise ValueError(f"Unhandled mode {args.mode}")

    # Call the selected module's main function, which will handle the rest of
    # the arguments
    module.main(remaining_args)


if __name__ == "__main__":
    main()
