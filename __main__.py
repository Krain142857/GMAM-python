import argparse
import sys
from pathlib import Path

from gmam.compiler import Compiler
from gmam.errors import CompileError


def main() -> int:
    parser = argparse.ArgumentParser(description="Compile GMAM timeline source files.")
    parser.add_argument("inputs", nargs="+", help="input .tl files")
    parser.add_argument("-o", "--output", help="output timeline XML (defaults to stdout)")
    parser.add_argument(
        "-f", "--format",
        choices=("gms", "gm82"),
        default="gms",
        help="file format: gms or gm82 (default: gms)",
    )
    parser.add_argument(
        "--output-type",
        choices=("timeline", "step", "txt"),
        default="timeline",
        help="output content: timeline, step, or txt (default: timeline)",
    )
    parser.add_argument(
        "--time-scale",
        choices=("ask", "adjust", "round"),
        default="ask",
        help="handle non-integer moments: ask, adjust, or round (default: ask)",
    )
    args = parser.parse_args()
    try:
        file_format = args.format
        output_type = args.output_type
        compiler = Compiler()
        timeline = compiler.compile_files(
            args.inputs,
            time_scale=args.time_scale,
            output_format=output_type,
        )
        input_path = Path(args.inputs[-1])
        output_path = input_path.with_suffix(".out")
        with output_path.open("w", encoding="utf-8", newline="\n") as stream:
            compiler.write_output_source(stream)
        print(f"已生成计算后的 step 文件：{output_path}", file=sys.stderr)
        if compiler.scaled_source is not None:
            scaled_path = input_path.with_name(f"{input_path.stem}.scaled.tl")
            with scaled_path.open("w", encoding="utf-8", newline="\n") as stream:
                compiler.write_scaled_source(stream)
            print(f"已生成放缩后的源文件：{scaled_path}", file=sys.stderr)
        if args.output:
            with open(args.output, "w", encoding="utf-8", newline="\n") as stream:
                Compiler.write_output(timeline, stream, file_format, output_type)
        else:
            Compiler.write_output(timeline, sys.stdout, file_format, output_type)
    except (CompileError, ValueError) as error:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
