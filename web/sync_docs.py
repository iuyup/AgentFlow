#!/usr/bin/env python3
"""
sync_docs.py - 从 patterns/ 目录同步文档到 web/docs/patterns/

用法: python sync_docs.py
"""

from pathlib import Path

PATTERNS_DIR = Path(__file__).parent.parent / "patterns"
OUTPUT_DIR = Path(__file__).parent / "docs" / "patterns"

PATTERNS = [
    "reflection",
    "debate",
    "map_reduce",
    "hierarchical",
    "voting",
    "guardrail",
    "rag_agent",
    "chain_of_experts",
    "human_in_the_loop",
    "swarm",
]


def process_readme(readme_path: Path, output_path: Path, lang: str):
    """处理单个 README 文件"""
    if not readme_path.exists():
        print(f"警告: {readme_path} 不存在,跳过")
        return

    content = readme_path.read_text(encoding="utf-8")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    print(f"生成: {output_path}")


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for pattern in PATTERNS:
        pattern_dir = PATTERNS_DIR / pattern

        # 英文版
        en_readme = pattern_dir / "README.md"
        en_output = OUTPUT_DIR / f"{pattern}.md"
        process_readme(en_readme, en_output, "en")

        # 中文版
        zh_readme = pattern_dir / "README_zh.md"
        zh_output = OUTPUT_DIR / f"{pattern}_zh.md"
        process_readme(zh_readme, zh_output, "zh")

    print(f"\n同步完成! 生成了 {len(PATTERNS) * 2} 个文档文件")


if __name__ == "__main__":
    main()
