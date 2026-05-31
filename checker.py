"""企业术语标准化检查工具

检查文本中的用词是否符合企业术语规范。
支持术语同义词替换、禁用词检测、术语一致性检查。
"""

import json
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any


class IssueLevel(Enum):
    """问题等级"""
    ERROR = "error"       # 必须修复
    WARNING = "warning"   # 建议修复
    INFO = "info"         # 提示信息


@dataclass
class Term:
    """术语条目"""
    standard: str                # 标准术语
    synonyms: List[str]          # 同义词（可接受）
    forbidden: List[str]         # 禁用词
    category: str                # 类别
    description: str = ""        # 说明
    context_pattern: Optional[str] = None  # 上下文匹配正则
    severity_if_violated: IssueLevel = IssueLevel.WARNING

    def matches_synonym(self, text: str) -> bool:
        """检查文本是否使用了同义词"""
        for syn in self.synonyms:
            if syn.lower() in text.lower():
                return True
        return False

    def matches_forbidden(self, text: str) -> bool:
        """检查文本是否使用了禁用词"""
        for word in self.forbidden:
            if word.lower() in text.lower():
                return True
        return False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "standard": self.standard,
            "synonyms": self.synonyms,
            "forbidden": self.forbidden,
            "category": self.category,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Term":
        return cls(
            standard=data["标准术语"],
            synonyms=data.get("同义词", []),
            forbidden=data.get("禁用词", []),
            category=data.get("类别", "通用"),
            description=data.get("说明", ""),
        )


@dataclass
class Issue:
    """检查发现的问题"""
    level: IssueLevel
    line: int
    column: int
    term: str
    message: str
    suggestion: str
    original: str
    replacement: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "level": self.level.value,
            "line": self.line,
            "column": self.column,
            "term": self.term,
            "message": self.message,
            "suggestion": self.suggestion,
            "original": self.original,
            "replacement": self.replacement,
        }


@dataclass
class CheckResult:
    """检查结果"""
    file_path: str
    issues: List[Issue] = field(default_factory=list)
    term_usage: Dict[str, int] = field(default_factory=dict)
    score: int = 100
    total_terms_found: int = 0

    @property
    def error_count(self) -> int:
        return len([i for i in self.issues if i.level == IssueLevel.ERROR])

    @property
    def warning_count(self) -> int:
        return len([i for i in self.issues if i.level == IssueLevel.WARNING])

    @property
    def info_count(self) -> int:
        return len([i for i in self.issues if i.level == IssueLevel.INFO])

    @property
    def is_clean(self) -> bool:
        return len(self.issues) == 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file_path": self.file_path,
            "score": self.score,
            "total_issues": len(self.issues),
            "errors": self.error_count,
            "warnings": self.warning_count,
            "infos": self.info_count,
            "issues": [i.to_dict() for i in self.issues],
            "term_usage": self.term_usage,
            "total_terms_found": self.total_terms_found,
        }


class TermLoader:
    """术语载入器"""

    @staticmethod
    def load_json(path: str) -> Dict[str, Term]:
        """从JSON文件加载术语表"""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        terms = {}
        for item in data.get("术语表", []):
            term = Term.from_dict(item)
            terms[term.standard] = term

        return terms

    @staticmethod
    def load_jsonl(path: str) -> Dict[str, Term]:
        """从JSONL文件加载"""
        terms = {}
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    item = json.loads(line)
                    term = Term.from_dict(item)
                    terms[term.standard] = term
        return terms

    @staticmethod
    def load_text(path: str) -> Dict[str, Term]:
        """从文本文件加载（每行：标准术语|同义词1,同义词2|禁用词1,禁用词2|类别）"""
        terms = {}
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split("|")
                if len(parts) >= 1:
                    term = Term(
                        standard=parts[0].strip(),
                        synonyms=[s.strip() for s in parts[1].split(",")] if len(parts) > 1 else [],
                        forbidden=[w.strip() for w in parts[2].split(",")] if len(parts) > 2 else [],
                        category=parts[3].strip() if len(parts) > 3 else "通用",
                    )
                    terms[term.standard] = term
        return terms


class TextChecker:
    """文本检查器"""

    def __init__(self, terms: Dict[str, Term]):
        self.terms = terms
        self.term_cache: Dict[str, List[re.Pattern]] = {}

        # 预编译正则
        self._compile_patterns()

    def _compile_patterns(self):
        """预编译正则表达式"""
        for standard, term in self.terms.items():
            patterns = []
            # 同义词正则
            if term.synonyms:
                syn_pattern = "|".join(re.escape(s) for s in term.synonyms)
                patterns.append(("synonym", re.compile(syn_pattern, re.IGNORECASE)))
            # 禁用词正则
            if term.forbidden:
                forbid_pattern = "|".join(re.escape(w) for w in term.forbidden)
                patterns.append(("forbidden", re.compile(forbid_pattern, re.IGNORECASE)))
            self.term_cache[standard] = patterns

    def check_file(self, file_path: str, encoding: str = "utf-8") -> CheckResult:
        """检查文件"""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")

        content = path.read_text(encoding=encoding)
        return self.check_text(content, file_path)

    def check_text(self, text: str, file_path: str = "<text>") -> CheckResult:
        """检查文本内容"""
        result = CheckResult(file_path=file_path)

        lines = text.split("\n")
        term_usage: Dict[str, int] = {}

        for line_num, line in enumerate(lines, 1):
            # 跳过空行和注释行
            if not line.strip() or line.strip().startswith("#"):
                continue

            for standard, patterns in self.term_cache.items():
                term = self.terms[standard]

                for pattern_type, pattern in patterns:
                    matches = list(pattern.finditer(line))
                    if not matches:
                        continue

                    result.total_terms_found += 1
                    term_usage[standard] = term_usage.get(standard, 0) + 1

                    for match in matches:
                        matched_text = match.group()
                        col = match.start() + 1

                        if pattern_type == "synonym":
                            issue = Issue(
                                level=term.severity_if_violated,
                                line=line_num,
                                column=col,
                                term=standard,
                                message=f"使用了同义词「{matched_text}」，建议替换为标准术语「{standard}」",
                                suggestion=f"将「{matched_text}」替换为「{standard}」",
                                original=matched_text,
                                replacement=standard,
                            )
                            result.issues.append(issue)

                        elif pattern_type == "forbidden":
                            issue = Issue(
                                level=IssueLevel.ERROR,
                                line=line_num,
                                column=col,
                                term=standard,
                                message=f"使用了禁用词「{matched_text}」",
                                suggestion=f"删除或替换为「{standard}」",
                                original=matched_text,
                                replacement=standard,
                            )
                            result.issues.append(issue)

        result.term_usage = term_usage

        # 计算评分
        if result.issues:
            score = 100
            for issue in result.issues:
                if issue.level == IssueLevel.ERROR:
                    score -= 10
                elif issue.level == IssueLevel.WARNING:
                    score -= 5
                else:
                    score -= 2
            result.score = max(0, score)

        return result

    def check_directory(
        self,
        directory: str,
        patterns: List[str] = None,
        recursive: bool = True,
    ) -> Dict[str, CheckResult]:
        """检查目录下所有匹配的文件"""
        if patterns is None:
            patterns = ["*.md", "*.txt", "*.rst"]

        base = Path(directory)
        if not base.exists():
            raise FileNotFoundError(f"目录不存在: {directory}")

        results = {}
        for pattern in patterns:
            search_method = base.rglob if recursive else base.glob
            for file_path in search_method(pattern):
                try:
                    result = self.check_file(str(file_path))
                    if result.issues:  # 只记录有问题的文件
                        results[str(file_path)] = result
                except Exception as e:
                    results[str(file_path)] = CheckResult(
                        file_path=str(file_path),
                        issues=[Issue(
                            level=IssueLevel.ERROR,
                            line=0,
                            column=0,
                            term="",
                            message=f"文件读取失败: {e}",
                            suggestion="",
                            original="",
                        )],
                        score=0,
                    )

        return results


class AutoCorrect:
    """自动修正工具"""

    def __init__(self, checker: TextChecker):
        self.checker = checker

    def correct_file(self, file_path: str, dry_run: bool = False) -> Tuple[str, int]:
        """自动修正文件中的术语问题"""
        result = self.checker.check_file(file_path)

        if not result.issues:
            return "无问题，无需修正", 0

        path = Path(file_path)
        content = path.read_text(encoding="utf-8")

        changes = 0
        lines = content.split("\n")

        for issue in reversed(result.issues):
            if issue.line > 0 and issue.line <= len(lines):
                line = lines[issue.line - 1]
                if issue.replacement:
                    new_line = line.replace(issue.original, issue.replacement)
                    if new_line != line:
                        lines[issue.line - 1] = new_line
                        changes += 1

        if not dry_run and changes > 0:
            new_content = "\n".join(lines)
            path.write_text(new_content, encoding="utf-8")
            return f"已修正 {changes} 处问题", changes

        return f"预览: 将修正 {changes} 处问题", changes

    def generate_report(self, check_result: CheckResult, output_path: str):
        """生成检查报告"""
        report_lines = [
            "# 术语检查报告",
            "",
            f"**文件：** {check_result.file_path}",
            f"**评分：** {check_result.score}/100",
            f"**总计：** {len(check_result.issues)} 个问题 "
            f"({check_result.error_count} 个错误, "
            f"{check_result.warning_count} 个警告, "
            f"{check_result.info_count} 个提示)",
            "",
            "## 问题详情",
            "",
        ]

        for i, issue in enumerate(check_result.issues, 1):
            level_icon = {
                IssueLevel.ERROR: "❌",
                IssueLevel.WARNING: "⚠️",
                IssueLevel.INFO: "ℹ️",
            }.get(issue.level, "•")

            report_lines.append(f"### {i}. {level_icon} [{issue.level.value}] {issue.term}")
            report_lines.append("")
            report_lines.append(f"- **位置：** 第 {issue.line} 行，第 {issue.column} 列")
            report_lines.append(f"- **原始文本：** `{issue.original}`")
            report_lines.append(f"- **问题描述：** {issue.message}")
            report_lines.append(f"- **修改建议：** {issue.suggestion}")
            if issue.replacement:
                report_lines.append(f"- **推荐替换：** `{issue.replacement}`")
            report_lines.append("")

        report_lines.append("## 术语使用统计")
        report_lines.append("")
        report_lines.append("| 标准术语 | 出现次数 |")
        report_lines.append("|----------|----------|")
        for term, count in sorted(check_result.term_usage.items(), key=lambda x: -x[1]):
            report_lines.append(f"| {term} | {count} |")

        report = "\n".join(report_lines)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(report)


def load_default_terms() -> Dict[str, Term]:
    """加载内置示例术语表"""
    terms_data = {
        "人工智能": Term(
            standard="人工智能",
            synonyms=["AI", "人工智能技术", "智能算法"],
            forbidden=["人工智障"],
            category="技术",
            description="通过计算机模拟人类智能的技术",
        ),
        "大语言模型": Term(
            standard="大语言模型",
            synonyms=["大模型", "LLM", "语言大模型"],
            forbidden=["AI大脑"],
            category="技术",
            description="基于海量文本数据训练的大型语言模型",
        ),
        "数字化转型": Term(
            standard="数字化转型",
            synonyms=["数智化", "数字化升级", "企业数字化"],
            forbidden=["上系统就行", "一键数字化"],
            category="业务",
            description="利用数字技术重构业务流程和管理体系",
        ),
        "降本增效": Term(
            standard="降本增效",
            synonyms=["降本提效", "降本增质", "降本提质增效"],
            forbidden=["裁员增效", "砍成本"],
            category="管理",
        ),
        "数据驱动": Term(
            standard="数据驱动",
            synonyms=["数据导向", "基于数据的"],
            forbidden=["纯数据决策", "数据万能"],
            category="管理",
        ),
        "私有化部署": Term(
            standard="私有化部署",
            synonyms=["私有部署", "本地部署", "On-Premises"],
            forbidden=["自己装"],
            category="技术",
        ),
    }
    return terms_data