# GMAM Python 编译器

GMAM Python 是一个将 GMAM 时间轴源文件（`.tl`）翻译为 GameMaker
时间轴文件的 Python 编译器。它包含词法分析、语法分析、表达式求值和
两种时间轴输出格式，以及一种每帧执行的 step 事件格式。

除普通 Step 外，语言还支持顶层 `forstep` 语句，可遍历列表批量生成
多个 Step。具体语法请参阅 [RULES.md](RULES.md)。

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
python -m gmam INPUTS... [-o OUTPUT] [-f {gms,gm82,step}] [--time-scale {ask,adjust,round}]
```

- `INPUTS...`：一个或多个 `.tl` 输入文件。多个文件会按命令行顺序合并编译。
- `-o`、`--output`：输出文件路径。不填写时写到标准输出。
- `-f`、`--format`：输出格式：
  - `gms`：GameMaker Studio 时间轴 XML，默认值；
  - `gm82`：GameMaker 8.2 的 GML/YYD ACTION 格式；
  - `step`：每帧执行一次的纯文本 `step`/`switch` 代码。
- `--time-scale`：处理非整数 moment：
  - `ask`：检测到 `go/look` 产生非整数时间时询问用户，默认值；
  - `adjust`：自动调整 `TLSTEP_PER_BEAT` 并整体放缩 moment；
  - `round`：对非整数 moment 四舍五入。

使用 `--format step` 时，`--time-scale` 会被忽略。`go/look` 的时间按照每秒
50 次 step event 计算：

```text
每个 note 对应的 moment = 50 * 60 / BPM * NOTE_PER_BEAT / note
```

计算过程保留小数，只在最终输出 moment 时四舍五入；因此不会询问调整、
生成 scaled 源文件，也不会因为小数 moment 报错。

`ask` 模式会给出两个推荐值。第一个是
`lcm(所有 note) / NOTE_PER_BEAT`，第二个是第一个推荐值乘以原
`TLSTEP_PER_BEAT`。如果手动输入过具体时间，可以考虑第二个值。确认调整
后，目标值输入为空时使用第一个推荐值。

如果实际采用了 `adjust`（包括 `ask` 中确认调整），命令行还会在第一个
输入文件旁生成 `<原名>.scaled.tl`。该文件第一行设置选定的
`TLSTEP_PER_BEAT`，之后写入已经完成时间计算和放缩的 Step。未调整或使用
`round` 时不会生成该文件。

无论使用哪种输出格式或时间缩放策略，命令行都会在最后一个输入文件旁生成
`<原名>.out`。该文件只包含所有已经展开、计算并完成最终 moment 处理的
Step，格式为：

```text
[0, 1, 2] {`计算后的内容`};
```

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

`format` 可选 `gms`、`gm82` 或 `step`。使用 `step` 时请在编译 API 中传入
`output_format="step"`，再使用 `Compiler.write_timeline(..., format="step")`。
编译后的 Step 文本也可通过 `Compiler.write_output_source()` 写入。

## 相关文档

- [RULES.md](RULES.md)：当前支持的主要语法规则和示例。
