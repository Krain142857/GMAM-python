import argparse
import sys

from .compiler import Compiler
from .errors import CompileError


def main() -> int:
    parser = argparse.ArgumentParser(description="Compile GMAM timeline source files.")
    parser.add_argument("inputs", nargs="+", help="input .tl files")
    parser.add_argument("-o", "--output", help="output timeline XML (defaults to stdout)")
    parser.add_argument(
        "-f", "--format",
        choices=("gms", "gm82"),
        default="gms",
        help="output format: gms XML or gm82 action script (default: gms)",
    )
    args = parser.parse_args()
    try:
        timeline = Compiler().compile_files(args.inputs)
        if args.output:
            with open(args.output, "w", encoding="utf-8", newline="\n") as stream:
                Compiler.write_timeline(timeline, stream, args.format)
        else:
            Compiler.write_timeline(timeline, sys.stdout, args.format)
    except CompileError as error:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
