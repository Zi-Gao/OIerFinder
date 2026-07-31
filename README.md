# OIerFinder

OIerFinder 是一个基于
[OIerDb-data-generator](https://github.com/OIerDb-ng/OIerDb-data-generator)
公开数据的 OI 选手信息查询与复合筛选工具。项目同时提供本地查询工具和部署在
Cloudflare Workers + D1 上的 Web 应用。

- 在线站点：[https://of.zigao.ac](https://of.zigao.ac)
- API 文档：[https://of.zigao.ac/docs](https://of.zigao.ac/docs)
- OpenAPI 3.1：[https://of.zigao.ac/openapi.json](https://of.zigao.ac/openapi.json)

## 功能

- 按比赛类型、年份、奖项等级、省份、学校、分数和排名组合筛选选手。
- 支持多条获奖条件取交集，例如查询“2023 年 NOI 金牌且 2021 年 NOIP
  一等奖”的选手。
- 按姓名首字母、性别和初中入学年份进一步筛选。
- 提供 React Web 界面、YAML 命令行查询和本地 Flask 页面。
- 查询并同步公开的洛谷奖项认证，将 NOI 系列奖项转换为查询条件。
- 自动跟踪上游数据内容，在内容未变化时避免重建和重写 D1。
- 对外提供 OpenAPI 3.1 契约和 Scalar 交互式 API 文档。

## 架构

| 组件 | 技术 | 位置 |
| --- | --- | --- |
| 在线前端 | React、Vite、Tailwind CSS | `cloudflare/worker/src/` |
| HTTP API | Hono、Cloudflare Workers | `cloudflare/worker/api/` |
| 云端数据库 | Cloudflare D1 | `cloudflare/migrations/` |
| 本地查询 | Python、SQLite、Flask | 仓库根目录、`utils/` |
| 上游数据 | Git submodule | `oierdb-data/` |
| 自动部署 | GitHub Actions | `.github/workflows/sync-oier-data.yml` |

## 快速开始

### 环境要求

- Git
- Python 3.10+
- [uv](https://docs.astral.sh/uv/)
- Node.js 22+（仅开发 Cloudflare Worker 时需要）

### 安装

```bash
git clone --recursive https://github.com/Zi-Gao/OIerFinder.git
cd OIerFinder
uv sync --locked
```

如果克隆时没有获取子模块：

```bash
git submodule update --init --recursive
```

### 生成本地数据库

先运行上游生成器，再构建 SQLite：

```bash
(cd oierdb-data && ../.venv/bin/python main.py)
uv run python create_db.py
```

生成的 `oier_data.db` 仅供本地运行使用，已被 Git 忽略。可以通过
`OIER_DATABASE_PATH` 指定其他输出位置：

```bash
OIER_DATABASE_PATH=/tmp/oier_data.db uv run python create_db.py
```

## 本地使用

### 命令行查询

复制并修改 [sample_config.yml](sample_config.yml)，然后执行：

```bash
uv run python oierfinder.py --config sample_config.yml
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
npm run dev
```

常用检查：

```bash
npm test
npm run lint
npm run build
```

`npm test` 除了覆盖查询逻辑，还会校验 OpenAPI 3.1 文档，并确保每个实际注册的业务
路由都出现在 API 契约中。

### API

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
D1。该同步是公开写操作；历史奖项不会因为洛谷当前页面缺失而删除。

请求参数、响应模型、示例和错误码以
[在线 API 文档](https://of.zigao.ac/docs) 为准。

## 自动同步与部署

工作流
[`.github/workflows/sync-oier-data.yml`](.github/workflows/sync-oier-data.yml)
在以下情况运行：

- 每 6 小时检查一次上游默认分支。
- 从 GitHub Actions 页面手动运行，可指定完整上游 SHA 或强制更新。
- `main` 分支中的 Worker、迁移、数据脚本或工作流发生变化。

### 数据变更判断

工作流先比较上游 Git SHA。需要检查数据时，再对生成的 `result.txt` 和规范化后的
`static.json` 计算 `source_data_hash`：

| 情况 | 行为 |
| --- | --- |
| 上游 SHA 和数据内容都未变化 | 跳过数据构建与上传 |
| 上游 SHA 变化，但数据内容未变化 | 只推进 active 上游 SHA |
| 数据内容变化或手动强制更新 | 构建完整快照，暂存上传并事务切换 D1 |
| 本仓库部署文件变化 | 测试并部署 Worker，不因此重写核心数据 |

核心数据使用完整快照而不是逐行增量，因为学校、比赛和记录 ID 依赖上游生成顺序，
不是稳定业务主键。洛谷奖项同步则使用增量插入与更新。

SQLite 只存在于 GitHub Runner 的临时目录，并在工作流结束时删除。发布 artifact
仅保留统计 JSON 和发布清单，不包含 `oier_data.db`。

### GitHub Environment

创建名为 `production` 的 Environment，并配置：

| Secret | 用途 |
| --- | --- |
| `CLOUDFLARE_ACCOUNT_ID` | Cloudflare 账号 ID |
| `CLOUDFLARE_DATABASE_ID` | 目标 D1 数据库 ID |
| `CLOUDFLARE_D1_API_TOKEN` | 仅用于 D1 读写 |
| `CLOUDFLARE_WORKERS_API_TOKEN` | 构建并部署 Worker |

建议按目标账号和资源限制 Token 权限。Worker 的可选 `ADMIN_SECRET` 应通过 Cloudflare
Secret 单独配置，工作流部署使用 `--keep-vars` 保留现有变量与 Secret。

### 手动部署

`update_cloudflare.py` 会更新子模块、生成上游数据、在临时目录构建 SQLite、同步 D1、
创建索引并部署 Worker。执行前需要准备 Cloudflare 环境变量并激活虚拟环境：

```bash
source .venv/bin/activate
python update_cloudflare.py
```

生产环境优先使用 GitHub Actions，以保留可追踪的版本、数据哈希和运行记录。

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
├── oierdb-data/             # 上游数据生成器子模块
├── utils/                   # 本地查询与洛谷解析
├── app.py                   # 本地 Flask 页面
├── create_db.py             # SQLite 构建
├── oierfinder.py            # YAML 命令行查询
└── update_cloudflare.py     # 手动云端更新流程
```

## 数据与隐私

核心数据来自
[OIerDb-ng/OIerDb-data-generator](https://github.com/OIerDb-ng/OIerDb-data-generator)。
项目仅聚合公开记录。使用、部署或再分发数据时，请遵守数据源要求、适用法律法规，并
尊重选手隐私。
