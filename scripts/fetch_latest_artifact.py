#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
本地最新安装包/脚本选择工具。

场景：
- 服务器某目录下有多个版本的安装包或脚本（例如 app-4.1.sh、app-4.1.3.sh 等），
  研发不能登录服务器，希望运维通过一个简单脚本，每次帮他们选出“版本号最大的那个”，
  并在当前目录导出为一个固定文件名（如 latest.sh / latest.tar.gz）。

特点：
- 仅依赖 Python 标准库。
- 只处理本地目录，不访问网络。
- 版本比较规则：按“点分数字”比较，例如 4.1.3 > 4.1，4.10 > 4.2.9。
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional, Pattern


# ========================
#  版本号数据结构与比较
# ========================


@dataclass(frozen=True, order=True)
class Version:
    parts: tuple[int, ...]

    @staticmethod
    def parse(text: str) -> "Version":
        """从字符串解析版本号，支持前缀 v / V。"""
        s = text.strip()
        if s.startswith(("v", "V")):
            s = s[1:]
        if not s:
            raise ValueError("empty version")

        nums: list[int] = []
        for seg in s.split("."):
            if not seg or not seg.isdigit():
                raise ValueError(f"invalid version segment: {seg!r} in {text!r}")
            nums.append(int(seg))

        # 去掉末尾多余的 0，使 4.1 == 4.1.0
        while nums and nums[-1] == 0:
            nums.pop()
        return Version(tuple(nums))

    def padded(self, n: int) -> tuple[int, ...]:
        """尾部补 0 以便比较不同长度的版本号。"""
        if len(self.parts) >= n:
            return self.parts
        return self.parts + (0,) * (n - len(self.parts))

    def __str__(self) -> str:
        return ".".join(str(x) for x in self.parts) if self.parts else "0"


def cmp_versions(a: Version, b: Version) -> int:
    n = max(len(a.parts), len(b.parts), 1)
    pa = a.padded(n)
    pb = b.padded(n)
    return (pa > pb) - (pa < pb)


# ========================
#  文件名中提取版本号
# ========================


DEFAULT_VERSION_REGEX = r"(?i)(?:^|[^0-9])v?(\d+(?:\.\d+)+)(?:[^0-9]|$)"


def extract_version(name: str, version_regex: Pattern[str]) -> Optional[Version]:
    """从文件名中提取版本号，提取失败返回 None。"""
    m = version_regex.search(name)
    if not m:
        return None
    try:
        return Version.parse(m.group(1))
    except ValueError:
        return None


# ========================
#  本地候选文件收集
# ========================


@dataclass(frozen=True)
class Candidate:
    name: str        # 文件名
    version: Version
    source_ref: str  # 本地绝对路径


def list_local_candidates(
    source_dir: Path,
    name_regex: Pattern[str],
    version_regex: Pattern[str],
) -> list[Candidate]:
    """在本地目录中筛选出包含可解析版本号的候选文件。"""
    out: list[Candidate] = []
    for p in source_dir.iterdir():
        if not p.is_file():
            continue
        name = p.name
        if not name_regex.search(name):
            continue
        v = extract_version(name, version_regex)
        if not v:
            continue
        out.append(
            Candidate(
                name=name,
                version=v,
                source_ref=str(p.resolve()),
            )
        )
    return out


def pick_latest(candidates: Iterable[Candidate]) -> Candidate:
    """从候选列表中选出版本号最大的那个。"""
    best: Optional[Candidate] = None
    for c in candidates:
        if best is None:
            best = c
            continue
        cmp = cmp_versions(c.version, best.version)
        if cmp > 0:
            best = c
        elif cmp == 0 and c.name > best.name:
            # 同版本号，用文件名作稳定的次级比较
            best = c
    if best is None:
        raise RuntimeError("no candidates")
    return best


# ========================
#  输出文件名与安全写入
# ========================


def default_latest_name(chosen_name: str) -> str:
    """
    根据原始文件名推断默认输出名 latest.xxx。

    - 处理多段后缀（.tar.gz / .tar.bz2 / .tgz 等） -> latest.tar.gz
    - 其他情况只取最后一个后缀（.sh / .zip） -> latest.sh / latest.zip
    - 无后缀时 -> latest
    """
    lower = chosen_name.lower()
    multi_exts = (
        ".tar.gz",
        ".tar.bz2",
        ".tar.xz",
        ".tar.zst",
        ".tar.lz4",
        ".tgz",
        ".tbz2",
        ".txz",
    )
    for ext in multi_exts:
        if lower.endswith(ext):
            return f"latest{ext}"

    suffix = Path(chosen_name).suffix  # 只取最后一段
    if suffix and not suffix[1:].isdigit():
        return f"latest{suffix}"
    return "latest"


def atomic_write_from_stream(
    dest_path: Path,
    stream,
    chmod_mode: Optional[int] = None,
) -> None:
    """使用临时文件 + 原子替换的方式安全写入目标文件。"""
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        prefix=".tmp.",
        dir=str(dest_path.parent),
        delete=False,
    ) as tf:
        tmp_path = Path(tf.name)
        shutil.copyfileobj(stream, tf)
        tf.flush()
        os.fsync(tf.fileno())
    os.replace(str(tmp_path), str(dest_path))
    if chmod_mode is not None:
        try:
            os.chmod(dest_path, chmod_mode)
        except OSError:
            # 权限设置失败不影响“拿到最新版文件”的主目标
            pass


def copy_local_to(dest_path: Path, src_path: Path) -> None:
    """从本地文件复制到目标文件，尽量继承源文件权限。"""
    try:
        src_mode = src_path.stat().st_mode & 0o777
    except OSError:
        src_mode = 0o644
    with open(src_path, "rb") as fsrc:
        atomic_write_from_stream(dest_path, fsrc, chmod_mode=src_mode)


# ========================
#  主流程
# ========================


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="fetch_latest_artifact.py",
        formatter_class=argparse.RawTextHelpFormatter,
        description=(
            "从本地目录中，按版本号获取最新版文件。\n"
            "默认版本号正则：提取 v4.1.3 / 4.1.3 这类（必须包含至少一个点）。"
        ),
    )
    parser.add_argument(
        "--source",
        required=True,
        help="本地目录路径（服务器上的安装包目录）",
    )
    parser.add_argument(
        "--name-regex",
        default=r".*",
        help=(
            "候选文件名过滤正则（先过滤，再提取版本）。\n"
            r"例如: 'app-.*\.sh$' 或 'app-.*\.tar\.gz$'"
        ),
    )
    parser.add_argument(
        "--version-regex",
        default=DEFAULT_VERSION_REGEX,
        help=(
            "从文件名提取版本号的正则（需要有一个捕获组，返回类似 4.1.3）。\n"
            f"默认: {DEFAULT_VERSION_REGEX}"
        ),
    )
    parser.add_argument(
        "--dest",
        default=".",
        help="输出目录（默认当前目录）",
    )
    parser.add_argument(
        "--output",
        default="",
        help="输出文件名。不指定时，根据源文件后缀自动生成 latest.xxx。",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只打印要选中的最新版及目标路径，不实际复制文件",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="打印候选列表与解析详情",
    )

    args = parser.parse_args(argv)

    try:
        name_re = re.compile(args.name_regex)
    except re.error as e:
        print(f"错误：--name-regex 非法：{e}", file=sys.stderr)
        return 2

    try:
        ver_re = re.compile(args.version_regex)
    except re.error as e:
        print(f"错误：--version-regex 非法：{e}", file=sys.stderr)
        return 2

    source_dir = Path(args.source).expanduser()
    if not source_dir.exists():
        print(f"错误：本地路径不存在：{source_dir}", file=sys.stderr)
        return 2
    if not source_dir.is_dir():
        print(f"错误：--source 必须是目录：{source_dir}", file=sys.stderr)
        return 2

    candidates = list_local_candidates(source_dir, name_re, ver_re)

    if args.verbose:
        print(f"候选数量：{len(candidates)}")
        for c in sorted(candidates, key=lambda x: (x.version.parts, x.name)):
            print(f"- {c.name}  version={c.version}  from={c.source_ref}")

    if not candidates:
        print(
            "没有找到任何候选文件。请检查：\n"
            "- source 目录是否正确且有文件\n"
            "- --name-regex 是否过于严格\n"
            "- 文件名中是否包含可提取的版本号（例如 4.1.3）",
            file=sys.stderr,
        )
        return 1

    best = pick_latest(candidates)
    print(f"选中最新版：{best.name}（version={best.version}）")
    print(f"来源：{best.source_ref}")

    dest_dir = Path(args.dest).expanduser().resolve()
    output_name = args.output.strip() or default_latest_name(best.name)
    output_path = dest_dir / output_name

    if args.dry-run:
        print(f"[dry-run] 将写入：{output_path}")
        return 0

    copy_local_to(output_path, Path(best.source_ref))
    print(f"已写入：{output_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

