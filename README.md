# OIerFinder

OIerFinder 是一个基于 [OIerDb-ng](https://github.com/OIerDb-ng/OIerDb-data-generator) 数据源的选手信息查询与筛选工具。本项目提供了一套完整的流水线，涵盖了从原始数据同步、本地数据库构建、多维度筛选引擎到云端（Cloudflare）部署的全过程。

## 核心功能

- **多维筛选引擎**：支持基于 YAML 配置的复合条件查询，能够根据姓名、性别、年级、省份、获奖等级、分数排名及 DB 评分进行精准筛选。
- **关联记录匹配**：支持跨比赛筛选，例如“寻找在 2023 年获得过 NOI 金牌且在 2021 年获得过 NOIP 一等奖的选手”。
- **本地 Web 界面**：基于 Flask 的交互式查询页面，提供直观的搜索体验。
- **洛谷（Luogu）集成**：
    - 支持爬取洛谷奖项认证数据。
    - 提供转换工具，可将洛谷网页复制的奖项文本一键生成查询配置文件。
- **数据统计分析**：内置脚本可生成比赛统计 JSON，支持可视化展示参赛趋势与省份分布。
- **云原生部署**：完整的 Cloudflare Workers + D1 数据库部署方案，前端采用 React + Vite + Shadcn UI 构建。

## 快速开始

### 1. 环境准备

确保已安装 Python 3.10+，并执行以下命令初始化项目：

```bash
# 克隆项目及子仓库
git clone --recursive https://github.com/your-repo/OIerFinder.git
cd OIerFinder

# 安装依赖
pip install -r requirements.txt
```

### 2. 数据处理流水线

本项目的数据依赖于 `oierdb-data` 子项目，需手动触发数据生成流程：

1. **生成原始数据**：
   ```bash
   cd oierdb-data
   python main.py
   cd ..
   ```
2. **构建 SQLite 数据库**：
   ```bash
   python create_db.py
   ```
   该操作会读取 `oierdb-data/dist` 下的 JSON 与文本数据，生成本地数据库 `oier_data.db`。

---

## 使用指南

### 1. 本地 Web 查询
启动 Flask 服务器以开启可视化搜索界面：
```bash
python app.py
```
默认访问地址：`http://127.0.0.1:5000`

### 2. 命令行查询 (CLI)
通过编写 YAML 配置文件进行复杂逻辑筛选：
```bash
python oierfinder.py -c sample_config.yml
```
配置文件支持设置入学年份区间、年级范围以及多组独立的记录过滤条件。

### 3. 洛谷工具集
- **奖项认证转换**：将洛谷个人主页的奖项认证文本存入 `awards.txt`，运行以下命令生成配置：
  ```bash
  python luogu2yml.py -i awards.txt -o config.yml
  ```
- **Top 1000 爬取**：
  ```bash
  python luogu_top1000.py
  ```

---

## 云端部署 (Cloudflare Stack)

项目支持在 Cloudflare 生态中部署高性能的公共查询服务，相关代码位于 `cloudflare/` 目录下：

- **Worker API**: 处理 D1 数据库查询逻辑（`cloudflare/worker/api`）。
- **D1 Database**: 存储结构化选手数据。
- **Frontend**: 基于 React 的现代化单页应用（`cloudflare/worker/src`）。

### 部署流程简述：
1. **自动化一键部署**：
   项目提供 `update_cloudflare.py` 脚本，可一键完成子仓库更新、数据生成、统计计算、D1 同步及 Worker 部署：
   ```bash
   python update_cloudflare.py
   ```
2. **手动分步部署**：
   - **生成统计 JSON**：
     ```bash
     python calculate_stats.py --db oier_data.db --output cloudflare/worker/api/contest_stats.json
     ```
   - **数据同步**：使用 `cloudflare/script/upload_to_d1.py` 将本地数据库上传至 Cloudflare D1。
   - **发布应用**：
     ```bash
     cd cloudflare/worker
     npm run deploy
     ```

### GitHub Actions 自动同步

工作流 [`.github/workflows/sync-oier-data.yml`](.github/workflows/sync-oier-data.yml)
每 6 小时检查一次 `oierdb-data` 上游默认分支，也支持从 Actions 页面手动运行。
上游 SHA 变化或手动选择强制数据更新时，会先运行上游生成器，再对生成的
`result.txt` 和规范化后的 `static.json` 计算 `source_data_hash`。只有数据内容发生变化
或手动强制更新时，才会构建 SQLite、发布 Worker 并替换 D1 核心数据；如果只有上游
提交发生变化，工作流仅推进 `DataRelease.upstream_sha`。本仓库部署相关文件发生变更时，
仍会测试并发布 Worker、应用 migrations 和索引，但不会因此替换核心数据。

在 GitHub 仓库中创建名为 `production` 的 Environment，并配置以下 Secrets：

- `CLOUDFLARE_ACCOUNT_ID`
- `CLOUDFLARE_DATABASE_ID`
- `CLOUDFLARE_D1_API_TOKEN`：仅授予目标账号的 D1 写权限
- `CLOUDFLARE_WORKERS_API_TOKEN`：使用 Cloudflare 的 Edit Workers 模板并限制到目标账号

首次运行会应用 D1 migrations 并创建 `DataRelease` 表。流水线依次执行数据生成、
完整性检查、Worker 测试与构建、Worker 部署、D1 暂存上传与事务切换，最后把对应
上游 SHA 标记为 active。生成的 SQLite、统计 JSON 和发布清单会作为 GitHub Actions
artifact 保留 14 天。当前数据发布使用完整快照而不是逐行增量；这是因为上游的学校、
比赛和记录 ID 依赖生成顺序，并非稳定业务主键。`source_data_hash` 内容检测保证未变化
的数据不会重复构建和上传，而发生变化时仍通过完整暂存和事务切换保证关联关系一致；
升级后的首次运行会为相同 active 上游版本补写该字段，不会因此重写核心数据。

## 数据声明与致谢

- **数据来源**：本项目核心数据源自 [OIerDb-ng/OIerDb-data-generator](https://github.com/OIerDb-ng/OIerDb-data-generator)。
- **隐私提醒**：选手信息仅供个人学习与学术研究使用，请务必遵守相关法律法规，尊重选手的个人隐私。

---
