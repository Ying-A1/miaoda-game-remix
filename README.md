# Miaoda Game Remix · 秒哒一键复刻爆款小游戏

A **Claude/Agent skill** that builds browser games on Baidu Miaoda (秒哒) by
**remixing built-in hot-game templates** instead of building from scratch.

一个运行在命令行 Agent 上的 **Skill**：在百度「秒哒」App Builder 之上做「加法」，
内置爆款小游戏模板，让用户用**半 DIY** 的方式复刻小游戏——保留经过验证的玩法，
把牌面 / 精灵 / 背景 / 头像换成自己的图片（家人、朋友、动漫形象）。

## What it does / 能做什么

- Pick a template (斗地主 Dou Dizhu · 2048 · 羊了个羊 · 贪吃蛇 Snake · 打砖块 Breakout)
- Replace visual assets (card faces, sprites, backgrounds, avatars) with your own images
- Assemble a high-quality generation prompt (PRD + reference code + asset instructions)
- Drive the official Miaoda `chat` → `generate-app` → `publish` lifecycle to deploy a playable app

> v1 ships `dou-dizhu` (斗地主) fully implemented; the other four templates are declared
> placeholders to be filled in.

## Layout / 目录结构

```
.
├── SKILL.md                     # Skill definition & full workflow (读这个)
├── scripts/
│   ├── remix.py                 # NEW — template remix layer (prompt assembly)
│   └── miaoda_api.py            # Official Miaoda platform CLI (unchanged)
└── templates/
    └── dou-dizhu/               # 斗地主 template: spec, asset slots, reference engine
```

## Quick start / 快速开始

```bash
# 1) See available templates and their replaceable asset slots
python scripts/remix.py list-templates
python scripts/remix.py show-template --template dou-dizhu

# 2) Preview the assembled generation prompt (no API call)
python scripts/remix.py build-prompt --template dou-dizhu --assets assets_map.json

# 3) Create the app via the official flow (needs an API key)
export MIAODA_API_KEY="sk_xxxxx"       # get one at https://www.miaoda.cn
python scripts/remix.py remix --template dou-dizhu --assets assets_map.json
```

See [SKILL.md](SKILL.md) for the complete workflow, commands, and lifecycle rules.

## Requirements / 依赖

- `python3`
- `requests` (`pip install requests`)
- A Miaoda API key in the `MIAODA_API_KEY` environment variable

## License / 许可

This project is released under the [MIT License](LICENSE).

The bundled reference engine under
[`templates/dou-dizhu/reference/`](templates/dou-dizhu/reference/) is derived from the
MIT-licensed [onestraw/doudizhu](https://github.com/onestraw/doudizhu) project
(Copyright © 2018 Larry He) and retains its original license and attribution.
