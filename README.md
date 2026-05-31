# 企业术语标准化检查工具

用于检查企业文档中的术语使用是否规范，确保内部沟通和对外输出的一致性。

## 功能特性

- **同义词检测**：识别并纠正使用了同义词（非标准术语）的情况
- **禁用词检测**：检测并标记企业禁止使用的词汇
- **自动修正**：一键替换不规范术语为标准术语
- **批量检查**：支持单个文件、目录批量检查
- **报告生成**：输出详细检查报告

## 安装

```bash
pip install term-standard-checker
```

## 快速开始

### 检查文件

```bash
# 使用默认术语表
term-check check README.md

# 使用自定义术语表
term-check check document.md --term-file 术语表.json

# 检查多个文件
term-check check file1.md file2.md file3.md
```

### 检查目录

```bash
term-check check-dir ./docs --pattern *.md
```

### 自动修正

```bash
# 预览模式
term-check fix README.md --dry-run

# 实际修正
term-check fix README.md
```

## 术语表格式

### JSON 格式（推荐）

```json
{
  "术语表": [
    {
      "标准术语": "人工智能",
      "同义词": ["AI", "人工智能技术"],
      "禁用词": ["人工智障"],
      "类别": "技术",
      "说明": "通过计算机模拟人类智能的技术"
    }
  ]
}
```

### 文本格式

```
# 标准术语|同义词1,同义词2|禁用词1,禁用词2|类别
人工智能|AI,人工智能技术|人工智障|技术
数字化转型|数智化,数字化升级|上系统就行,一键数字化|业务
```

## 使用示例

```python
from checker import TextChecker, load_default_terms

# 使用默认术语表
checker = TextChecker(load_default_terms())

# 检查文本
result = checker.check_text("我们的AI平台使用了大模型技术")

if result.is_clean:
    print("术语规范！")
else:
    for issue in result.issues:
        print(f"第{issue.line}行: {issue.message}")

# 检查文件
result = checker.check_file("document.md")
print(f"评分: {result.score}/100")
```

## CLI 命令

| 命令 | 说明 | 示例 |
|------|------|------|
| `check` | 检查文件 | `term-check check README.md` |
| `check-dir` | 检查目录 | `term-check check-dir ./docs` |
| `fix` | 自动修正 | `term-check fix README.md` |
| `list-terms` | 列出术语 | `term-check list-terms` |
| `inline` | 快速验证 | `term-check inline "这里填文本"` |

## 内置示例术语表

| 标准术语 | 类别 | 可接受的同义词 | 禁用词 |
|----------|------|---------------|--------|
| 人工智能 | 技术 | AI, 人工智能技术, 智能算法 | 人工智障 |
| 大语言模型 | 技术 | 大模型, LLM, 语言大模型 | AI大脑 |
| 数字化转型 | 业务 | 数智化, 数字化升级 | 上系统就行, 一键数字化 |
| 降本增效 | 管理 | 降本提效, 降本增质 | 裁员增效, 砍成本 |
| 私有化部署 | 技术 | 私有部署, 本地部署, On-Premises | 自己装 |
| 数据驱动 | 管理 | 数据导向, 基于数据的 | 纯数据决策, 数据万能 |

## 项目结构

```
企业术语标准化检查/
├── README.md
├── checker.py      # 核心检查逻辑
├── cli.py          # 命令行入口
└── 术语表.json     # 示例术语表
```

## 许可证

MIT License