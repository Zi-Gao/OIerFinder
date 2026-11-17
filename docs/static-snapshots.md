# 静态竞赛数据与洛谷 D1

核心竞赛数据改为经过校验的静态 SQLite 快照。网页在 Web Worker 中查询，独立 Node 服务保留 HTTP 查询能力；洛谷奖项仍由原 Cloudflare Worker 读取和增量写入 `LuoguPrizes`。浏览器查询不会请求 `/query-oier`，也不把管理员密钥交给本地查询线程。

## 本地准备数据

先按 README 生成 `oier_data.db`，再执行：

```sh
uv run python cloudflare/script/build_static_snapshot.py \
  --database oier_data.db \
  --upstream-sha "$(git -C oierdb-data rev-parse HEAD)" \
  --worker-version "$(git rev-parse HEAD)" \
  --source-data-hash "$(uv run python cloudflare/script/data_fingerprint.py)"
```

产物放在 `cloudflare/worker/public/data/`，不提交 Git。构建器重新生成仅含四张核心表的数据库，校验业务键、外键、统计和逻辑内容，再加入浏览器需要的索引。原数据库中的洛谷表、发布表或其他私有表不会进入下载包。

`manifest.json` 是小型版本指针，记录来源版本、数据库与统计文件的摘要、大小和行数。压缩数据库按最多 8 MB 分片，所有资源路径包含不可变 snapshot_id。先写完所有资源，再替换 manifest；单个文件不依赖 HTTP Range。页面每次查询前检查版本，全部校验并打开新数据库后才替换旧数据库。

## 网页预览

```sh
cd cloudflare/worker
npm ci
npm run dev
```

Node.js 使用 24 或更高版本。网页第一次搜索时下载并准备数据，显示下载进度；SQLite 在独立线程运行。浏览器允许存储时缓存已验证的资源。缓存被禁用或空间不足时继续用内存查询；损坏缓存按摘要识别并重新下载。更新完成后清理旧资源缓存。

已完整缓存的版本在网络不可用时仍可查询，结果标为 SAVED DATA，并显示实际数据 SHA。新版本下载或校验失败时明确报错，不将不同版本拼成一个数据库。若发布切换恰好使旧资源不可用，重新点击搜索会读取最新 manifest 后再尝试。首次尚未下载数据时不能离线查询。

核心查询不再受 D1 行数或 Worker CPU 限制，但仍受用户设备的内存和性能限制。下载包包含索引，比只含业务表的原始归档大。浏览器不支持 WASM 或 gzip 解压时会提示使用较新浏览器或 HTTP API。

## 保留 HTTP 查询 API

在仓库的 `cloudflare/worker` 目录运行：

```sh
SNAPSHOT_MANIFEST="$PWD/public/data/manifest.json" npm run query-api
```

默认仅监听 `127.0.0.1:8788`，提供 `POST /query-oier`、`GET /version` 和 `GET /health`。请求与成功响应保留现有结构，匿名服务端查询仍执行原来的资源约束。它和浏览器共用 SQL、筛选、去重及 NULL 值语义。

生产服务可将 `SNAPSHOT_MANIFEST` 设为网站的 `https://of.zigao.ac/data/manifest.json`。服务启动时准备数据，之后定期检查版本；代理指定新 snapshot_id 时立即检查。每个查询固定一个完整快照。数据损坏、版本不匹配或下载失败返回 503，不回退到旧 D1 核心表。

查询在独立线程串行执行，主进程限制待处理请求数、请求大小及超时。耗时过长时终止查询线程并恢复服务，避免一个查询永久阻塞接口。`ADMIN_SECRET` 可按原契约放宽公开查询限制。`QUERY_BACKEND_SECRET` 可用于限制独立服务只接收 Cloudflare 代理请求；配置后 Cloudflare 与独立服务必须使用相同值。

可选 Docker：在 `cloudflare/worker` 目录构建，文件由现有快照引导：

```sh
docker build -f server/Dockerfile -t oier-query .
docker run --rm -p 127.0.0.1:8788:8788 \
  -v "$PWD/public/data:/snapshots:ro" \
  -e SNAPSHOT_MANIFEST=/snapshots/manifest.json oier-query
```

生产需要常驻服务的机器或容器平台，并在外层提供 HTTPS。首次发布前，可用本地 manifest/只读数据目录启动服务；网站第一份静态数据上线后，再改为远端 manifest 自动刷新，避免网站与 API 相互等待首次初始化。

Cloudflare 的公开路径仍为 `POST /query-oier`。配置 `QUERY_API_ORIGIN` 指向独立服务 HTTPS 源站；本地开发可以使用 `http://127.0.0.1:8788`。可在未提交 Git 的 `.dev.vars` 配置。未设置源站时接口返回明确的 503，网页本地查询和洛谷接口独立运行。生产切换前必须完成服务部署和代理联调。

## 工作流与 D1

新版 Actions 冻结上游 SHA → 生成并验证数据 → 打包静态资源 → 测试并构建 → 检查查询服务健康 → 部署兼容 Worker 和静态数据。它不调用旧 `incremental_sync.py publish`，也不向 OIer、Record 等 D1 核心表写入。旧 D1 核心数据保留，不自动清空；旧增量脚本仅作历史工具。

部署前配置 GitHub 仓库变量 `QUERY_API_ORIGIN`。服务健康检查失败或变量缺失时停止部署，避免悄悄停用用户要求保留的查询 API。若配置了后端共享密钥，也要提供 GitHub 的 `QUERY_BACKEND_SECRET` 以及 Cloudflare Worker 对应密钥。

日常部署只使用 Cloudflare Workers 发布权限。只有首次建立洛谷表时才手动选中 `initialize_luogu`，使用现有 D1 token 并执行 `0001_create_luogu_prizes_table.sql`；不会运行历史核心表迁移。已存在的洛谷表不需要重复初始化。

`/luogu/prizes?sync=1` 和 `/luogu/to_query?sync=1` 保持原逻辑：从洛谷读取、与已存奖项合并，然后后台增量写 D1。它们仍消耗 D1 额度，核心数据切换静态存储并不会取消这部分计量。

目前线上工作流维持禁用状态。完成独立服务部署、设置来源地址并验证完整链路后再恢复；不在本次代码编写中自动启用或发布。
