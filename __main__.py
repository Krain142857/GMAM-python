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
        choices=("gms", "gm82", "step"),
        default="gms",
        help="file format: gms or gm82; legacy step means gm82 + step (default: gms)",
    )
    parser.add_argument(
        "--output-type",
        choices=("timeline", "step"),
        default="timeline",
        help="output content: timeline or step (default: timeline)",
    )
    parser.add_argument(
        "--time-scale",
        choices=("ask", "adjust", "round"),
        default="ask",
        help="handle non-integer moments: ask, adjust, or round (default: ask)",
    )
    args = parser.parse_args()
    try:
        file_format = "gm82" if args.format == "step" else args.format
        output_type = "step" if args.format == "step" else args.output_type
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
            if file_format == "gms" and output_type == "step":
                Compiler.inject_gms_step(timeline, args.output)
            elif file_format == "gm82" and output_type == "step":
                Compiler.inject_gm82_step(timeline, args.output)
            else:
                with open(args.output, "w", encoding="utf-8", newline="\n") as stream:
                    Compiler.write_output(timeline, stream, file_format, output_type)
        else:
            if file_format == "gms" and output_type == "step":
                raise ValueError("gms + step requires -o/--output for GMX injection")
            Compiler.write_output(timeline, sys.stdout, file_format, output_type)
    except (CompileError, ValueError) as error:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
