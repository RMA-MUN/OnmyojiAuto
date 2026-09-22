"""一键打包：OAT 本体 + OAT 更新程序，然后合并到同一目录。

流程（对标现有手工命令）：
  1. nuitka 打包 OAT 本体      -> main.dist/（含 OAT.exe）
  2. nuitka 打包更新程序        -> <updater-dist>/（含 OAT_Updater.exe）
  3. 合并：先拷 OAT 产物到合并目录，再把更新程序产物叠加上去，
     重名文件直接覆盖（两者同版本依赖，DLL 基本一致；关键是两个 exe 落到同一目录）。

用法：
  python build_release.py                      # 全流程
  python build_release.py --skip-oat            # 只打更新程序+合并（复用上次 main.dist）
  python build_release.py --skip-updater        # 只打本体+合并
  python build_release.py --merge-only          # 只合并（都不打）
  python build_release.py --merge-dir D:/out    # 指定合并目录

注意：两次 nuitka standalone 构建很慢（各约十几分钟起），请耐心等待。
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))

OAT_CMD = [
    "-m", "nuitka",
    "--standalone",
    "--windows-disable-console",
    "--follow-imports",
    "--remove-output",
    "--windows-icon-from-ico=OAT/tools/uiResources/icon.ico",
    "--enable-plugin=pyqt6",
    "--include-data-dir=OAT/tools/uiResources=OAT/tools/uiResources",
    "--include-data-dir=platforms=platforms",
    "--output-filename=OAT",
    "main.py",
]

UPDATER_CMD = [
    "-m", "nuitka",
    "--standalone",
    "--windows-disable-console",
    "--follow-imports",
    "--remove-output",
    "--windows-icon-from-ico=OAT/tools/uiResources/icon.ico",
    "--enable-plugin=pyqt6",
    "--output-dir={updater_build_dir}",
    "--output-filename=OAT_Updater",
    "OAT_Updater_GUI/main.py",
]

OAT_DIST = os.path.join(ROOT, "main.dist")
OAT_EXE = "OAT.exe"
UPDATER_EXE = "OAT_Updater.exe"


def run(cmd: list[str], desc: str) -> None:
    print(f"[build] {desc}：{' '.join(cmd)}", flush=True)
    ret = subprocess.run([sys.executable, *cmd], cwd=ROOT)
    if ret.returncode != 0:
        raise SystemExit(f"[build] {desc}失败，退出码 {ret.returncode}")


def find_dist(build_dir: str, exe_name: str) -> str:
    """在构建输出目录下找到包含 exe 的 dist 目录。

    注意：构建目录里可能有历史残留（如之前误拷进去的整包 OAT/），
    必须优先选 *.dist 且选最新的，而不是按字母顺序碰到的第一个。
    """
    if os.path.isfile(os.path.join(build_dir, exe_name)):
        return build_dir
    cands = []
    for entry in sorted(os.listdir(build_dir)):
        cand = os.path.join(build_dir, entry)
        if os.path.isdir(cand) and os.path.isfile(os.path.join(cand, exe_name)):
            cands.append(cand)
    if not cands:
        raise SystemExit(f"[build] 在 {build_dir} 下找不到 {exe_name}，打包可能失败")
    pool = [c for c in cands if c.endswith(".dist")] or cands
    pool.sort(key=os.path.getmtime)
    if len(cands) > 1:
        print(f"[build] 发现多个候选目录，选用最新：{pool[-1]}", flush=True)
    return pool[-1]


def merge_dirs(src: str, dst: str) -> tuple[int, int]:
    """把 src 整棵树拷到 dst，重名文件覆盖。返回 (拷入文件数, 覆盖数)。"""
    copied, overwritten = 0, 0
    for dirpath, _dirnames, filenames in os.walk(src):
        rel = os.path.relpath(dirpath, src)
        target_dir = dst if rel == "." else os.path.join(dst, rel)
        os.makedirs(target_dir, exist_ok=True)
        for name in filenames:
            dst_file = os.path.join(target_dir, name)
            if os.path.exists(dst_file):
                overwritten += 1
            copied += 1
            shutil.copy2(os.path.join(dirpath, name), dst_file)
    return copied, overwritten


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="打包 OAT 本体 + 更新程序并合并")
    ap.add_argument("--skip-oat", action="store_true", help="跳过 OAT 本体打包（复用 main.dist）")
    ap.add_argument("--skip-updater", action="store_true", help="跳过更新程序打包")
    ap.add_argument("--merge-only", action="store_true", help="只合并，不打包")
    ap.add_argument("--updater-build-dir", default=r"E:/OAT/OAT_Updater_Build",
                    help="更新程序 nuitka --output-dir（默认：E:/OAT/OAT_Updater_Build）")
    ap.add_argument("--merge-dir", default=r"E:/OAT/OAT", help="合并输出目录（默认：E:/OAT/OAT）")
    args = ap.parse_args(argv)

    if not args.merge_only and not args.skip_oat:
        run(OAT_CMD, "打包 OAT 本体")
    if not os.path.isfile(os.path.join(OAT_DIST, OAT_EXE)):
        raise SystemExit(f"[build] 找不到 {OAT_DIST}\\{OAT_EXE}，先正常打包一次本体")

    updater_dist = None
    if not args.merge_only and not args.skip_updater:
        updater_cmd = [c.format(updater_build_dir=args.updater_build_dir) for c in UPDATER_CMD]
        run(updater_cmd, "打包更新程序")
    if not (args.merge_only and args.skip_updater):
        updater_dist = find_dist(args.updater_build_dir, UPDATER_EXE)

    os.makedirs(args.merge_dir, exist_ok=True)
    n1, o1 = merge_dirs(OAT_DIST, args.merge_dir)
    print(f"[build] OAT 本体已合并：{n1} 个文件（{o1} 个覆盖）", flush=True)
    if updater_dist:
        n2, o2 = merge_dirs(updater_dist, args.merge_dir)
        print(f"[build] 更新程序已合并：{n2} 个文件（{o2} 个覆盖）", flush=True)

    for exe in (OAT_EXE, UPDATER_EXE):
        ok = os.path.isfile(os.path.join(args.merge_dir, exe))
        print(f"[build] {'OK ' if ok else '缺失'} {exe}", flush=True)
        if not ok:
            raise SystemExit(f"[build] 合并目录缺少 {exe}")
    print(f"[build] 完成：{args.merge_dir}", flush=True)


if __name__ == "__main__":
    main()
