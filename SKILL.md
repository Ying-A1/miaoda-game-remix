---
name: miaoda-game-remix
description: >-
  Create browser games on Baidu Miaoda (秒哒) by remixing built-in hot game
  templates (斗地主 Dou Dizhu, 2048, 羊了个羊, 贪吃蛇 Snake, 打砖块 Breakout) instead of
  building from scratch. Semi-DIY: users pick a template and replace card faces,
  sprites, backgrounds and avatars with custom images (family photos, friends,
  anime characters). Also supports full app create / modify / generate / deploy
  via natural language.
metadata:
  openclaw:
    requires:
      bins:
        - python3
      env:
        - MIAODA_API_KEY
    primaryEnv: MIAODA_API_KEY
disable-model-invocation: false
---

# Miaoda Game Remix (秒哒爆款小游戏复刻)

This skill builds on the official **Miaoda (秒哒) App Builder** and adds a
**semi-DIY template remix** workflow on top of it.

Instead of asking the user to describe a whole game from scratch (full DIY),
this skill ships **built-in hot game templates** and lets the user **remix**
one: keep the proven gameplay, replace the visual assets with custom images.

Two scripts are used together:

```bash
# 1) Template remix layer (NEW) — assembles a high-quality generation prompt
python scripts/remix.py <command> [options]

# 2) Official Miaoda platform CLI (UNCHANGED) — the actual API calls & lifecycle
python scripts/miaoda_api.py <command> [options]
```

`remix.py` never talks to the platform directly — it assembles the instruction
and then drives `miaoda_api.py`, so the official, well-tested API flow and its
lifecycle rules are **fully preserved**.

---

# When to Use This Skill

Use this skill when the user wants to:

* create a **browser game** or **mini game**
* build a game **like a known hot title** (斗地主 / 2048 / 羊了个羊 / 贪吃蛇 / 打砖块)
* **customize / reskin** a game: replace card faces, tiles, sprites, background,
  or player avatars with **their own images** (family, friends, anime, pets)
* "把斗地主的牌换成我家人的照片"
* "做一个贪吃蛇，蛇头换成我的头像"
* modify or publish a Miaoda game they already created

For non-game apps (dashboards, SaaS, reports, PPT), use the base
`miaoda-app-builder` skill instead.

---

# Routing Keywords

斗地主, 2048, 羊了个羊, 贪吃蛇, snake, 打砖块, breakout, 小游戏, 爆款游戏,
换牌面, 换头像, 自定义图片, 复刻游戏, remix game, reskin, custom sprites,
make a card game, clone a hot game.

---

# Built-in Templates (爆款模板)

| id | 名称 | 类型 | 可替换素材(示例) |
|----|------|------|-----------------|
| `dou-dizhu` | 斗地主 | 纸牌 | 54张牌面 / 大小王 / 牌背 / 牌桌背景 / 三个头像 / 地主标识 |
| `2048` | 2048 | 数字合成 | 各数字方块 / 背景 (规划中) |
| `sheep` | 羊了个羊 | 消除 | 图案卡牌 / 背景 (规划中) |
| `snake` | 贪吃蛇 | 街机 | 蛇头/蛇身 / 食物 / 背景 (规划中) |
| `breakout` | 打砖块 | 街机 | 砖块 / 挡板 / 球 / 背景 (规划中) |

> v1 currently ships **`dou-dizhu` fully implemented**; the other four are
> declared placeholders being filled in. Always call `remix.py list-templates`
> to see what is actually available before promising a template to the user.

---

# The Semi-DIY Remix Workflow (核心新增流程)

This is the main new capability. Follow these steps:

### Step 1 — Discover templates

```bash
python scripts/remix.py list-templates
python scripts/remix.py show-template --template dou-dizhu
```

`show-template` prints the template metadata **and** the replaceable asset
**slots** (from `assets.json`). Show the user which slots they can customize.

### Step 2 — Collect custom images from the user

Ask the user which slots they want to replace and get an **image for each**.

> **Image input rule (v1):** the generation instruction can only carry images
> as **public https URLs** in text. The official `chat` payload sends text
> parts only — it does **not** upload local files.
>
> * If the user gives a URL → use it directly.
> * If the user gives a local file → it must first be turned into a public URL
>   by the surrounding Harness / an image host. `remix.py` does **not** host
>   images itself in v1. If no URL is available, proceed with default assets
>   and tell the user which slots were left as default.

Write the chosen mapping to a JSON file, keyed by slot:

```json
{
  "joker_big": "https://cdn.example.com/grandpa.png",
  "joker_small": "https://cdn.example.com/grandma.png",
  "table_background": "https://cdn.example.com/table.png"
}
```

### Step 3 — Assemble the generation prompt

```bash
# Preview only (no API call) — ALWAYS do this first to sanity-check
python scripts/remix.py build-prompt --template dou-dizhu --assets assets_map.json
```

This merges: template **PRD** (`spec.md`) + **reference source code**
(`reference/`) + **asset replacement instructions** into one super-prompt.
Unknown slot keys produce `[warn]` lines — fix them before generating.

### Step 4 — Generate via the official flow

```bash
export MIAODA_API_KEY="sk_xxxxx"

# Dry-run first to see the exact chat command + next steps
python scripts/remix.py remix --template dou-dizhu --assets assets_map.json --dry-run

# Real run: this calls the official `chat` with the assembled prompt
python scripts/remix.py remix --template dou-dizhu --assets assets_map.json
```

The `remix` command runs the official `chat`. From here you are back on the
**standard Miaoda lifecycle** (below): capture `appId` + `conversationId`, wait
for the Generate App button, `generate-app --watch`, then `publish --wait`.

### Step 5 — Iterate (change assets / tweak gameplay)

Further changes are normal modifications on the generated app — use the official
`chat` with the **same** `appId` + `conversationId` (do **not** call
`generate-app` again). E.g. "把牌背换成 https://.../back.png".

---

# ⚠️ On "copying platform templates" (为什么不走网页版一键复制)

The web UI lets you browse a template gallery, search (e.g. "斗地主") and
**one-click copy** someone else's app. **The current platform API does NOT
expose this.** The packaged `miaoda_api.py` only offers: `list-apps` (your own
apps only), `app-detail`, `chat`, `trajectory`, `publish`, `publish-status`.
There is **no** template-search, gallery-read, or app-fork/duplicate endpoint.

So this skill does **not** rely on platform-side copying. Instead it ships its
own template library (`templates/`) and feeds a high-quality PRD + reference
code through the standard `chat` endpoint. This is more stable and fully
controllable, and it works with today's API.

> The only hint that a "square/gallery" exists is the `isReleaseAppSquare`
> field in the publish payload. A read/copy API for the square is unconfirmed
> and undocumented — do not depend on it.

---

# Stateless Execution Model

Both CLIs are **stateless**. Workflow state lives on the Miaoda platform and is
inferred from `appId`, `conversationId`, application detail, and trajectory
events. Always pass the right identifiers when continuing / modifying an app.

---

# Application Lifecycle Rules (官方规则，保留)

## Initial Creation

1. Start with a `chat` request (here: produced by `remix.py remix`).
2. The app enters the **PRD refinement stage**.
3. Continue chatting with `miaoda_api.py chat` to refine if needed.
4. When the trajectory contains a **Generate App** button (`"type":"button"`
   and `"event":{"name":"generateApp"}` in
   `result.artifact.parts[].data.actions[]`), call `generate-app`.

Generation is required **only once** during initial creation.

## Multi-Round Modification

After generation:

* **Do not call `generate-app` again.**
* Continue with `chat` using the same `appId` and `conversationId`.

## Publishing

Allowed after the app has been generated at least once. No extra generation
needed. Follow with status polling or use `--wait`:

```
publish --wait
```

Stop when status is `SUCCESS` or `FAILED`.

---

# Application URLs

* **Editor / preview (yourself only):** `https://www.miaoda.cn/projects/<app_id>`
* **Production (public, share this one):** `https://<app_id>.appmiaoda.com`

Only share the production URL, and only **after publishing succeeds**. Never
share the editor URL externally.

---

# Standard Workflow (with remix)

```
remix.py remix --template <id> --assets <map>   →  (official chat, creates app)
   →  miaoda_api.py generate-app --watch
   →  miaoda_api.py publish --wait
   →  share https://<app_id>.appmiaoda.com
```

---

# Available Commands

## remix.py (NEW — template layer)

Always set `MIAODA_API_KEY` before `remix` (not needed for the read-only
`list-templates` / `show-template` / `build-prompt`).

### list-templates
List all installed templates (id, name, category, hotness, description).
```bash
python scripts/remix.py list-templates
```

### show-template
Show one template's metadata and its replaceable asset slots.
```bash
python scripts/remix.py show-template --template dou-dizhu
```

### build-prompt
Assemble and print the full generation prompt (PRD + reference code + asset
instructions). **No API call.** Use this to review before generating.
```bash
python scripts/remix.py build-prompt --template dou-dizhu --assets assets_map.json --extra "牌桌用中式红金风格"
```
- `--template` (required): template id
- `--assets`: JSON file mapping `{slot_key: image_url}`
- `--extra`: extra free-form requirements appended to the prompt

### remix
Assemble the prompt and drive the official `chat` to create the app.
```bash
python scripts/remix.py remix --template dou-dizhu --assets assets_map.json          # real
python scripts/remix.py remix --template dou-dizhu --assets assets_map.json --dry-run # preview cmd only
```
- Same options as `build-prompt`, plus `--dry-run` (print the chat command and
  next steps without calling the API).
- On a real run, extract `appId` / `conversationId` from the `chat` output and
  continue with the official lifecycle.

## miaoda_api.py (UNCHANGED — official platform CLI)

All official commands are preserved as-is:

| command | purpose |
|---------|---------|
| `list-apps [--brief]` | list your apps |
| `app-detail --app-id <id>` | app detail (auto-injects `conversationId`) |
| `chat --text <t> [--app-id --context-id]` | create / refine / modify |
| `trajectory --app-id <id>` | poll progress to terminal state |
| `fetch-trajectory --app-id <id>` | single non-polling event fetch |
| `get-context-id --app-id <id>` | recover a lost `conversationId` |
| `conversation-history --app-id <id>` | human-readable past turns |
| `generate-app --app-id <id> --context-id <ctx> --watch` | trigger generation (once) |
| `publish --app-id <id> --wait` | deploy to production |
| `publish-status --release-id <id>` | poll deploy status |

> **⚠️ `--app-id` and `--context-id` must always be used together** when
> continuing an app. Passing `--app-id` without `--context-id` makes the
> platform silently create a brand-new app (the CLI now errors to prevent this).
> To create fresh, omit both. To recover a lost `conversationId`, use
> `get-context-id`.

See the base `miaoda-app-builder` documentation for full per-command details of
`miaoda_api.py`; its behavior is identical here.

---

# Complete Example — Remix 斗地主 with family photos

```bash
export MIAODA_API_KEY="sk_xxxxx"
cd ~/.openclaw/skills/miaoda-game-remix

# 1) See what can be customized
python scripts/remix.py show-template --template dou-dizhu

# 2) Prepare asset map (public https URLs)
cat > assets_map.json <<'JSON'
{
  "joker_big": "https://cdn.example.com/grandpa.png",
  "joker_small": "https://cdn.example.com/grandma.png",
  "table_background": "https://cdn.example.com/livingroom.png"
}
JSON

# 3) Review the assembled prompt
python scripts/remix.py build-prompt --template dou-dizhu --assets assets_map.json

# 4) Create the app (official chat under the hood) — capture appId/conversationId
python scripts/remix.py remix --template dou-dizhu --assets assets_map.json | tee remix_out.txt
APP_ID=$(head -1 remix_out.txt | python3 -c 'import sys,json;print(json.load(sys.stdin)["appId"])')
CTX_ID=$(head -1 remix_out.txt | python3 -c 'import sys,json;print(json.load(sys.stdin)["conversationId"])')

# 5) Generate when the Generate App button appears
python scripts/miaoda_api.py generate-app --app-id "$APP_ID" --context-id "$CTX_ID" --watch

# 6) Publish
python scripts/miaoda_api.py publish --app-id "$APP_ID" --wait
echo "https://$APP_ID.appmiaoda.com"
```

---

# Error Handling

* **IAM access key validation failed** → `MIAODA_API_KEY` missing/invalid; get a
  key at https://www.miaoda.cn and export it.
* **秒点不足 (Insufficient Credits)** → recharge at https://www.miaoda.cn.
* **Unknown template** → run `remix.py list-templates`; only offer templates
  that actually exist.
* **Asset slot warning** → an `--assets` key doesn't match any declared slot;
  check `show-template` output for valid slot keys.
* **No public URL for a local image** → generate with defaults for that slot and
  tell the user; local upload is not supported by the platform API in v1.
* **`--app-id` without `--context-id`** → would create a new app; always pass
  both, or use `get-context-id` to recover the `conversationId`.

---

# Design Notes / Roadmap

* v1: `dou-dizhu` fully implemented; 2048 / 羊了个羊 / 贪吃蛇 / 打砖块 are
  declared placeholders to fill in (add `spec.md` + `assets.json` +
  `reference/` per template).
* Reference code under each template's `reference/` must be **permissively
  licensed (MIT / Apache-2.0)** since it is fed to the platform and regenerated.
* Open question to confirm with the platform: whether `chat` can accept image
  **file** parts (not just text URLs). If yes, a future version can upload local
  images directly instead of requiring public URLs.
