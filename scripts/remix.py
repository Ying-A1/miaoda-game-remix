#!/usr/bin/env python3
"""
Miaoda Game Remix — 半-DIY 小游戏模板复刻工具

在秒哒官方 miaoda_api.py 之上做「加法」：
  - 内置爆款小游戏模板(spec + 参考源码 + 可替换素材槽位)
  - 用户提供自定义图片，映射到素材槽位
  - 把「模板规格 + 参考代码 + 自定义素材」拼成一条超级生成指令
  - 复用官方 chat / generate-app / publish 流程真正生成应用

本脚本本身不直接调用秒哒 API 生成，而是产出/执行标准的 miaoda_api.py 命令，
从而完整保留官方那套稳定的 API 调用方式与生命周期规则。

Usage:
    python remix.py list-templates
    python remix.py show-template --template dou-dizhu
    python remix.py build-prompt --template dou-dizhu [--assets assets_map.json] [--extra "额外要求"]
    python remix.py remix --template dou-dizhu [--assets assets_map.json] [--dry-run]

assets_map.json 格式(把素材槽位 key 映射到公开图片 URL):
    {
      "joker_big": "https://example.com/grandpa.png",
      "joker_small": "https://example.com/grandma.png",
      "table_background": "https://example.com/bg.png"
    }
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPT_DIR.parent
TEMPLATES_DIR = SKILL_ROOT / "templates"
MIAODA_API = SCRIPT_DIR / "miaoda_api.py"

# 参考代码拼进指令时的单文件字符上限，避免指令过长。
# 设为 20000 以容纳斗地主核心规则引擎(engine.py ~18KB)完整放入，
# 保证最关键的牌型判定/大小比较逻辑不被截断。
_MAX_REF_CHARS_PER_FILE = 20000
_REF_CODE_EXTS = {".js", ".ts", ".jsx", ".tsx", ".html", ".css", ".py", ".vue"}


# ---------------------------------------------------------------------------
# 模板发现与读取
# ---------------------------------------------------------------------------

def _iter_template_dirs():
    """Yield each template directory that contains a template.json."""
    if not TEMPLATES_DIR.is_dir():
        return
    for child in sorted(TEMPLATES_DIR.iterdir()):
        if child.is_dir() and (child / "template.json").is_file():
            yield child


def _load_template_meta(template_dir: Path) -> dict:
    """Load and return the template.json metadata dict for a template directory."""
    with open(template_dir / "template.json", encoding="utf-8") as f:
        return json.load(f)


def _resolve_template_dir(template_id: str) -> Path:
    """Return the directory for a template id, or raise if it does not exist."""
    template_dir = TEMPLATES_DIR / template_id
    if not (template_dir / "template.json").is_file():
        available = ", ".join(d.name for d in _iter_template_dirs()) or "(none)"
        raise RuntimeError(
            f"Unknown template '{template_id}'. Available templates: {available}"
        )
    return template_dir


def list_templates() -> list[dict]:
    """Return brief metadata for all installed templates."""
    out = []
    for template_dir in _iter_template_dirs():
        meta = _load_template_meta(template_dir)
        out.append({
            "id": meta.get("id", template_dir.name),
            "name": meta.get("name", ""),
            "category": meta.get("category", ""),
            "hotness": meta.get("hotness", ""),
            "description": meta.get("description", ""),
        })
    return out


def _read_text(path: Path) -> str:
    """Read a UTF-8 text file, returning empty string if missing."""
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8")


def _read_reference_code(template_dir: Path, ref_dir_name: str) -> list[tuple[str, str]]:
    """Collect (filename, truncated_content) for code files in the reference dir."""
    ref_dir = template_dir / ref_dir_name
    files: list[tuple[str, str]] = []
    if not ref_dir.is_dir():
        return files
    for path in sorted(ref_dir.rglob("*")):
        if path.is_file() and path.suffix.lower() in _REF_CODE_EXTS:
            content = path.read_text(encoding="utf-8", errors="replace")
            if len(content) > _MAX_REF_CHARS_PER_FILE:
                content = content[:_MAX_REF_CHARS_PER_FILE] + "\n/* ...(truncated)... */"
            files.append((path.name, content))
    return files


# ---------------------------------------------------------------------------
# 素材映射与指令拼装
# ---------------------------------------------------------------------------

def _load_assets_map(assets_path: Optional[str]) -> dict:
    """Load the user-provided {slot_key: image_url} mapping, or return empty dict."""
    if not assets_path:
        return {}
    with open(assets_path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise RuntimeError("--assets file must be a JSON object of {slot_key: url}")
    return data


def _validate_assets(assets_map: dict, slots_def: dict) -> list[str]:
    """Return warnings for asset keys that don't match any declared slot."""
    valid_keys = {s["key"] for s in slots_def.get("slots", [])}
    warnings = []
    for key in assets_map:
        if key not in valid_keys:
            warnings.append(
                f"asset key '{key}' does not match any slot in assets.json "
                f"(valid: {', '.join(sorted(valid_keys))})"
            )
    return warnings


def _render_asset_instructions(assets_map: dict, slots_def: dict) -> str:
    """Render a human/agent-readable block describing which assets to replace."""
    if not assets_map:
        return "（本次未提供自定义素材，全部使用模板默认素材。）"
    label_by_key = {s["key"]: s.get("label", s["key"]) for s in slots_def.get("slots", [])}
    lines = []
    for key, url in assets_map.items():
        label = label_by_key.get(key, key)
        lines.append(f"- 【{label}】(slot: {key}) 替换为图片: {url}")
    return "\n".join(lines)


def build_prompt(
    template_id: str,
    assets_path: Optional[str] = None,
    extra: str = "",
) -> tuple[str, dict, list[str]]:
    """Assemble the full generation instruction for a template.

    Returns (prompt_text, template_meta, warnings).
    """
    template_dir = _resolve_template_dir(template_id)
    meta = _load_template_meta(template_dir)

    spec = _read_text(template_dir / meta.get("specFile", "spec.md"))
    slots_def = json.loads(_read_text(template_dir / meta.get("assetsFile", "assets.json")) or "{}")
    assets_map = _load_assets_map(assets_path)
    warnings = _validate_assets(assets_map, slots_def)

    ref_files = _read_reference_code(template_dir, meta.get("referenceDir", "reference"))
    ref_block = ""
    if ref_files:
        parts = ["\n## 参考实现代码（请参考其牌型判定/游戏流程逻辑，保证规则正确）\n"]
        for fname, content in ref_files:
            lang = Path(fname).suffix.lstrip(".")
            parts.append(f"### {fname}\n```{lang}\n{content}\n```")
        ref_block = "\n".join(parts)

    asset_block = _render_asset_instructions(assets_map, slots_def)

    extra_block = ""
    if extra and extra.strip():
        extra_block = f"\n## 额外的自定义要求（用户附加，优先满足）\n{extra.strip()}\n"

    prompt = f"""请基于以下规格，生成一个「{meta.get('name', template_id)}」小游戏应用。
严格遵循规格中的玩法规则和界面要求，做到可玩、规则正确、界面美观、移动端和桌面端都适配。

## 应用规格 (PRD)
{spec}

## 自定义素材替换要求（半-DIY）
请把游戏中对应的视觉素材替换为以下用户提供的图片。图片要自适应原素材尺寸、不变形；未列出的素材使用模板默认。
{asset_block}
{extra_block}{ref_block}

## 输出要求
- 完整实现规格中列出的全部牌型和出牌校验，AI 对手不得犯规。
- 素材引用集中管理，方便后续再次替换。
- 一次性生成可直接游玩的完整应用。
"""
    return prompt, meta, warnings


# ---------------------------------------------------------------------------
# 复用官方 CLI 执行生成
# ---------------------------------------------------------------------------

def _run_miaoda(args: list[str]) -> int:
    """Invoke the official miaoda_api.py CLI with the given args, streaming output."""
    cmd = [sys.executable, str(MIAODA_API), *args]
    print(f"[remix] exec: {' '.join(cmd)}", file=sys.stderr, flush=True)
    proc = subprocess.run(cmd)
    return proc.returncode


def remix(
    template_id: str,
    assets_path: Optional[str] = None,
    extra: str = "",
    dry_run: bool = False,
) -> int:
    """Build the prompt and drive the official chat flow to create the app.

    With --dry-run, only prints the assembled chat command without calling the API.
    """
    prompt, meta, warnings = build_prompt(template_id, assets_path, extra)
    for w in warnings:
        print(f"[remix][warn] {w}", file=sys.stderr)

    chat_args = ["chat", "--text", prompt]
    query_mode = meta.get("defaultQueryMode")
    if query_mode:
        chat_args += ["--query-mode", query_mode]

    if dry_run:
        print(json.dumps({
            "template": template_id,
            "recommendedFlow": meta.get("recommendedFlow", []),
            "chatCommand": ["python", "scripts/miaoda_api.py", *chat_args[:1],
                            "--text", "<assembled prompt below>"] ,
            "promptChars": len(prompt),
        }, ensure_ascii=False, indent=2))
        print("\n----- ASSEMBLED PROMPT -----\n")
        print(prompt)
        print("\n----- NEXT STEPS (per official lifecycle) -----")
        print("1) 上面这条 chat 会创建 App 并进入 PRD 阶段，记下返回的 appId / conversationId")
        print("2) 出现 generateApp 按钮后: python scripts/miaoda_api.py generate-app --app-id <id> --context-id <ctx> --watch")
        print("3) 发布: python scripts/miaoda_api.py publish --app-id <id> --wait")
        return 0

    if not os.environ.get("MIAODA_API_KEY"):
        print("Error: MIAODA_API_KEY not set. export MIAODA_API_KEY=... 或用 --dry-run 预览指令。",
              file=sys.stderr)
        return 1

    return _run_miaoda(chat_args)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    """Construct the remix CLI argument parser."""
    parser = argparse.ArgumentParser(description="Miaoda Game Remix — 半-DIY 模板复刻工具")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list-templates", help="列出所有内置模板")

    p = sub.add_parser("show-template", help="查看某个模板的规格与可替换素材槽位")
    p.add_argument("--template", required=True, help="模板 id, 如 dou-dizhu")

    p = sub.add_parser("build-prompt", help="拼装生成指令并打印(不调用 API)")
    p.add_argument("--template", required=True)
    p.add_argument("--assets", default=None, help="素材映射 JSON 文件 {slot_key: url}")
    p.add_argument("--extra", default="", help="额外的自定义要求")

    p = sub.add_parser("remix", help="拼装指令并复用官方 chat 流程创建应用")
    p.add_argument("--template", required=True)
    p.add_argument("--assets", default=None, help="素材映射 JSON 文件 {slot_key: url}")
    p.add_argument("--extra", default="", help="额外的自定义要求")
    p.add_argument("--dry-run", action="store_true", help="只打印指令, 不调用 API")

    return parser


def main():
    """Parse CLI args and dispatch to the appropriate remix function."""
    parser = build_parser()
    args = parser.parse_args()

    try:
        if args.command == "list-templates":
            print(json.dumps(list_templates(), ensure_ascii=False, indent=2))

        elif args.command == "show-template":
            template_dir = _resolve_template_dir(args.template)
            meta = _load_template_meta(template_dir)
            slots = json.loads(_read_text(template_dir / meta.get("assetsFile", "assets.json")) or "{}")
            print(json.dumps({"meta": meta, "assets": slots}, ensure_ascii=False, indent=2))

        elif args.command == "build-prompt":
            prompt, meta, warnings = build_prompt(args.template, args.assets, args.extra)
            for w in warnings:
                print(f"[warn] {w}", file=sys.stderr)
            print(prompt)

        elif args.command == "remix":
            rc = remix(args.template, args.assets, args.extra, dry_run=args.dry_run)
            sys.exit(rc)

    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
