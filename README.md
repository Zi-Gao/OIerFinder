<div align="center">

# OIerFinder

**从公开竞赛记录中，找到符合条件的 OI 选手。**

基于 [OIerDb](https://github.com/OIerDb-ng/OIerDb) 的复合查询工具，
提供在线页面、HTTP API 和本地查询方式。

[在线使用](https://of.zigao.ac) · [API 文档](https://of.zigao.ac/docs) · [OpenAPI 3.1](https://of.zigao.ac/openapi.json)

</div>

---

[功能](#功能) · [快速开始](#快速开始) · [本地使用](#本地使用) ·
[Worker 开发](#cloudflare-worker-开发) · [API](#api) ·
[同步与部署](#自动同步与部署) · [项目结构](#项目结构)

## 功能

- **复合筛选**：按比赛类型、年份、奖项、省份、学校、分数和排名组合查询；
  多条获奖条件取交集，例如同时获得 2023 年 NOI 金牌和 2021 年 NOIP 一等奖。
- **选手条件**：进一步按姓名首字母、性别和初中入学年份筛选。
- **洛谷导入**：查询公开的洛谷奖项认证，将可识别的 NOI 系列奖项转换为查询条件。
- **多种使用方式**：在线页面、HTTP API、YAML 命令行查询和本地 Flask 页面。
- **增量同步**：跟踪上游数据，校验快照后仅向 Cloudflare D1 写入变化行。

### 在线查询

| 入口 | 用途 |
| --- | --- |
| **UI Builder** | 使用表单组合选手条件和多条获奖条件 |
| **Raw JSON** | 直接编辑查询请求，与表单共享查询条件 |
| **Luogu UID** | 获取洛谷奖项，将可识别的条件导入表单 |

页面还支持设置结果数量、切换深色模式和提供可选的管理员密钥。密钥仅保存在当前
页面内存中，刷新后需要重新输入。

## 架构

| 组件 | 技术 | 位置 |
| --- | --- | --- |
| 在线前端 | React、Vite、Tailwind CSS | `cloudflare/worker/src/` |
| HTTP API | Hono、Cloudflare Workers | `cloudflare/worker/api/` |
| 云端数据库 | Cloudflare D1 | `cloudflare/migrations/` |
| 本地查询 | Python、SQLite、Flask | 仓库根目录、`utils/` |
| 上游数据 | Git submodule | `oierdb-data/generator/`、`oierdb-data/data/` |
| 自动部署 | GitHub Actions | `.github/workflows/sync-oier-data.yml` |

## 快速开始

只想查询？直接打开[在线站点](https://of.zigao.ac)。以下步骤用于在本地生成数据库
并运行 Python 查询工具；Worker 开发另见[下文](#cloudflare-worker-开发)。

### 环境要求

- Git
- Python 3.10+
- [uv](https://docs.astral.sh/uv/)
- Node.js 22+（仅开发 Cloudflare Worker 时需要）

### 1. 获取项目并安装依赖

```bash
git clone --recursive https://github.com/Zi-Gao/OIerFinder.git
cd OIerFinder
uv sync --locked
```

如果克隆时没有获取子模块：

```bash
git submodule update --init --recursive
```

从旧数据源升级的已有克隆，需要先同步子模块的新地址，再检出仓库记录的版本：

```bash
git submodule sync -- oierdb-data
git submodule update --init --recursive
```

### 2. 生成本地数据库

先运行上游生成器，再构建 SQLite：

```bash
(cd oierdb-data/generator && ../../.venv/bin/python main.py)
uv run python create_db.py
```

生成器从 `oierdb-data/data/` 读取原始数据，产物位于
`oierdb-data/generator/dist/`。导入时从同一上游版本的 `generator/util.py` 读取
省份、奖项和比赛类型编号表，将编号转换为查询接口使用的名称；废弃学校的占位项
保留原始 ID，避免比赛记录关联到错误学校。

生成的 `oier_data.db` 仅供本地运行使用，已被 Git 忽略。可以通过
`OIER_DATABASE_PATH` 指定其他输出位置：

```bash
OIER_DATABASE_PATH=/tmp/oier_data.db uv run python create_db.py
```

本地 CLI 和 Flask 页面默认读取仓库根目录的 `oier_data.db`；使用其他输出位置时，
需将数据库放回该路径才能供它们使用。

## 本地使用

### 命令行查询

复制并修改 [sample_config.yml](sample_config.yml)，然后执行：

```bash
cp sample_config.yml config.yml
# 编辑 config.yml
uv run python oierfinder.py --config config.yml
```

`records` 中的每个条件组都必须由同一名选手的某条记录满足，多个条件组之间为 AND
关系。

### Flask 页面

确保仓库根目录存在 `oier_data.db`，然后运行：

```bash
uv run python app.py
```

默认访问 `http://127.0.0.1:5000`。

### 洛谷奖项文本转换

```bash
uv run python luogu2yml.py \
  --input sample_luogu_awards.txt \
  --output config.yml
```

生成的 YAML 可以直接交给本地命令行查询工具使用。

## Cloudflare Worker 开发

```bash
cd cloudflare/worker
npm ci
npx wrangler d1 migrations apply DB --local
npm run dev
```

默认访问 `http://localhost:5173`。本地开发使用独立的 D1 数据库，上面的迁移命令
只创建表和同步保护，不会自动导入选手数据，也不会连接或修改线上数据库；仅启动页面
即可查看界面，查询真实数据需要另行准备本地数据。`create_db.py` 生成的 SQLite
文件供本地 Python 工具使用，不会自动成为 Worker 的 D1 数据库。

常用检查：

```bash
npm test
npm run lint
npm run build
```

`npm test` 除了覆盖查询逻辑，还会校验 OpenAPI 3.1 文档，并确保每个实际注册的业务
路由都出现在 API 契约中。

## API

例如，查询 2023 年获得 NOI 金牌的选手：

```bash
curl -X POST https://of.zigao.ac/query-oier \
  -H 'Content-Type: application/json' \
  -d '{"record_filters":[{"contest_type":"NOI","level":"金牌","year":2023}],"oier_filters":{},"limit":20}'
```

每个 `record_filters` 条件都需要由该选手的至少一条记录满足，条件之间为 AND。
完整字段、示例和错误码见 [交互式 API 文档](https://of.zigao.ac/docs)。

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| `POST` | `/query-oier` | 按记录和选手属性筛选 |
| `GET` | `/luogu/to_query` | 将洛谷奖项转换为查询条件 |
| `GET` | `/luogu/prizes` | 查询或同步洛谷奖项 |
| `GET` | `/version` | 查看应用与 active 上游数据 SHA |
| `GET` | `/openapi.json` | 获取 OpenAPI 3.1 契约 |
| `GET` | `/docs` | 打开 Scalar API 文档 |

所有业务接口都可以匿名调用。配置可选的 `X-Admin-Secret` 后，管理员请求可以放宽
`/query-oier` 的部分资源限制，并在服务端错误响应中看到调试信息。不要在公开客户端
中保存管理员密钥。

洛谷接口在使用 `sync=true` 或 `sync=1` 时会从洛谷读取最新奖项并在后台增量写入
D1。该同步是公开写操作；历史奖项不会因为洛谷当前页面缺失而删除。响应中的
`synced=true` 表示已成功读取并安排后台写入，并不保证后台写入已经完成。

## 自动同步与部署

工作流
[`.github/workflows/sync-oier-data.yml`](.github/workflows/sync-oier-data.yml)
在以下情况运行：

- 每天北京时间 09:17（UTC 01:17）检查一次上游默认分支。
- 从 GitHub Actions 页面手动运行，可指定完整上游 SHA 或强制重新生成和比较。
- `main` 分支中的 Worker、迁移、数据脚本或工作流发生变化。

### 数据变更判断

工作流先比较上游 Git SHA 和入库规则版本。需要检查数据时，再对生成的 `result.txt`、规范化后的
`static.json` 以及同一版本的省份、奖项和比赛类型编号表计算 `source_data_hash`。
编号含义变化也会触发数据更新，单纯的生成器代码或 JSON 排版变化不会导致重写：

| 情况 | 行为 |
| --- | --- |
| 上游 SHA 和数据内容都未变化 | 跳过数据构建与上传 |
| 上游 SHA 变化，但数据内容未变化 | 只推进 active 上游 SHA |
| 数据内容变化或入库规则变化 | 完整生成并校验快照，仅事务写入新增、修改、删除的行 |
| 手动 `force=true` | 强制重新生成和比较；不绕过校验，不强制全量上传 |
| 本仓库部署文件变化 | 测试并部署 Worker，不因此重写核心数据 |

完整数据在 Runner 上生成，差异在本地计算。`Record` 按 `(oier_uid, contest_id)`
比较，忽略重建时会变化的自增 `id`，保留线上已有记录的内部编号。选手合并或拆分
产生的旧行删除和新行插入也包含在差量中。`LuoguPrizes` 独立维护，不参与核心发布。

### 快照与发布状态

工作流自动创建同仓库的独立 `data-state` 分支，存放以下文件：

```text
oier_data.db.gz       # 规范排序的四张核心表，不包含连接凭据或其他表
contest_stats.json   # 与该快照逐项核对的 Worker 统计
manifest.json        # 文件校验、业务数据校验、入库规则版本、来源与行数
```

先保存不可变候选 commit，再部署兼容 Worker，最后在同一个 D1 事务中应用差量、
校验结果并更新 `DataRelease.snapshot_commit`。D1 的指针是成功基准，分支 HEAD
可能是尚未发布的候选版本，不能直接当成线上状态。上传失败不写核心表；事务失败
保留旧数据与旧指针；响应丢失后先查询发布记录，禁止盲目重发。

首次接入只读线上核心表制作基准，确认读取期间版本和变更计数未变化，存档成功后
才补上快照指针；不会重写已有核心数据。没有已有 `active` 发布记录、基准损坏或
缺失时会停止，不自动尝试全量覆盖空库或修复不明状态。

迁移 `0004` 为核心表增加事务内写入门禁和变更计数触发器。旧脚本和未开启门禁的
直接写入会被拒绝；发布器在同一事务中开启门禁、写入并关闭门禁。每次增删改都会
在同一事务里推进计数。
大差量通过 JSON 参数打包为批量 SQL，每组保留逐行业务键、旧值和写入结果校验，
减少语句解析和响应数量。所有分组仍由同一个 D1 batch 原子提交，不拆分正式表事务。
参数按列位置压缩并用 UTF-8 发送，避免重复字段名及中文转义放大请求。
线上计数与成功快照不符、保护表/触发器/索引被改动时停止发布。每条差量都有旧值、
唯一性和写入结果断言，数据、发布指针和估算写入记账一起提交或回滚。
命令行入口会核对目标库与 Worker 的 `DB` 绑定一致；计划还绑定具体账号和数据库，
防止准备后更换环境把差量写到另一个库。

项目不设置单次或每日写入额度，也不额外限制业务行操作数或设置 4 MiB 请求阈值。
计划中的估算写入及历史命名为 `OierSyncBudget` 的日累计记录仅用于审计，不拦截发布；
旧的 `D1_SYNC_MAX_ESTIMATED_WRITES`、`D1_SYNC_DAILY_WRITE_BUDGET` 配置已移除。
每条 SQL 仍校验 D1 的
100,000 字节及 100 个绑定参数限制，整批请求受服务端 30 秒执行时限等
[平台限制](https://developers.cloudflare.com/d1/platform/limits/)约束。
估算包含断言、变更计数和索引开销，不等同 Cloudflare 账单。实际可用额度由
[Cloudflare 套餐与账号总用量](https://developers.cloudflare.com/d1/platform/pricing/)决定。
校验失败或 Cloudflare 拒绝写入时保留失败记录，不拆分正式表事务或回退全量上传。
`publish-result.json` 和工作流摘要会区分以下状态：

- `blocked`：发布前校验失败，未尝试写核心表。
- `not_committed`：写入失败后已重新读取并确认旧发布仍有效，下次从该成功快照重新规划。
- `outcome_unknown`：超时或响应异常后暂时无法确认结果，停止写入；后续先读取 D1 发布记录再决定是否更新。
- `conflict`：核验到非预期的发布身份，停止并要求审计。
- `committed_response_lost`：响应丢失，但重新读取确认目标已提交，不重复写入。

Cloudflare 7500、7429、网络连接等暂时性错误，只有重新读取确认本次未提交，才会延迟重试，
最多尝试三次；每次重试仍核对成功基准，并受同一事务的发布身份与变更计数断言保护。
Worker 部署使用锁定依赖中的 Wrangler；10013 或网络类暂时错误会延迟重试，最多三次。
失败的 job 保持失败状态，同时保存计划、错误、尝试次数和恢复建议。Cloudflare 配额耗尽时不立即循环重试；
下次每日任务会先核验线上发布状态，再从实际成功版本比较上游。

数据分支采用普通追加提交，不强推或自动改写历史。旧快照属于 Git 历史；保留策略
需要另行规划，必须保留 D1 当前引用的 commit。Runner 的 SQLite 与下载快照在
结束时清理；Actions 的审计 artifact 只保留清单、差量数量和实际读写统计 14 天。

核心实现及测试位于 `cloudflare/script/incremental_sync.py`、`incremental_d1.py`、
`sync_snapshot.py` 及对应 `test_*.py`。`prepare` 只规划和建立首次基准，`archive`
只保存候选，`publish` 才能写核心表。Worker 与 D1 不属于跨服务事务，新 Worker
必须兼容发布前的旧数据。

### GitHub Environment

创建名为 `production` 的 Environment，并配置：

| Secret | 用途 |
| --- | --- |
| `CLOUDFLARE_ACCOUNT_ID` | Cloudflare 账号 ID |
| `CLOUDFLARE_DATABASE_ID` | 目标 D1 数据库 ID |
| `CLOUDFLARE_D1_API_TOKEN` | 仅用于 D1 读写 |
| `CLOUDFLARE_WORKERS_API_TOKEN` | 构建并部署 Worker |

保存快照的 job 需要 `contents: write`；`data-state` 的分支规则须允许该 Action
普通推送。工作流仍只监听 `main` 的 push，数据分支提交不会递归触发同步。

建议按目标账号和资源限制 Token 权限。Worker 的可选 `ADMIN_SECRET` 应通过 Cloudflare
Secret 单独配置，工作流部署使用 `--keep-vars` 保留现有变量与 Secret。

### 手动部署

生产数据发布使用同一个受保护的 GitHub Actions 流程。可以在 Actions 页面手动运行，
也可以通过 GitHub CLI 触发：

```bash
gh workflow run sync-oier-data.yml --ref main -f force=true
```

旧的 `update_cloudflare.py` 全量上传路径不再用于日常生产发布。旧上传器默认拒绝
全量写入；显式 `--allow-initial-full-upload` 只保留给尚未安装增量保护的旧式初始导入。
安装 `0004` 后，即使还没建立快照指针，也会在上传暂存表之前拒绝旧路径。不要
通过手工改动 `DataRelease` 或写入门禁来跳过基准或漂移检查。

## 项目结构

```text
.
├── .github/workflows/       # 自动同步与部署
├── cloudflare/
│   ├── migrations/          # D1 migrations
│   ├── script/              # D1 上传、指纹和索引脚本
│   └── worker/
│       ├── api/             # Hono API 与 OpenAPI
│       └── src/             # React 前端
├── oierdb-data/             # OIerDb 子模块（generator/ 与 data/）
├── utils/                   # 本地查询与洛谷解析
├── app.py                   # 本地 Flask 页面
├── create_db.py             # SQLite 构建
├── oierfinder.py            # YAML 命令行查询
└── update_cloudflare.py     # 旧式全量更新脚本，不用于日常生产部署
```

## 数据与隐私

核心数据来自
[OIerDb-ng/OIerDb](https://github.com/OIerDb-ng/OIerDb)。旧的
`OIerDb-data-generator` 已合并到该仓库，自动同步跟踪新仓库的默认分支。
项目仅聚合公开记录。使用、部署或再分发数据时，请遵守数据源要求、适用法律法规，并
尊重选手隐私。
