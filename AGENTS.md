# Repository Guidelines

## 项目概述

基于 NoneBot2（Python 3.11）的 QQ 机器人，为物理实验课提供图片查询：

- **大雾1**：按实验名返回大雾1 题库原题图片；
- **大雾2**：按实验名返回二级大雾题库原题图片。

两者完全同构，都走「精确匹配 → AI 模糊匹配」两级回退。机器人同时支持 QQ 官方机器人（开放平台）与 OneBot v11 两套适配器，业务代码与适配器解耦。

## 项目结构

```
RzyL/
├── bot.py                      # 入口：nonebot.init + 注册 OneBot v11 + load_plugins("src/plugins")
├── pyproject.toml / uv.lock    # 依赖（nonebot2 / alconna / onebot.v11 / aiohttp）
├── pyrightconfig.json          # 类型检查配置（指向 .venv）
├── .env.secret.temple          # 密钥模板；复制为 .env.secret 后填真实值
└── src/
    ├── asserts/                # 静态资源（图片 + 关键词 JSON），不是 Python 包
    │   ├── dawu/               #   大雾1：{英文键}.jpg + keywords.json
    │   └── dawu2/              #   大雾2：{英文键}.jpg（27 张）+ keywords.json（27 键）
    ├── utils/                  # 跨插件公共代码
    │   ├── safe_send.py        #   safe_send / safe_finish：发送失败不抛出、不中断流程
    │   ├── adapter_compat.py   #   跨适配器：图片段 / 消息组装 / 剥 <@openid>
    │   └── ai_error.py         #   format_ai_error：错误码 → 可区分原因的中文提示
    └── plugins/
        ├── dawu/               # 大雾1
        └── dawu2/              # 大雾2（与 dawu 同构，仅命令名 / 配置键 / 资源目录不同）
```

资源加载统一用 `Path(__file__).parent.parent.parent / "asserts" / ...` 定位；图片路径常用 `Path.cwd() / "src" / "asserts" / ...`。

## 开发命令

```bash
uv sync              # 安装依赖
uv run bot.py        # 运行机器人（OneBot v11 适配器）
uv run pyright       # 静态类型检查（pyrightconfig.json 指向 .venv）
```

若 `uv` 不在 PATH（例如非交互 SSH），可直接用 `.venv/bin/python` / `.venv/bin/pyright`；VM 上 `uv` 位于 `/opt/vlab/bin`。

无测试框架。改动后用 `uv run pyright` + 实际命令验证。

## 命令一览

| 命令 | 说明 |
|------|------|
| `大雾1 <实验名>` | 查询大雾1 题库原题图片，精确 / AI 模糊匹配 |
| `大雾1 ls` | 列出所有关键词 |
| `大雾2 <实验名>` | 查询二级大雾题库原题图片，精确 / AI 模糊匹配 |
| `大雾2 ls` | 列出所有关键词 |
| `/help` | 统一帮助：列出全部命令与用法 |

## 核心机制

### 大雾1 / 大雾2（同构）

- **注册**：`on_alconna(Alconna("大雾1", Args["name", str]), rule=Rule(check_group), priority=0, block=True)`。
- **群组过滤**：`config.py` 读 `dawu_allowed_groups` / `dawu2_allowed_groups`（两者独立），留空放行全部群。`_parse_groups` 兼容 str / int / list——NoneBot 加载自定义配置时会先 `json.loads`，单个群号会变成 int、JSON 数组会变成 list。
- **官方机器人群过滤**：QQ 官方事件没有数字群号，只有 `group_openid`（十六进制字符串，且按机器人加密，同一群在不同机器人下不同）。`check_group` 对 QQ 事件比对 `dawu_qq_allowed_groups` / `dawu2_qq_allowed_groups`，解析用 `_parse_openids`（**不能**沿用 `_parse_groups`，它按 `isdigit()` 过滤会把 openid 全丢掉）。
- **精确匹配**：`find_keywords`（定义在 `__init__.py`，不在 `keywords.py`）对每个别名做**子串**匹配（`alias in text`），因此一次输入可命中多个键。`keywords.py` 只负责顶层 `json.loads`。
- **缺失图片**：命中键但 `{键}.jpg` 不存在时，汇总提示缺失的图片文件名。
- **AI 回退**：精确未命中 → `ai_match(text, KEYWORDS)`，调用 OpenAI 兼容 `/chat/completions`。
- **速率限制**：按 `user_id` 每 60 秒最多 10 次。

### AI 调用

两个插件**各自持有一份 `ai_match.py`**（两份逐字节相同）。修改其中一个时，注意同步另一个。

- **配置**：`base_url` / `api_key` / `model_think`；`AI_TIMEOUT` 默认 180 秒，`AI_CONCURRENCY` 默认 5。
- **并发**：`asyncio.Semaphore(AI_CONCURRENCY)`，每个插件各一个信号量。
- **瞬时故障重试**：HTTP 500/502/503/504/529、网络错误、超时会重试 1 次（退避 1 秒）。
- **长连接与分段超时**：模块级 `ClientSession` 复用，`ClientTimeout(connect=30, sock_read=120, total=AI_TIMEOUT)`。
- **错误码**：`config` / `timeout` / `network` / `parse` / `http_<status>` / `unknown`，由 `src/utils/ai_error.py` 翻译成可区分原因的中文提示。注意「AI 成功但无匹配」不是错误（error 为 `None`）。

## 配置与安全

- 复制 `.env.secret.temple` → `.env.secret`，填入 `BASE_URL` / `API_KEY` / `MODEL_THINK`，以及可选的 `AI_TIMEOUT` / `AI_CONCURRENCY` / `DAWU_ALLOWED_GROUPS` / `DAWU2_ALLOWED_GROUPS`。
- **QQ 官方机器人**：`QQ_BOTS` 是 JSON 数组，元素为 `{id, secret, intent, use_websocket}`；`intent` 只要 `c2c_group_at_messages` 与 `group_members`。另有 `QQ_IS_SANDBOX`、`DAWU_QQ_ALLOWED_GROUPS`、`DAWU2_QQ_ALLOWED_GROUPS`。
- `.env`、`.env.secret` 均被 `.gitignore` 忽略，永不提交。分享日志时同样注意 API 响应中的敏感内容。

## 代码风格与命名

使用惯用 Python，4 空格缩进，需要处加类型注解，网络与 bot 操作一律用 async API。保持模块职责单一：命令路由在 `__init__.py`，配置在 `config.py`，外部 API 逻辑在 `ai_match.py`。函数、变量、模块用 `snake_case`，常量用 `UPPER_SNAKE_CASE`。除非任务明确要求改文案，否则保留现有中文命令与用户可见消息。

## 测试与验证

无测试框架，也不要在没有框架的情况下新增测试文件。改动行为后至少做到：

1. `uv run pyright`（或 `.venv/bin/pyright`）零错误；
2. 用真实命令走一遍关键路径：精确匹配、AI 回退、`ls`、`/help`、群组过滤（若改了配置）；
3. 资源名与关键词键保持一致，保证查表行为可预期。

VM 上有项目自身的 venv 和真实配置，可直接驱动插件真实 handler 做端到端验证（`nonebot.init()` + 加载 alconna + 直接调用 handler 并替换 `safe_finish`/`safe_send` 收集输出），比在本地造数据更接近真实。

## 提交规范

使用 Conventional Commits 风格，常带 scope，例如 `feat(dawu): 更新关键词`、`fix(dawu2): 修正帮助文案`。说明里写清行为变更、验证步骤；用户可见的改动附上机器人输出示例。

## 改动前必读的坑

- **变更链路**：本地 commit → 推到 GitHub → VM 上 `git pull --ff-only` → **重启 bot**（改 Python 必须重启才生效）。不要用 `ssh_upload` 直接覆盖 VM 上的文件，那会让 VM 与 git 记录分叉，后续 `pull` 冲突。
- **重启方式**（服务器上只跑官方 bot，不再需要 NapCat）：
  ```bash
  tmux kill-session -t rzyl-qq
  tmux new-session -d -s rzyl-qq "cd ~/RzyL && ONEBOT_WS_URLS='[]' .venv/bin/python bot.py > official-bot.log 2>&1"
  ```
  `ONEBOT_WS_URLS='[]'` 用于在没跑 OneBot 实现的机器上**关掉 v11 连接**，否则会无限重连刷日志。启动后确认日志里有 `Loaded adapters` 和 `QQ | Bot <AppID> connected`。
- **切图脚本不在仓库内**：`slice_dawu2.py` 只在本地维护（已 gitignore），键→页范围硬编码在脚本里。题库更新后必须**逐页**核对实验标题与页码，不能想当然——两次更新都是「某实验由单页变跨页」引起的整体偏移：v1.3「双臂电桥」单页变跨页（16-17），v2.0「双光栅实验」单页变跨页（27-28），其后所有实验页码 +1。核对方法：`pdftotext -f N -l N -layout` 逐页取标题，与 TOC 对照（印刷页 = 物理页 − 5）。
- **`二级大雾题库/`**：当前切片用 **`二级大雾题库v2.3.pdf`**（2026-11-03 版，42 页，正文 6–41；该文件封面标注的是 Version 2.2，与文件名不一致），LaTeX 源码（`main.tex` 等）不在仓库中；该目录整体被 gitignore。重新切片需先自备 PDF，并把脚本顶部的 `PDF` 常量指向新文件名。
- **题库小版本更新常常不改页码**：v2.1（改答案）、v2.3（补图/补题/改公式）都保持 42 页且目录不变，只需重切受影响的图，`EXPERIMENTS` 不用动。判断「哪些页真的变了」的可靠办法：先 `pdftotext` 去空白后逐页比对（可过滤掉整篇重排版带来的折行差异），再对剩余页做字符级 diff。
- **切图在本地做，不在 VM 上做**：VM 没有 poppler（`pdftoppm`）也没有 PIL，磁盘长期 90%+；本地切好后只提交 `src/asserts/dawu2/*.jpg`。

- **官方适配器必须 alconna ≥ 0.62.1**：0.60.4 的 `uniseg/adapters/qq/exporter.py` 在 `get_message_id` 里写死了事件白名单，不认 `GROUP_MESSAGE_CREATE`（全量消息模式），所有 matcher 的 rule 检查都会抛 `AssertionError`，表现为「消息收到了但一条都不回」。
- **官方网关只有 `/gateway/bot` 可用**：`GET https://api.sgroup.qq.com/websocket` 已废弃（426 Upgrade Required），adapter-qq 1.7.3 用的是 `/gateway/bot`，更老的版本连不上。
- **官方一条消息只能带一个媒体**：adapter 的 `_extract_qq_media` 取 `image[-1]`，多图会被静默丢弃。所以 `adapter_compat.compose_image_reply` 在 QQ 下只发第一张，其余列成「另有 N 个匹配」。
- **官方被动回复 5 分钟 / 最多 5 条**：回复要带事件 `msg_id` + 递增 `msg_seq`，超时报 `40034128`。单次请求的发送条数要控制在 2 条内（AI 回退时「正在尝试AI匹配…」+ 结果）。
- **群里默认要 @ 才收得到**，除非群主在「添加机器人 → 设置权限」里打开「接收全量消息」。打开后事件变成 `GROUP_MESSAGE_CREATE`，`content` 里的 @ 会被替换成 `<@member_openid>` / `<@all>`，由 `bot.py` 的 `event_preprocessor` 调 `strip_qq_mentions` 统一剥掉。
- **QQ 事件没有 `user_id` 字段**：只有 `get_user_id()`；`group_id` 在 QQ 下是 `group_openid` 字符串，`int(group_id)` 会 `ValueError`，白名单逻辑必须按适配器分支。

## 许可证

MIT
