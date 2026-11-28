# Schema Boundary：用具体JSON说明接口破坏

给定旧、新两份JSON Schema，寻找“旧版接受、新版拒绝”的真实JSON输入。面向AI工具参数、结构化输出和API契约变更；每份反例经过序列化并由独立jsonschema验证器复核。

**这是有界检查器，不是全域兼容证明器，也不能保证世界领先。** 没找到反例必须连同整数范围、字符表、长度、深度、键名范围一起看。默认仅生成整数数值，不覆盖小数实例。

## 运行

从源码目录安装，Python3.10+：

```sh
python -m pip install .
python -m schema_boundary compare examples/search.old.json examples/search.new.json --domain examples/domain.json --output review-case
```

退出1代表发现破坏性反例，是本合成示例的预期结果。打开`review-case/report.html`看报告、`witness.json`看实际输入。输出目录必须不存在，不会覆盖已有结果。

- `counterexample` / 1：具体JSON旧版通过、新版失败。
- `bounded-compatible` / 3：只在声明有限域内没有反例，不能称全域兼容。必须显式传`--accept-bounded`才退出0。
- `empty-source` / 4：源约束在该域内无解，不拿真空蕴含做绿灯。
- `unknown` / 2：不支持、预算耗尽、求解未知或独立复核不一致。
- `error` / 2：输入/参数/文件错误。

正向对照把目标换成`examples/search.relaxed.json`；不支持路径用`examples/unsupported.json`。案例全部自制，不是假装真实厂商事故。

## 范围与质量

支持2020-12的布尔schema、类型、const/enum、数值边界和multipleOf、字符串长度、同构items数组、properties/required/additionalProperties、数量限制、allOf/anyOf/oneOf/not。不支持正则、引用、format、unevaluated*等时明确unknown，不静默忽略。解析小数采用Decimal，整数语义的0.0归一为0；true与1不混淆。

预算：1MiB输入、32层/4000结构节点、12个键、3000符号节点、25000共享编译工作单位。solver超时不是全流程墙钟上限。实际范围和测试结果见[英文说明](README.md)、[验收记录](docs/VERIFICATION.md)。

```sh
python -m unittest discover -s tests -v
python tools/verify_mutations.py
```

项目无网络/模型调用；报告不回显schema注释，但属性名和反例字面量也可能敏感，分享前需检查。未发布PyPI；不要自行安装同名未知包。当前提供源码与本地安装包，不预造上线链接。

## 快速开始与支持状态

### 问题
找到一个被源 schema 接受、被目标 schema 拒绝的具体 JSON 值，并附带有限搜索域。

### 安装
```sh
python -m pip install .
```

### 成功命令
```sh
schema-boundary compare examples/search.old.json examples/search.relaxed.json --domain examples/domain.json --accept-bounded
```
预期：由于显式使用 --accept-bounded，有界兼容结果被接受；退出码 0。

### 故意失败命令
```sh
schema-boundary compare examples/search.old.json examples/search.new.json --domain examples/domain.json --output review-case
```
预期：序列化反例经过独立复检，命令退出码 1。

### 证据与覆盖边界
证据包括独立 jsonschema 重放、微型域谓词穷举、成对枚举决策、真实 Z3 资源耗尽、错误解码 witness 对照，以及选定的官方语料库检查。求解器 UNSAT 只表示在打印域内有界兼容，绝不是通用 schema 包含证明。

### 支持状态
版本 0.1.0 是面向 Python 3.10+ 的实验性有界检查器。源码快照表明尚未发布到 PyPI；请安装经审查的检出或源码分发包。维护为尽力而为，不提供 SLA。

### 限制
默认域使用深度 2、数组 0..2、字符串 0..8 个码点、整数 -16..16 和解析后的对象键。不支持小数实例、$ref、pattern、format、网络解析及许多其他关键字；这些情况产生 unknown，不会静默成功。
