import argparse
import sys
from pathlib import Path

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
    parser.add_argument(
        "--time-scale",
        choices=("ask", "adjust", "round"),
        default="ask",
        help="handle non-integer moments: ask, adjust, or round (default: ask)",
    )
    args = parser.parse_args()
    try:
        compiler = Compiler()
        timeline = compiler.compile_files(args.inputs, time_scale=args.time_scale)
        if compiler.scaled_source is not None:
            input_path = Path(args.inputs[0])
            scaled_path = input_path.with_name(f"{input_path.stem}.scaled.tl")
            with scaled_path.open("w", encoding="utf-8", newline="\n") as stream:
                compiler.write_scaled_source(stream)
            print(f"已生成放缩后的源文件：{scaled_path}", file=sys.stderr)
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
