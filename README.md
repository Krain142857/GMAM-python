# GMAM Python 编译器

GMAM Python 是一个将 GMAM 源文件（`.tl`）编译为 GameMaker 时间轴相关输出的
Python 编译器。

## 运行环境

- Python 3.9 或更高版本
- Windows、Linux 和 macOS 均可运行
- 当前核心编译库仅依赖 Python 标准库

GMAM 当前源码不需要安装第三方包；直接使用系统 Python 即可运行命令行和
作为库导入。

如果你只是把 `gmam` 当作一个 Python 包在自己的脚本中调用，通常不需要额外
准备虚拟环境之外的任何依赖。

在项目根目录（包含 `gmam` 文件夹的目录）执行：

```powershell
python -m gmam input\test.tl -o output\test.timeline.gmx
python -m gmam.__main_gui___
```

## 命令行接口

```text
python -m gmam INPUTS... [-o OUTPUT] [-f {gms,gm82}] [--output-type {timeline,step,txt}] [--time-scale {ask,adjust,round}]
```

参数说明：

- `INPUTS...`：一个或多个 `.tl` 输入文件，按命令行顺序合并编译。
- `-o`、`--output`：输出文件路径；省略时写到标准输出。
- `-f`、`--format`：timeline 或 step 输出所使用的目标格式：
  - `gms`：GameMaker Studio XML；
  - `gm82`：GameMaker 8.2 的 GML / YYD ACTION 文本。
- `--output-type`：输出模式：
  - `timeline`：输出 timeline；
  - `step`：输出 Step 事件内容；
  - `txt`：输出纯文本 Step 代码。
- `--time-scale`：处理非整数 moment 的策略：
  - `ask`：发现非整数时间时询问；
  - `adjust`：自动调整 `TLSTEP_PER_BEAT` 并整体放缩；
  - `round`：直接四舍五入。

### 输出模式与格式的关系

`format` 与 `output-type` 组合行为如下：

- `gms + timeline`：输出 GMS timeline XML；
- `gm82 + timeline`：输出 GM82 timeline 文本；
- `gms + step`：向 GMX 对象文件注入或替换 Step 事件；
- `gm82 + step`：向 GM82 object 文件注入或替换 `Step_0`；
- `txt`：忽略 `format`，直接输出纯文本 Step 代码。

### step 注入规则

`gms + step` 需要 `-o` 指向 GMX 对象文件。生成代码会带有
`///GMAM GENERATED` 标记，并注入到 `eventtype=3, enumb=0`。

- 若已有带该标记的 action，则替换该 action；
- 若已有 Step 事件但没有该标记，则只追加 action；
- 若没有 Step 事件，则新增事件；
- 若目标文件不存在，则自动创建最小可用 GMX 对象文件。

`gm82 + step` 需要 `-o` 指向 GM82 object 文件，并将带有
`///GMAM GENERATED` 标记的 action 注入或替换到 `Step_0`。

- 若已有带该标记的 action，则替换该 action；
- 若已有 `Step_0` 但没有该标记，则只追加 action；
- 若没有 `Step_0`，则新增该事件。


### 示例

```powershell
# 输出 GMS timeline XML
python -m gmam input\test.tl -o output\test.timeline.gmx

# 输出 GM82 timeline 文本
python -m gmam input\test.tl -o output\test.timeline.gm82 --format gm82

# 注入 GMS Step 事件
python -m gmam input\avoidance.tl -o objects\objAvoid.object.gmx --format gms --output-type step

# 输出纯文本 Step 代码
python -m gmam input\test.tl --output-type txt

# 合并多个输入文件
python -m gmam input\define.tl input\avoidance.tl --format gms
```

### 错误处理

编译失败时返回退出码 `1`，并在标准错误输出中打印诊断信息。
诊断信息包含：

- 文件名（多文件输入时为实际出错文件）；
- 行号；
- 列号；
- 错误消息。

## Python API

### 基本编译

```python
from gmam import Compiler

compiler = Compiler()
timeline = compiler.compile_files(["input/test.tl"], time_scale="round")

with open("test.timeline.gmx", "w", encoding="utf-8") as output:
    Compiler.write_output(timeline, output, "gms", "timeline")
```

### 输出纯文本 Step 代码

```python
from gmam import Compiler
from io import StringIO

compiler = Compiler()
timeline = compiler.compile_files(["input/test.tl"], output_format="txt")

stream = StringIO()
Compiler.write_output(timeline, stream, "gms", "txt")
print(stream.getvalue())
```

### 访问附加产物

```python
from gmam import Compiler

compiler = Compiler()
compiler.compile_files(["input/test.tl"], time_scale="adjust")

print(compiler.output_source)
print(compiler.scaled_source)
```

说明：

- `compile_files()` 负责读取文件并编译；
- `compile_sources()` 可直接接收源码字符串与文件名；
- `write_output()` 根据 `format` 和 `output_type` 输出最终结果；
- `write_output_source()` 可写出 `.out` 对应内容；
- `write_scaled_source()` 可写出 `.scaled.tl` 对应内容。

## 作者

Krain

## 开源协议

本项目采用 **MIT License** 开源。

你可以在遵守 MIT License 条款的前提下使用、复制、修改、合并、发布、分发、
再授权和销售本项目的软件副本。

建议在项目根目录提供对应的 `LICENSE` 文件，以便与 README 中的协议说明保持一致。