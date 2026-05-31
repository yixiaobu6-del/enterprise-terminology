"""命令行入口 - 企业术语标准化检查工具"""

import click
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress

from checker import (
    TermLoader,
    TextChecker,
    AutoCorrect,
    CheckResult,
    IssueLevel,
    load_default_terms,
)


console = Console()


@click.group()
@click.version_option("1.0.0")
def cli():
    """企业术语标准化检查工具"""
    pass


def _load_checker(term_file: str = None) -> TextChecker:
    """加载术语表并创建检查器"""
    if term_file:
        path = Path(term_file)
        if path.suffix == ".json":
            terms = TermLoader.load_json(str(path))
        elif path.suffix == ".txt":
            terms = TermLoader.load_text(str(path))
        else:
            raise click.BadParameter(f"不支持的术语表格式: {path.suffix}")
    else:
        terms = load_default_terms()

    return TextChecker(terms)


@cli.command()
@click.argument("files", nargs=-1, type=click.Path(exists=True))
@click.option("--term-file", "-t", type=click.Path(exists=True), help="术语表文件")
@click.option("--json", "output_json", is_flag=True, help="输出JSON格式")
@click.option("--report", "-r", type=click.Path(), help="生成检查报告")
def check(files, term_file, output_json, report):
    """检查文件的术语使用规范

    示例:
        term-check check README.md
        term-check check file1.md file2.md
        term-check check *.md --term-file 术语表.json
    """
    checker = _load_checker(term_file)

    total_issues = 0
    total_files = 0

    for file_path in files:
        total_files += 1
        try:
            result = checker.check_file(file_path)
        except Exception as e:
            console.print(f"[red]检查 {file_path} 失败: {e}[/red]")
            continue

        if output_json:
            import json as json_module
            console.print(json_module.dumps(result.to_dict(), ensure_ascii=False, indent=2))
            continue

        # 显示结果
        if result.is_clean:
            console.print(f"[green]✅ {file_path}：无问题[/green]")
        else:
            console.print(f"\n[bold]{file_path}[/bold]")
            console.print(f"  评分: {result.score}/100")

            for issue in result.issues:
                level_icon = {
                    IssueLevel.ERROR: "[red]❌[/red]",
                    IssueLevel.WARNING: "[yellow]⚠️[/yellow]",
                    IssueLevel.INFO: "[blue]ℹ️[/blue]",
                }.get(issue.level, "•")

                console.print(
                    f"  {level_icon} 第{issue.line}行: "
                    f"[bold]{issue.term}[/bold] - {issue.message}"
                )

            total_issues += len(result.issues)

        # 生成报告
        if report:
            fixer = AutoCorrect(checker)
            report_path = report.format(filename=Path(file_path).stem)
            fixer.generate_report(result, report_path)
            console.print(f"  [green]报告已生成: {report_path}[/green]")

    if total_files > 0:
        console.print(f"\n[bold]总计：检查 {total_files} 个文件，发现 {total_issues} 个问题[/bold]")


@cli.command()
@click.argument("file_path", type=click.Path(exists=True))
@click.option("--term-file", "-t", type=click.Path(exists=True), help="术语表文件")
@click.option("--dry-run", is_flag=True, help="预览模式，不实际修改")
def fix(file_path, term_file, dry_run):
    """自动修正文件中的术语问题

    示例:
        term-check fix README.md
        term-check fix README.md --term-file 术语表.json
        term-check fix README.md --dry-run
    """
    checker = _load_checker(term_file)
    fixer = AutoCorrect(checker)

    if dry_run:
        msg, changes = fixer.correct_file(file_path, dry_run=True)
        if changes > 0:
            console.print(f"[yellow]预览: 将修正 {changes} 处问题[/yellow]")
        else:
            console.print("[green]无需修正[/green]")
    else:
        msg, changes = fixer.correct_file(file_path)
        console.print(msg)


@cli.command("check-dir")
@click.argument("directory", type=click.Path(exists=True))
@click.option("--term-file", "-t", type=click.Path(exists=True), help="术语表文件")
@click.option("--pattern", "-p", multiple=True, help="文件匹配模式")
def check_directory(directory, term_file, pattern):
    """检查目录下所有文件

    示例:
        term-check check-dir ./docs
        term-check check-dir ./docs --pattern *.md --pattern *.txt
    """
    checker = _load_checker(term_file)
    patterns = list(pattern) if pattern else ["*.md", "*.txt", "*.rst"]

    with Progress() as progress:
        task = progress.add_task("[cyan]检查目录...", total=None)

        results = checker.check_directory(directory, patterns)

        progress.update(task, completed=True)

    if not results:
        console.print("[green]目录下所有文件均符合术语规范[/green]")
        return

    total_issues = sum(len(r.issues) for r in results.values())

    console.print(f"\n[bold]{len(results)} 个文件存在问题，共 {total_issues} 项[/bold]\n")

    for file_path, result in sorted(results.items()):
        errors = result.error_count
        warnings = result.warning_count
        infos = result.info_count

        parts = []
        if errors:
            parts.append(f"[red]{errors}个错误[/red]")
        if warnings:
            parts.append(f"[yellow]{warnings}个警告[/yellow]")
        if infos:
            parts.append(f"[blue]{infos}个提示[/blue]")

        console.print(f"  {file_path}: {' '.join(parts)}")


@cli.command()
@click.option("--term-file", "-t", type=click.Path(exists=True), help="术语表文件")
def list_terms(term_file):
    """列出所有术语

    示例:
        term-check list-terms
        term-check list-terms --term-file 术语表.json
    """
    console.print("\n[bold]已加载的术语表[/bold]\n")

    checker = _load_checker(term_file)
    table = Table(show_header=True, header_style="bold")
    table.add_column("标准术语", width=20)
    table.add_column("同义词", width=30)
    table.add_column("禁用词", width=20)
    table.add_column("类别", width=10)

    for standard, term in sorted(checker.terms.items()):
        table.add_row(
            standard,
            ", ".join(term.synonyms) if term.synonyms else "-",
            ", ".join(term.forbidden) if term.forbidden else "-",
            term.category,
        )

    console.print(table)
    console.print(f"\n[bold]共计 {len(checker.terms)} 条术语[/bold]")


@cli.command()
@click.argument("text")
@click.option("--term-file", "-t", type=click.Path(exists=True), help="术语表文件")
def inline(text, term_file):
    """检查单行文本（快速验证）

    示例:
        term-check inline "我们的AI平台使用了大模型技术"
    """
    checker = _load_checker(term_file)
    result = checker.check_text(text)

    if result.is_clean:
        console.print("[green]文本符合术语规范[/green]")
    else:
        console.print("[yellow]发现问题：[/yellow]")
        for issue in result.issues:
            console.print(f"  {issue.message}")


if __name__ == "__main__":
    cli()