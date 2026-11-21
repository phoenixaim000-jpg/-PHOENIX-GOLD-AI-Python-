# -*- coding: utf-8 -*-
"""
================================================================================
PROJECT: PHOENIX-GOLD-AI-Python
FILE NAME: deploy_to_phoenix_gold_ai.py
AUTHOR: AIM PHOENIX (KIKKAKE &)
VERSION: 1.0.0 (GitHub Deployment Automation)
================================================================================

【概要】
作成済みの高速トレード両替プログラム (`phoenix_gold_high_speed_exchange.py`) を
GitHub リポジトリ `PHOENIX-GOLD-AI-Python` へ自動デプロイ（git init / add / commit / push）
するためのデプロイ実行スクリプトです。

【使い方】
1. GitHub上で `PHOENIX-GOLD-AI-Python` リポジトリを作成（または既存リモートURLを用意）。
2. 以下のように実行:
   python deploy_to_phoenix_gold_ai.py --repo-url https://github.com/<YOUR_USER>/PHOENIX-GOLD-AI-Python.git
   （dry-run 確認のみの場合は --dry-run を付与）
================================================================================
"""

import argparse
import os
import subprocess
from pathlib import Path


DEFAULT_TARGET_FILE = "phoenix_gold_high_speed_exchange.py"


def run_cmd(cmd: list[str], cwd: Path, dry_run: bool = False) -> tuple[int, str]:
    printable = " ".join(cmd)
    if dry_run:
        print(f"[DRY-RUN] {printable}")
        return 0, ""
    proc = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True)
    output = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode != 0:
        print(f"[ERROR] コマンド失敗 ({proc.returncode}): {printable}\n{output}")
    else:
        print(f"[OK] {printable}")
        if output.strip():
            print(output.strip())
    return proc.returncode, output


def deploy_to_github(
    project_dir: Path,
    repo_url: str,
    branch: str = "main",
    commit_message: str = "deploy: PHOENIX-GOLD-AI-Python high-speed GOLD/Crypto/FX exchange engine",
    dry_run: bool = False,
) -> bool:
    target_path = project_dir / DEFAULT_TARGET_FILE
    if not target_path.exists():
        print(f"[ERROR] デプロイ対象ファイルが見つかりません: {target_path}")
        return False

    script_name = os.path.basename(globals().get("__file__", "deploy_to_phoenix_gold_ai.py"))

    git_dir = project_dir / ".git"
    if not git_dir.exists():
        code, _ = run_cmd(["git", "init"], project_dir, dry_run=dry_run)
        if code != 0:
            return False

    run_cmd(["git", "branch", "-M", branch], project_dir, dry_run=dry_run)

    code, remotes_out = run_cmd(["git", "remote"], project_dir, dry_run=False) if not dry_run else (0, "")
    if repo_url:
        if "origin" in remotes_out.splitlines():
            run_cmd(["git", "remote", "set-url", "origin", repo_url], project_dir, dry_run=dry_run)
        else:
            run_cmd(["git", "remote", "add", "origin", repo_url], project_dir, dry_run=dry_run)

    code, _ = run_cmd(["git", "add", DEFAULT_TARGET_FILE, script_name], project_dir, dry_run=dry_run)
    if code != 0:
        return False

    code, _ = run_cmd(["git", "commit", "-m", commit_message], project_dir, dry_run=dry_run)
    if code not in (0, 1):
        return False

    if repo_url:
        code, _ = run_cmd(["git", "push", "-u", "origin", branch], project_dir, dry_run=dry_run)
        if code != 0:
            return False

    print(f"\n=== PHOENIX-GOLD-AI-Python デプロイ完了 ({branch}) ===")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Deploy high-speed exchange Python program to PHOENIX-GOLD-AI-Python on GitHub")
    parser.add_argument("--dir", default=".", help="プロジェクトディレクトリパス")
    parser.add_argument("--repo-url", default="", help="GitHubリポジトリURL (例: https://github.com/USER/PHOENIX-GOLD-AI-Python.git)")
    parser.add_argument("--branch", default="main", help="デプロイ先ブランチ (デフォルト: main)")
    parser.add_argument("--message", default="deploy: PHOENIX-GOLD-AI-Python high-speed GOLD/Crypto/FX exchange engine", help="コミットメッセージ")
    parser.add_argument("--dry-run", action="store_true", help="実際のgit実行を行わずコマンドを表示")
    args = parser.parse_args()

    deploy_to_github(
        project_dir=Path(args.dir).resolve(),
        repo_url=args.repo_url.strip(),
        branch=args.branch.strip(),
        commit_message=args.message.strip(),
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()

