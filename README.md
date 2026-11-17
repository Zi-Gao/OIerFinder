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
- **静态数据更新**：跟踪上游并发布经过校验的 SQLite 快照，网页在浏览器内查询，洛谷奖项继续增量写入 D1。

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
| 核心竞赛数据 | 静态 SQLite 快照、浏览器 WASM 查询 | `cloudflare/worker/src/data/` |
| 查询 API | 独立 Node.js 快照服务、Cloudflare 代理 | `cloudflare/worker/server/` |
| 洛谷奖项数据库 | Cloudflare D1 | `cloudflare/migrations/` |
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
npx wrangler d1 execute DB --local --file ../migrations/0001_create_luogu_prizes_table.sql
npm run dev
```

默认访问 `http://localhost:5173`。核心查询需要先生成静态快照；洛谷功能使用独立的本地 D1，不会修改线上数据。完整的数据打包、浏览器缓存及 API 服务启动方式见[静态数据说明](docs/static-snapshots.md)。

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

核心数据使用静态快照发布，不再向 D1 导入选手和成绩。洛谷同步继续读写 D1。

工作流 [`.github/workflows/sync-oier-data.yml`](.github/workflows/sync-oier-data.yml) 保留每日北京时间 09:17、手动运行和相关源码变动三种触发方式。线上工作流在迁移期间保持禁用，完成服务部署和联调后再恢复。

发布步骤是：固定上游 SHA、生成完整数据库、校验业务数据与外键、加入查询索引、生成带摘要的压缩分片和 manifest、测试、检查独立 API 服务健康，最后部署静态数据与兼容 Worker。整个流程不执行 D1 核心表发布事务，因此不会因年度 CSP 数据入库产生几十万次 D1 写入。

浏览器首次查询下载并校验数据，后续复用本机缓存；同一查询固定一个完整版本。`POST /query-oier` 仍然保留，由 Cloudflare 代理到独立快照查询服务，查询逻辑与浏览器一致。源站未配置、不可用或尚未加载相同版本时返回 503，不查询旧 D1 核心数据。`GET /version` 报告静态快照对应的上游 SHA。

生产发布需要 `CLOUDFLARE_ACCOUNT_ID`、`CLOUDFLARE_WORKERS_API_TOKEN` 和仓库变量 `QUERY_API_ORIGIN`。首次建立洛谷表时可手动选择 `initialize_luogu`，该步骤才使用 `CLOUDFLARE_D1_API_TOKEN`。日常核心数据更新不需要 D1 写入权限。可选的 `QUERY_BACKEND_SECRET` 必须在查询服务、Cloudflare Worker 和健康检查中保持一致。

详细的本地准备、独立 API 部署、首次迁移顺序、版本校验与恢复方式见[静态数据与洛谷 D1](docs/static-snapshots.md)。旧增量同步和全量上传脚本不再用于日常生产发布；不要用它们覆盖仍然保留的历史 D1 核心表。

## 项目结构

```text
.
├── .github/workflows/       # 自动同步与部署
├── cloudflare/
│   ├── migrations/          # D1 migrations
│   ├── script/              # 静态快照构建、指纹及历史 D1 工具
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
