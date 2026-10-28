# GMAM 语法规则

## 一、基本元素

GMAM 源文件由三种基本元素组成：

1. **Step**：向时间轴写入代码内容；
2. **表达式**：计算并返回一个值；
3. **定义**：定义变量或宏。

`forstep` 属于 Step：它本身不返回值，而是遍历列表并批量生成
一个或多个 Step。除 `forstep` 外，`for`、赋值、`go`、`look` 等结构
都属于表达式。

## 二、支持的顶层结构

源文件顶层可以按随意顺序写入以下结构：

```text
定义
Step
forstep
表达式;
```

### 2.1 定义

变量定义：

```text
def name = expression
```

宏定义：

```text
def name(parameter, ...) = expression
```

`def` 末尾的分号可写可不写：

```text
def x = 1;
def y = 2
```

### 2.2 Step

Step 必须以分号结束：

```text
{ `code();` } [0];
[0] { `code();` };
```

### 2.3 forstep

`forstep` 只能位于顶层，格式为：

```text
forstep (identifier in listExpression, ...) do {
    stepOrExpression;
    stepOrExpression;
}
```

块内可以包含一个或多个 Step，也可以包含表达式语句。

### 2.4 顶层表达式

顶层表达式必须以分号结束。表达式会被求值，但结果不会直接写入时间轴：

```text
1 + 2;
for (x in {1, 2}) do {x};
```

## 三、Step

### 3.1 Step 格式

Step 由 **content** 和 **positions** 两部分组成，两个部分的顺序可以
互换：

```text
{ content } [ positions ];
[ positions ] { content };
```

示例：

```text
{ `show_debug_message("start");` } [0];
[0, 30, 60] { `show_debug_message("tick");` };
```

### 3.2 Content

content 是一个 Composite 列表，最终会递归展开并拼接为字符串：

```text
[0] { `a();`, `b();` };
```

该 Step 的代码内容为：

```text
a();b();
```


### 3.3 Positions

positions 是一个 Composite 列表，最终会递归展开为多个 moment：

```text
[0, 10, 20] { `tick();` };
```

会生成三个时间点。moment 必须是非负整数。

### 3.4 forstep 中的 Step

`forstep` 的块内支持一个或多个 Step，并支持两种顺序：

```text
forstep (x in {0, 1}) do {
    [x] { `first();` };
    { `second();` } [x + 1];
}
```

块内的 Step 在每次迭代中使用当前绑定变量求值。

## 四、表达式

### 4.1 表达式的返回值

表达式可能返回以下四种值：

1. **数字**：整数或小数；
2. **字符串**：反引号包围的原始字符串；
3. **列表**：由 Composite、区间或 `for` 等结构产生；
4. **NULL**：赋值表达式的返回值。

### 4.2 裸字符串

反引号表示原始字符串：

```text
`instance_create(0, 0, obj_player);`
```

支持的转义包括：

- ``\\``：反斜杠；
- ``\```：反引号；
- `\n`：换行。

### 4.3 数字和算术表达式

数字可以是整数或小数：

```text
1
3.14
```

支持的二元运算：

```text
+  -  *  /  div  mod
```

支持一元运算：

```text
+value
-value
```

示例：

```text
1 + 2 * 3      => 7
7 / 2          => 3.5
7 div 2        => 3
7 mod 2        => 1
-(1 + 2)       => -3
```

规则：

- `/` 为普通除法，可以产生小数；
- `div` 和 `mod` 要求整数操作数；
- 除数不能为 `0`；
- 二元算术运算默认左结合；
- 一元运算支持嵌套。

### 4.4 比较表达式

相等比较：

```text
left == right
```

数字和字符串可以使用 `==`。列表值与非列表值比较时返回 `0`；
列表与列表比较不支持。

数字比较：

```text
left < right
left > right
left <= right
left >= right
```

示例：

```text
1 == 1         => 1
1 == 2         => 0
`a` == `a`     => 1
3 < 5          => 1
3 >= 5         => 0
```

这些运算只支持数字，返回数字 `1` 或 `0`。

### 4.5 条件表达式

格式：

```text
condition ? trueValue : falseValue
```

示例：

```text
x == 0 ? `empty` : `value`
1 ? `yes` : `no`      => `yes`
0 ? `yes` : `no`      => `no`
```

`condition` 必须是数字：值为 `0` 时判定为假，非零值判定为真。
`trueValue` 与 `falseValue` 都是单个表达式，也可以是含花括号的列表表达式。
当条件为真时，返回 `trueValue` 的求值结果；当条件为假时，返回
`falseValue` 的求值结果。

条件表达式的返回类型由实际命中的分支决定。

### 4.6 列表表达式

花括号表示列表：

```text
{1, 2, 3}              => {1, 2, 3}
{`a`, `b`, `c`}        => {`a`, `b`, `c`}
{{1, 2}, {3, 4}}       => {{1, 2}, {3, 4}}
```

列表可以嵌套。列表元素可以是任何表达式。

### 4.7 区间表达式

格式：

```text
begin:difference:end
```

默认不包含结束值；末尾添加 `++` 时包含结束值：

```text
0:20:100        => {0, 20, 40, 60, 80}
0:20:100++      => {0, 20, 40, 60, 80, 100}
```

开始值和步长可以省略：

```text
:1:10           => {0, 1, 2, 3, 4, 5, 6, 7, 8, 9}
2::10           => {2, 3, 4, 5, 6, 7, 8, 9}
::10            => {0, 1, 2, 3, 4, 5, 6, 7, 8, 9}
```

默认开始值为 `0`，默认步长为 `1`。步长不能为 `0`，所有区间参数
必须是数字。

### 4.8 赋值表达式

变量必须先定义，之后才能赋值：

```text
def x = 0
x = x + 1;
```

赋值会修改变量，并返回 `NULL`。`for` 局部变量和宏参数也可以赋值。

### 4.9 for 表达式

`for` 返回列表，格式为：

```text
for (identifier in listExpression, ...) do { expressionList }
```

示例：

```text
for (x in {1, 2, 3}) do {x, x * 10}   => {1, 10, 2, 20, 3, 30}
```

`do` 后必须是 Composite 列表，不能直接写裸表达式。多个来源按位置
配对，长度必须相同：

```text
for (x in {1, 2}, y in {10, 20}) do {x, y}   => {1, 10, 2, 20}
```

来源表达式在外部作用域计算，绑定变量只在 body 内有效。来源列表会
递归展开后遍历；来源也可以是另一个 `for` 表达式。

### 4.10 列表特殊运算

#### `rep`

将列表重复指定次数后拼接：

```text
{1, 2} rep 3
```

结果为：

```text
{1, 2, 1, 2, 1, 2}
```

重复次数必须是自然数，`rep 0` 返回空列表。

#### `flat`

递归展开嵌套列表：

```text
flat {{1, 2}, {3, 4}}
```

结果为：

```text
{1, 2, 3, 4}
```

`flat` 也可以展开区间和 `for` 表达式产生的列表。

#### 列表算术

列表可以和数字广播运算：

```text
{1, 2, 3} + 10        => {11, 12, 13}
```

两个列表可以按位置运算，但长度必须相同：

```text
{1, 2, 3} * {2, 3, 4} => {2, 6, 12}
```

一元 `+`、`-` 也会递归作用于列表：

```text
-{1, {2, 3}}          => {-1, {-2, -3}}
```

### 4.11 表达式优先级

从高到低大致为：

```text
括号
一元 + - flat
* / div mod rep
+ -
== < > <= >=
?:
区间
赋值
```

括号可以改变优先级：

```text
(1 + 2) * 3      => 9
1 + 2 * 3        => 7
```

## 五、定义

### 5.1 标识符和作用域

标识符首字符可以是字母或 `_`，后续字符可以是字母、数字或 `_`。
变量和宏不能重名。

宏参数和 `for` 绑定变量只在各自的局部作用域中有效，并会遮蔽外部
同名变量。

### 5.2 变量定义

```text
def start = 0
def name = `player`
```

变量定义的分号可写可不写。

### 5.3 宏定义和调用

定义：

```text
def add(a, b) = a + b
def scale(x, n = 2) = x * n
```

调用：

```text
add(1, 2)
scale(3)
scale(x = 3, n = 4)
```

参数可以按位置传递，也可以使用参数名。默认参数必须位于参数列表
末尾。

调用参数会在调用者作用域中先求值，再绑定到宏参数。

### 5.4 内置变量

编译器自动提供：

| 名称 | 默认值 | 说明 |
| --- | ---: | --- |
| `TIME` | `0` | 当前时间指针 |
| `BPM` | `120` | 音乐 BPM |
| `NOTE_PER_BEAT` | `4` | 几分音符为一拍 |
| `TLSTEP_PER_BEAT` | `8` | 一拍对应的 timeline step 数量 |

内置变量可以读取和赋值，但不能使用 `def` 重定义。

## 六、时间控制

### 6.1 TIME

`TIME` 初始值为 `0`，可以读取和手动赋值。

### 6.2 go 和 look

格式：

```text
go(number, note)
look(number, note)
```

第一个参数 `number` 支持数字或数字列表，第二个参数 `note` 必须是正数，表示几分音符。
用于求得：当前 `TIME` 往后数 `number` 个 `note` 分音符后，`TIME` 的值。

- `go` 返回数字或列表，并将 `TIME` 更新为结果中的最大值；
- `look` 返回数字或列表，但不修改 `TIME`。

示例：

```text
look(1, 4)        => 8
TIME              => 0

go(1, 4)          => 8
TIME              => 8

look({0, 1, 2}, 8) => {8, 12, 16}
TIME               => 8

go({0, 1, 2}, 8)   => {8, 12, 16}
TIME               => 16
```

以上示例基于默认值：`TIME = 0`、`NOTE_PER_BEAT = 4`、`TLSTEP_PER_BEAT = 8`。
其中四分音符对应 `8` 个 step，八分音符对应 `4` 个 step。


在 `timeline` 模式下计算每个 `note` 分音符对应的 step 数量：

```text
TLSTEP_PER_BEAT * NOTE_PER_BEAT / note
```

在 `step` 或 `txt` 模式下计算每个 `note` 分音符对应的 step 数量：

```text
50 * 60 / BPM * NOTE_PER_BEAT / note
```

go 和 look 的结果：

```text
TIME + number 中的值 * 每个 note 对应的 step
```

### 6.3 timeline 模式自适应 TLSTEP_PER_BEAT

只有在 `timeline` 模式下，`go/look` 计算出非整数时间时，才触发自适应处理。
推荐值为：

```text
lcm(所有 go/look 的 note) / NOTE_PER_BEAT
```

询问模式还会显示第二个推荐值：

```text
第一推荐值 * 原 TLSTEP_PER_BEAT
```

第二个值适合手动输入过具体时间的情况。

相关命令行参数--time-scale：

- `ask`：询问是否调整，再询问目标值；直接回车使用第一推荐值；
- `adjust`：使用第一推荐值，并整体放缩 moment 以保持对应现实时间不变；
- `round`：不调整 `TLSTEP_PER_BEAT`，最终对非整数 moment 四舍五入。

`timeline` 模式忽略 `BPM`。

### 6.4 step / txt 模式


- 忽略 `TLSTEP_PER_BEAT`；
- 忽略 `--time-scale`；
- 计算过程中不提前四舍五入；
- 只在最终输出 moment 时四舍五入。

两者输出形式不同：

- `step`：写入现有工程的 object 的 Step 事件；
- `txt`：直接输出纯文本 Step 代码。

### 6.5 计算结果文件

无论输出格式和时间缩放策略如何，命令行都会生成最后一个输入文件名
对应的 `.out` 文件：

```text
[0, 1, 2] {`计算完毕的字符串`};
```

`adjust` 实际生效时还会生成 `.scaled.tl`：

```text
TLSTEP_PER_BEAT = 3;
[0, 1, 2] {`已计算的内容`};
```

## 七、注释与报错

### 7.1 注释

支持两种注释：

```text
// 单行注释
/* 多行注释 */
```

示例：

```text
// 这是一行注释
[0] {`a();`};

/* 这是一段
   多行注释 */
[1] {`b();`};
```

注释不会参与求值，也不会写入输出结果。

### 7.2 报错格式

单文件输入时：

```text
行:列: 错误信息 (element: 相关元素值)
```

多文件输入时：

```text
文件名:行:列: 错误信息 (element: 相关元素值)
```

示例：

```text
1:15: division by zero (element: 'number=0')
a.tl:3:8: undefined identifier x (element: "IDENTIFIER='x'")
```

错误会尽量显示相关 token、变量名、操作数或实际求值结果；
其中 `element` 用于帮助定位触发错误的直接对象。

### 7.3 词法错误

常见词法错误包括：

- 非法字符；
- 未闭合的反引号字符串；
- 未闭合的多行注释；
- 小数点后缺少数字。

示例：

```text
`abc
```

可能报错：

```text
1:5: unterminated raw string
```

### 7.4 语法错误

常见语法错误包括：

- 缺少括号、方括号或花括号；
- 缺少必须的分号；
- Step 缺少 content 或 positions；
- `forstep` 块为空；
- `forstep` 块缺少结束花括号；
- `for` 或 `forstep` 绑定格式错误。

示例：

```text
def x = (1 + );
```

可能报错：

```text
1:14: expected an expression (element: "RPAREN=')'")
```

### 7.5 语义错误

常见语义错误包括：

- 未定义变量或宏；
- 重复定义；
- 变量、列表和数字类型不匹配；
- 除零；
- 区间步长为 `0`；
- `go/look` 参数不合法；
- `for` / `forstep` 来源长度不一致；
- moment 为负数或无法转换为整数。

示例：

```text
1 div 0;
```

可能报错：

```text
1:7: division by zero (element: 'number=0')
```

### 7.6 行列号与文件定位

错误位置支持跨行源文件，并正确处理：

- `\n`；
- `\r\n`；
- `\r`。

多文件输入时，报错会指向**实际出错的那个文件**，而不是简单指向最后一个输入文件。
这对把变量定义、宏定义和主逻辑拆分到多个 `.tl` 文件中的写法尤其重要。
