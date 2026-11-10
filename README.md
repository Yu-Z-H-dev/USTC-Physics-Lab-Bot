# RzyL - 物理实验查询机器人

基于 NoneBot2 的 QQ 机器人，为USTC 大学物理-综合实验 和 大学物理-基础实验 的入门测和出门测题目提供解答图片查询：精确匹配 + AI 模糊匹配。
同时支持 **QQ 官方机器人（开放平台）** 与 **OneBot v11** 两套适配器。

开发者有自行部署的[QQbot](https://bot.q.qq.com/s/wCmsrOOoTu)，如有需要可以将其接入群聊。

## 功能特性

- **关键词匹配**：精确子串匹配 + AI 模糊匹配回退
- **图片查询**：按实验名返回题库原题图片（入门测 / 出门测题目）
- **多关键词**：一次输入可命中多个实验
- **群组白名单**：可按群号 / 群 openid 限制可用范围
- **速率限制**：每用户每 60 秒最多 10 次请求
- **双适配器**：同一份业务代码，同时兼容 QQ 官方机器人与 OneBot v11
- **AI 请求优化**：长连接复用 + 分段超时 + 可配置并发

## 命令

| 命令 | 说明 |
|------|------|
| `大雾1 <实验名>` | 查询大雾1 题库原题图片，精确 / AI 模糊匹配 |
| `大雾1 ls` | 列出所有关键词 |
| `大雾2 <实验名>` | 查询二级大雾题库原题图片，精确 / AI 模糊匹配 |
| `大雾2 ls` | 列出所有关键词 |
| `/help` | 统一帮助：列出全部命令与用法 |

发 `/help`（不带斜杠的 `help` 也可以）会回复完整用法：

```text
物理实验查询机器人

用法：
  大雾1 <实验名>   大雾1 题库原题图片（例：大雾1 杨氏模量）
  大雾2 <实验名>   二级大雾题库原题图片（例：大雾2 霍尔效应）
  大雾1 ls         查看大雾1 的全部关键词
  大雾2 ls         查看大雾2 的全部关键词
  /help            显示本帮助

精确匹配不到时会自动尝试 AI 模糊匹配；
一次输入命中多个实验时，会列出全部匹配项。
```

> 帮助只有这一个入口。旧的 `大雾1 help` / `大雾2 help` 已移除，发送后不会响应（也不会触发 AI 匹配）。
> `/help` 不受群白名单限制，任何群里都能用。

## 安装

```bash
uv sync
```

## 配置

复制 `.env.secret.temple` 为 `.env.secret`，并配置 `.env`（NoneBot 与连接方式）。

### `.env.secret`（AI 匹配与群组过滤）

```env
BASE_URL=https://api.example.com/v1   # OpenAI 兼容 API 地址
API_KEY="your_api_key"
MODEL_THINK=""                        # 模糊匹配使用的模型
AI_TIMEOUT=60                         # AI 请求总超时（秒）
AI_CONCURRENCY=5                      # AI 并发上限

DAWU_ALLOWED_GROUPS=                  # 大雾1 的群号白名单（逗号分隔，留空=全部放行）
DAWU2_ALLOWED_GROUPS=                 # 大雾2 的群号白名单

QQ_BOTS=                              # QQ 官方机器人，JSON 数组，见模板注释
QQ_IS_SANDBOX=false
DAWU_QQ_ALLOWED_GROUPS=               # 官方机器人的 group_openid 白名单
DAWU2_QQ_ALLOWED_GROUPS=
```

### `.env`（NoneBot 运行配置）

```env
HOST=0.0.0.0
PORT=8080
COMMAND_START=[""]
COMMAND_SEP=[""]
ENVIRONMENT=secret
DRIVER=~aiohttp

# OneBot v11 连接（不用时留空数组即可关闭）
ONEBOT_ACCESS_TOKEN=
ONEBOT_WS_URLS=["ws://127.0.0.1:3001"]
```

> `.env` 与 `.env.secret` 已被 `.gitignore` 忽略，永不提交。

## 项目结构

```
RzyL/
├── bot.py                      # 入口：init + 注册适配器 + load_plugins
├── pyproject.toml / uv.lock    # 依赖
├── pyrightconfig.json          # 类型检查配置
├── .env.secret.temple          # 配置模板
└── src/
    ├── asserts/                # 静态资源（图片 + 关键词 JSON）
    │   ├── dawu/               #   大雾1
    │   └── dawu2/              #   大雾2（27 个实验）
    ├── utils/
    │   ├── adapter_compat.py   #   跨适配器：图片段 / 消息组装 / 剥 <@openid>
    │   ├── safe_send.py        #   发送容错
    │   └── ai_error.py         #   AI 错误码 → 中文提示
    └── plugins/
        ├── dawu/               # 大雾1
        └── dawu2/              # 大雾2（与 dawu 同构）
```

## 部署（QQ 官方机器人）

1. 在 [QQ 开放平台](https://q.qq.com) 创建群机器人，拿到 AppID / AppSecret；
2. `.env.secret` 写入 `QQ_BOTS`（WebSocket 长连接），intent 只需
   `c2c_group_at_messages` 与 `group_members`；
3. 启动：

   ```bash
   ONEBOT_WS_URLS='[]' .venv/bin/python bot.py    # 只跑官方 bot 时关掉 v11 连接
   ```

4. 群里默认需要 @ 机器人；群主在「添加机器人 → 设置权限」里打开「接收全量消息」后可直接发命令。

## AI 调用

两个插件各持有一份 `ai_match.py`（逐字节相同），调用 OpenAI 兼容的 `/chat/completions`：

- 模块级 `ClientSession` 复用，`ClientTimeout(connect=30, sock_read=120, total=AI_TIMEOUT)`；
- `asyncio.Semaphore(AI_CONCURRENCY)` 控制并发；
- HTTP 500/502/503/504/529、网络错误、超时重试 1 次；
- 错误码 `config` / `timeout` / `network` / `parse` / `http_<status>` / `unknown`，由 `ai_error.py` 翻译成中文。

## 技术栈

- **框架**：NoneBot2（Python 3.11）
- **适配器**：nonebot-adapter-qq（QQ 官方）、nonebot-adapter-onebot（v11）
- **命令解析**：Alconna
- **HTTP**：aiohttp

## 开发

```bash
uv run bot.py        # 运行
uv run pyright       # 类型检查
```

## 特别鸣谢

本仓库代码由 https://github.com/RaymondzyLei/RzyL 进行加工之后得到

如对解答有疑问，可以发邮件到[邮箱](work.yzh@outlook.com)

## 许可证

MIT
