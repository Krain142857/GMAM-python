# GMAM Python 编译器

GMAM Python 是一个将 GMAM 时间轴源文件（`.tl`）翻译为 GameMaker
时间轴文件的 Python 编译器。它包含词法分析、语法分析、表达式求值和
两种时间轴输出格式。

## 运行环境

- Python 3.9 或更高版本
- 仅使用 Python 标准库，不需要安装第三方包
- Windows、Linux 和 macOS 均可运行

在项目根目录（包含 `gmam` 文件夹的目录）运行：

```powershell
python -m gmam 输入文件.tl -o 输出文件 --format gms
```

## 命令行参数

```text
python -m gmam INPUTS... [-o OUTPUT] [-f {gms,gm82}] [--time-scale {ask,adjust,round}]
```

- `INPUTS...`：一个或多个 `.tl` 输入文件。多个文件会按命令行顺序合并编译。
- `-o`、`--output`：输出文件路径。不填写时写到标准输出。
- `-f`、`--format`：输出格式：
  - `gms`：GameMaker Studio 时间轴 XML，默认值；
  - `gm82`：GameMaker 8.2 的 GML/YYD ACTION 格式。
- `--time-scale`：处理非整数 moment：
  - `ask`：检测到 `go/look` 产生非整数时间时询问用户，默认值；
  - `adjust`：自动调整 `TLSTEP_PER_BEAT` 并整体放缩 moment；
  - `round`：对非整数 moment 四舍五入。

`ask` 模式会给出两个推荐值。第一个是
`lcm(所有 note) / NOTE_PER_BEAT`，第二个是第一个推荐值乘以原
`TLSTEP_PER_BEAT`。如果手动输入过具体时间，可以考虑第二个值。确认调整
后，目标值输入为空时使用第一个推荐值。

如果实际采用了 `adjust`（包括 `ask` 中确认调整），命令行还会在第一个
输入文件旁生成 `<原名>.scaled.tl`。该文件第一行设置选定的
`TLSTEP_PER_BEAT`，之后写入已经完成时间计算和放缩的 Step。未调整或使用
`round` 时不会生成该文件。

示例：

```powershell
# 输出 GMS 时间轴 XML
python -m gmam input\test.tl -o output\test.timeline.gmx

# 输出 GM 8.2 格式
python -m gmam input\test.tl -o output\test.gml --format gm82

# 编译多个文件并输出到标准输出
python -m gmam input\define.tl input\avoidance.tl --format gms
```

编译失败时，程序会在错误输出中显示行号和列号，并返回退出码 `1`。

## Python API

```python
from gmam import Compiler

timeline = Compiler().compile_files(["input/test.tl"], time_scale="round")

with open("test.timeline.gmx", "w", encoding="utf-8") as output:
    Compiler.write_timeline(timeline, output, format="gms")
```

`format` 可选 `gms` 或 `gm82`。

## 相关文档

- [RULES.md](RULES.md)：当前支持的主要语法规则和示例。
