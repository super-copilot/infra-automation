#!/usr/bin/env python3

import argparse
import re
import sys
from pathlib import Path


# 匹配文件名中的版本号，例如:
# app-2.1.2.tar.gz -> 2.1.2
# app_v5.10.rpm -> 5.10
VERSION_RE = re.compile(r"(?<!\d)v?(\d+(?:\.\d+)+)(?!\d)")


def extract_version(filename: str):
    """从文件名中提取版本号，并转成可比较的整数元组。"""
    matches = list(VERSION_RE.finditer(filename))
    if not matches:
        return None

    # 版本号通常更靠近文件名末尾，取最后一个匹配结果更稳妥。
    version_str = matches[-1].group(1)
    return tuple(int(part) for part in version_str.split("."))


def find_latest_package(directory: Path, keyword: str | None = None):
    """在目录中查找最新安装包，必要时可按关键字过滤。"""
    candidates = []

    for file_path in directory.iterdir():
        if not file_path.is_file():
            continue

        if keyword and keyword not in file_path.name:
            continue

        version = extract_version(file_path.name)
        if version is None:
            continue

        # 版本相同的情况下，用修改时间兜底。
        candidates.append((version, file_path.stat().st_mtime, file_path))

    if not candidates:
        return None

    candidates.sort(key=lambda item: (item[0], item[1]))
    return candidates[-1][2]


def main():
    parser = argparse.ArgumentParser(description="获取目录中的最新安装包")
    parser.add_argument("directory", help="安装包所在目录")
    parser.add_argument(
        "--name",
        dest="keyword",
        default=None,
        help="按关键字过滤包名，例如 myapp / nginx / mysql",
    )
    args = parser.parse_args()

    directory = Path(args.directory)
    if not directory.exists() or not directory.is_dir():
        print(f"错误: 目录不存在或不是目录: {directory}", file=sys.stderr)
        sys.exit(1)

    latest = find_latest_package(directory, args.keyword)
    if latest is None:
        print("未找到符合条件的安装包", file=sys.stderr)
        sys.exit(2)

    print(latest.resolve())


if __name__ == "__main__":
    main()


# =========================
# 面试说明 / 讲解口述稿
# =========================
#
# 一、脚本作用
# 这个脚本的目的是让研发人员在不知道具体版本号的情况下，直接获取某个目录中的最新安装包。
# 研发只需要传入安装包目录，脚本就会自动扫描目录并返回最新版本文件的绝对路径。
#
# 二、核心设计思路
# 这道题的关键点不是“找到文件”，而是“正确比较版本号”。
# 如果直接按字符串比较，会出现错误，例如：
# 1. "2.1.2" 和 "2.1"
# 2. "5.10" 和 "5.1.9"
# 字符串比较并不能表达版本号的真实大小关系，所以这里采用的做法是：
# 1. 先从文件名中提取版本号
# 2. 再把版本号按点分割
# 3. 最后把每一段转成整数元组进行比较
#
# 例如：
# "2.1.2" -> (2, 1, 2)
# "2.1"   -> (2, 1)
# "5.10"  -> (5, 10)
# "5.1.9" -> (5, 1, 9)
#
# 这样比较时，Python 会按照元组的每一位依次比较，因此可以正确得到：
# 1. 2.1.2 > 2.1
# 2. 5.10 > 5.1.9
#
# 三、代码结构说明
# 1. VERSION_RE
#    使用正则表达式从文件名中提取版本号。
#    它支持类似 app-2.1.2.tar.gz、app_v5.10.rpm 这种常见命名格式。
#
# 2. extract_version(filename)
#    负责从文件名中提取版本号，并把字符串版本号转换成整数元组。
#    如果文件名中没有合法版本号，就返回 None。
#
# 3. find_latest_package(directory, keyword=None)
#    负责遍历目录下的所有文件，筛选出可以识别版本号的安装包。
#    如果传了 keyword，就进一步按关键字过滤文件名。
#    然后把候选文件按“版本号 + 修改时间”排序，取最后一个，也就是最新的包。
#
# 4. main()
#    负责处理命令行参数、校验目录是否存在，并最终输出最新安装包的绝对路径。
#
# 四、为什么加修改时间兜底
# 如果目录里存在两个版本号完全相同的包，比如：
# myapp-2.1.2-build1.tar.gz
# myapp-2.1.2-build2.tar.gz
# 单纯按版本号比较无法区分先后，所以这里额外使用文件修改时间作为第二排序条件。
# 在版本相同的情况下，优先返回修改时间更新的那个文件。
#
# 五、使用方式
# 1. 查找目录中最新的安装包：
#    python3 scripts/latest_package.py /data/packages
#
# 2. 如果目录里有多个产品包，可以按关键字过滤：
#    python3 scripts/latest_package.py /data/packages --name myapp
#
# 六、面试时可直接口述的版本
# “这个脚本的目标是让研发人员不需要记具体版本号，只要给一个目录，就能拿到最新安装包。
#  实现时我没有直接按字符串比较文件名，因为那样会出现版本号比较错误，比如 5.10 和 5.1.9。
#  我是先用正则从文件名里提取版本号，再把版本号拆成整数元组，比如 5.10 变成 (5, 10)，
#  5.1.9 变成 (5, 1, 9)，这样比较就符合版本语义了。
#  脚本主要分三部分：第一部分提取版本号，第二部分遍历目录筛选候选文件，
#  第三部分对候选文件按版本号排序并返回最新文件。为了更稳妥，我还加了修改时间作为兜底逻辑，
#  防止版本号相同的时候无法区分。最终研发人员只需要执行一条命令，就能得到最新安装包的绝对路径。” 
#
# 七、如果面试官继续追问，可以这样回答
# 1. 为什么不用字符串直接比较？
#    因为字符串比较是按字符顺序，不符合版本号的数值语义。
#
# 2. 为什么版本号要转成元组？
#    因为元组天然支持逐段比较，刚好符合主版本、次版本、修订版本的比较逻辑。
#
# 3. 如果以后想增强这个脚本，可以怎么做？
#    可以继续扩展：
#    1) 支持递归扫描子目录
#    2) 支持 beta、rc、snapshot 等预发布版本
#    3) 支持按产品名分组后分别输出每个产品的最新包
#    4) 支持把结果输出成 JSON，方便其他系统调用
