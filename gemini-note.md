# OIerFinder Project Summary

This document provides a summary of the files in the OIerFinder project.

## `app.py`

This is the main Flask application file. It provides a web interface for searching for OIers (Olympiad in Informatics contestants).

- **Framework:** Flask
- **Database:** SQLite (`oier_data.db`)
- **Functionality:**
  - Provides a web form for searching OIers based on criteria like enrollment year, grade, and contest records.
  - Supports three query types: a user-friendly UI, YAML for complex queries, and a format from the Luogu website.
  - Uses `utils/finder_engine.py` for search logic and `utils/luogu_parser.py` to handle Luogu input.
- **Routes:**
  - `/`: Displays the search form.
  - `/search`: Handles form submission, processes the query, and displays the results.

## `calculate_stats.py`

This script generates statistics from the `oier_data.db` database.

- **Purpose:** To calculate statistics about contestants and contests.
- **Input:** The path to the SQLite database (`oier_data.db` by default).
- **Output:** A JSON file (`contest_stats.json` by default) containing the calculated statistics.
- **Statistics Calculated:**
  - The global minimum and maximum year of contests.
  - The number of participants for each combination of contest year, contest type, province, and award level.
- **Usage:** The generated JSON file is intended to be used by a Cloudflare Worker, likely to provide data for the web interface.

## `create_db.py`

This script is responsible for creating and populating the SQLite database.

- **Purpose:** To create the `oier_data.db` SQLite database and populate it with data from source files.
- **Data Sources:**
  - `oierdb-data/dist/static.json`: Contains data about schools and contests.
  - `oierdb-data/dist/result.txt`: Contains data about OIers and their contest records.
- **Database Schema:** Creates four tables:
  - `School`: Stores information about schools.
  - `Contest`: Stores information about contests.
  - `OIer`: Stores information about the contestants.
  - `Record`: Stores the contest records for each contestant, linking to the other tables.
- **Process:**
  1. Deletes the existing `oier_data.db` file if it exists.
  2. Creates the database tables.
  3. Loads school and contest data from `static.json`.
  4. Loads OIer and record data from `result.txt`.
  5. Commits the changes to the database.

## `luogu_crawler.py`

This script crawls data from the Luogu website.

- **Purpose:** To fetch prize information for the top 1000 users from Luogu.
- **Functionality:**
  1. Gets the top 1000 users from Luogu using `utils.luogu_crawl.getTop1000User()`.
  2. Fetches the prize information for these users using `utils.luogu_crawl.getPrizes()`.
  3. Saves the prize information to `luogu_user.txt` in JSON format.

## `luogu_top1000.py`

This is a simple script to get and print the top 1000 users from the Luogu website.

- **Purpose:** To display the top 1000 users from Luogu.
- **Functionality:** It calls the `getTop1000User()` function from `utils.luogu_crawl.py` and prints the returned list of users to the console.

## `luogu2yml.py`

This script converts Luogu award certification text to a YAML configuration file.

- **Purpose:** To convert text in the Luogu awards certification format into a YAML configuration file compatible with `oierfinder`.
- **Inputs:**
  - `--input`: The input text file containing Luogu awards data (defaults to `luogu_awards.txt`).
  - `--mapping`: A YAML file for name mapping (defaults to `name_mapping.yml`).
- **Output:**
  - `--output`: The output YAML configuration file (defaults to `config.yml`).
- **Functionality:**
  1. Reads the Luogu awards text from the input file.
  2. Uses the `luogu_parser.convert_luogu_to_config()` function to perform the conversion.
  3. Writes the resulting dictionary to the output YAML file.

## `main.py`

This is a simple placeholder or entry point for the project.

- **Purpose:** To serve as a minimal entry point.
- **Functionality:** It defines a `main` function that prints "Hello from oierfinder!".

## `oierfinder.py`

This is the main command-line interface for finding OIers.

- **Purpose:** To provide a command-line interface for searching for OIers based on a YAML configuration file.
- **Input:**
  - `--config`: The path to the YAML configuration file (defaults to `config.yml`).
- **Database:** Connects to the `oier_data.db` SQLite database.
- **Functionality:**
  1. Loads the search criteria from the specified YAML configuration file.
  2. Connects to the SQLite database.
  3. Uses the `finder_engine.find_oiers()` function to perform the search based on the loaded configuration.
  4. Prints the search results to the console in a formatted table.

## `utils/finder_engine.py`

This file contains the core logic for finding OIers in the database.

- **Purpose:** To provide the core functionality for querying the `oier_data.db` database to find OIers based on a set of criteria.
- **Key Functions:**
  - `build_where_clause_and_values(params)`: A helper function that dynamically builds the `WHERE` clause of an SQL query based on filter parameters.
  - `find_oiers(config, cursor)`: The main function that orchestrates the search.
- **Search Logic:**
  1. Filters the `OIer` table based on enrollment year and grade ranges to get an initial set of candidates.
  2. Iterates through the `records` constraints in the configuration, querying the `Record` table for each.
  3. Narrows down the candidates by finding the intersection of results from each record constraint.
  4. Fetches the full details of the OIers who satisfy all conditions and returns them,.
  5. ordered by their `oierdb_score`.

## `utils/luogu_crawl.py`

This file contains functions for crawling data from the Luogu website.

- **Purpose:** To provide functions for fetching data from the Luogu website, specifically user prize lists and user rankings.
- **Key Functions:**
  - `getPrizeList(uid)`: Fetches and parses the prize list for a specific user.
  - `getPrizes(uids)`: Gets the prize lists for a list of user IDs.
  - `getTop1000User()`: Fetches the top 1000 users from Luogu by scraping the first 20 pages of the rankings.
- **Dependencies:** `requests`, `tqdm`.
- **Headers:** Uses a custom `User-Agent` (`OlerFinder-Bot/1.0`).

## `utils/luogu_parser.py`

This file is responsible for parsing Luogu award text and converting it into the application's configuration format.

- **Purpose:** To parse text in the Luogu awards certification style and convert it into a YAML configuration dictionary.
- **Key Functions:**
  - `load_mapping(mapping_file)`: Loads a YAML mapping file for translating Luogu's contest names and award levels.
  - `convert_luogu_to_config(luogu_text, mapping_file)`: The main function that performs the conversion.
- **Parsing Logic:**
  1. Reads `contest_mapping` and `level_mapping` from the mapping file.
  2. Processes the input text in pairs of lines (contest/year and award level).
  3. Uses regex to extract year and contest name.
  4. Looks up the contest and award level in the mappings to standardize them.
  5. Creates a `record` dictionary for each valid entry.
  6. Returns a final configuration dictionary containing a list of these records.

## `cloudflare/worker/api/get_luogu_prizes.js`

This is a Cloudflare Worker function that serves as an API endpoint to fetch Luogu prize information.

- **Purpose:** To provide an API for retrieving Luogu prizes for a given user.
- **Framework:** Cloudflare Workers.
- **Input:**
  - `uid` (query parameter): The Luogu user ID.
  - `sync` (query parameter, optional): If true, forces a refetch of the data.
  - `noi_only` (query parameter, optional): If true, filters for "NOI series" contests.
- **Functionality:**
  1. Calls `getPrizes` (from `./luogu_to_query.js`) to get the prize list.
  2. Optionally filters the list for NOI series contests.
  3. Sorts the prize list by year and contest name.
  4. Returns the prize list as a JSON response.
- **Error Handling:** Includes error handling and provides detailed errors for admins.

## `cloudflare/worker/api/index.js`

This file is the main entry point for the Cloudflare Worker's API.

- **Purpose:** To define the API routes for the Cloudflare Worker and serve static files.
- **Framework:** Hono.
- **API Routes:**
  - `POST /query-oier`: Handled by `queryOierHandler` to perform the main search.
  - `GET /luogu/to_query`: Handled by `luoguToQueryHandler` to convert Luogu data to a query.
  - `GET /luogu/prizes`: Handled by `getLuoguPrizesHandler` to fetch Luogu prizes.
- **Static Files:** Serves static files for any routes that don't match the API endpoints.

## `cloudflare/worker/api/luogu_to_query.js`

This file contains the core logic for handling Luogu data in the Cloudflare Worker.

- **Purpose:**
  1. To fetch, process, and store Luogu prize information in a Cloudflare D1 database.
  2. To provide an API endpoint (`/luogu/to_query`) that converts a user's Luogu prizes into a query payload.
- **Data Fetching and Processing:**
  - `getPrizes`: The main function for getting prizes. It can fetch from Luogu, the D1 database, or both, and then merge the results.
  - `fetchAndProcessLuoguPrizes`: Scrapes the Luogu user page to get the prize list.
  - `updateD1PrizesIncremental`: Performs an incremental update of the D1 database.
- **API Endpoint (`luoguToQueryHandler`):**
  - Takes a `uid` and an optional `sync` parameter.
  - Calls `getPrizes` to get the user's prize list.
  - Calls `generateQueryPayload` to convert the prize list into a query payload.
  - Returns the query payload as a JSON response.
- **Mappings:** Defines mappings to standardize Luogu contest and prize names.

## `cloudflare/worker/api/query_oier.js`

This file is the main query engine for the Cloudflare Worker, handling the `/query-oier` endpoint.

- **Purpose:** To provide a secure, efficient, and robust API endpoint for querying OIer data.
- **Security and Validation:**
  - **Input Validation**: Strictly validates and sanitizes the incoming JSON payload, checking for allowed keys and correct data types.
  - **Query Strength**: Calculates a "strength" score for each query to prevent overly broad and expensive queries.
  - **Filter Limits**: Limits the number of record filters allowed in a single query.
- **Query Optimization and Execution:**
  - **Filter Pre-processing**: Normalizes filters and removes redundant ones.
  - **Selectivity Estimation**: Uses pre-calculated statistics from `contest_stats.json` to reorder filters, executing the most selective ones first.
  - **Dynamic Query Strategy**: Switches between SQL-based filtering and a faster in-memory "verification mode" for small result sets.
  - **Chunking**: Breaks down large queries into smaller chunks to avoid database limitations.
- **API Handler (`queryOierHandler`):**
  - The main Hono handler for the `POST /query-oier` endpoint.
  - Orchestrates the entire process: validation, pre-processing, and query execution.
  - For admins, it includes detailed usage statistics in the response.

## `cloudflare/worker/src/App.jsx`

This is the root React component of the frontend application.

- **Purpose:** To manage the overall application state and render the UI components.
- **State Management:**
  - Manages the active tab, query filters, search results, and global settings.
  - Persists global settings (`adminSecret`, `limit`) to `localStorage`.
- **Key Components:**
  - `QueryBuilder`: A UI for building queries with form fields.
  - `JsonQuery`: A text area for entering raw JSON queries.
  - `LuoguQuery`: A component for querying by Luogu UID.
  - `ResultsDisplay`: A component for displaying the search results.
- **Core Functionality:**
  - `handleSearch`: The central function for executing a search. It processes and cleans filter data, sends the API request, and updates the state.
  - `handleLuoguQueryImport`: Allows importing a query from the Luogu tab to the UI Builder.
  - **Tabbed Interface**: Allows switching between different query methods.
- **Layout:** Uses Tailwind CSS for a two-column layout.

## `cloudflare/worker/src/components/JsonQuery.jsx`

This component provides a raw JSON interface for making queries.

- **Purpose:** To allow users to write or paste a raw JSON query payload.
- **State Management:**
  - Uses a local state `jsonString` for the textarea content.
  - Receives `recordFilters`, `oierFilters`, and `limit` as props from the parent `App` component.
- **Synchronization:**
  - `useEffect`: Updates the textarea content when the props from `App` change.
  - `handleTextChange`: Tries to parse the JSON in real-time and updates the shared state in `App` if the JSON is valid.
- **Functionality:**
  - `handleSubmit`: Parses the final JSON string and calls the `onSearch` callback from `App` to execute the search.
- **UI:** A `textarea` for JSON input and a "Search" button.

## `cloudflare/worker/src/components/LuoguQuery.jsx`

This component handles the "Luogu UID" tab in the UI.

- **Purpose:** To fetch a user's awards from Luogu and convert them into a query for the "UI Builder" tab.
- **State Management:**
  - Manages the Luogu UID input, the fetched prize list, loading states, and error messages.
- **Functionality:**
  - `handleFetchPrizes`: Calls the `getLuoguPrizes` API function to fetch the user's awards.
  - `handleImport`: Calls the `getQueryFromJson` API function to convert the awards into a query payload. It then passes this payload up to the `App` component to be imported into the UI Builder.
- **UI:**
  - An input field for the Luogu UID.
  - A button to fetch awards.
  - A table to display the fetched awards.
  - A button to import the query.

## `cloudflare/worker/src/components/QueryBuilder.jsx`

This is the main component for the "UI Builder" tab.

- **Purpose:** To provide a user-friendly interface for building complex queries using form inputs.
- **Component Composition:**
  - Uses a child `RecordFilter` component for each record condition.
  - Defines reusable, styled form components (`Input`, `Select`, `Label`).
- **State Management:**
  - It's a controlled component; the filter state is managed by the parent `App` component.
  - It receives the filter state and callback functions as props.
- **Functionality:**
  - Allows adding, removing, and updating multiple record filters.
  - Provides a form for OIer-specific filters, with an expandable "Advanced Options" section.
  - Triggers the search by calling the `onSearch` callback from the `App` component.
- **UI:**
  - A dynamic list of record filter forms.
  - A form for OIer conditions.
  - A "Search" button.

## `cloudflare/worker/src/components/RecordFilter.jsx`

This component provides the form for a single record filter.

- **Purpose:** To encapsulate the form logic and UI for a single record filter condition.
- **State Management:**
  - A controlled component that receives its state (`filter`) and `onChange` callback as props.
  - Manages the local `showAdvanced` state to toggle advanced options for that specific filter.
- **Functionality:**
  - `handleChange`: A generic handler that updates the parent's state via the `onChange` callback.
  - `toggleAdvanced`: Shows or hides advanced filter options and clears their values when hidden.
- **UI:**
  - A "remove" button.
  - Basic inputs for `Contest Type`, `Level`, and `Year`.
  - An expandable section with advanced inputs like `Year Range`, `Provinces`, `Score Range`, etc.
- **Reusability:** Designed to be dynamically rendered in a list by its parent, `QueryBuilder`.

## `cloudflare/worker/src/components/ResultsDisplay.jsx`

This component is responsible for displaying the search results.

- **Purpose:** To render the search results, loading state, or error messages.
- **Props:** `results`, `error`, `loading`.
- **Conditional Rendering:**
  - Displays a "Loading..." message if `loading` is true.
  - Displays an error box if `error` is present.
  - Renders nothing if `results` is null.
- **Functionality:**
  - `formatGender`: A helper to convert numeric gender to a string.
  - **Usage Statistics:** Displays a collapsible section with raw usage stats if they exist in the `results` object (for admins).
  - **Results Table:** Displays the found OIers in a table with links to their profiles on an external site.
- **UI:** A well-formatted table and collapsible sections for a clean presentation.

## Other Files

### `README.md`

- **Purpose**: The main documentation for the project.
- **Content**: Explains the project's purpose, how to install dependencies, run the Flask web app and command-line tools, and how to update the data from the submodule.

### `oierdb-data/README.md`

- **Purpose**: The README for the `oierdb-data` submodule.
- **Content**: Explains how to install dependencies and generate the raw data files used by the main application.

### `cloudflare/worker/wrangler.toml`

- **Purpose**: The configuration file for the Cloudflare Worker.
- **Content**: Defines the worker's name, entry point, asset configuration, and the binding for the Cloudflare D1 database.

### `pyproject.toml`

- **Purpose**: The standard Python project configuration file.
- **Content**: Defines project metadata and lists the project's dependencies for modern Python packaging tools.

### `requirements.txt`

- **Purpose**: A traditional Python dependency file.
- **Content**: Lists the specific versions of Python packages required, ensuring a reproducible environment.

然，在阅读了整个项目之后，我非常乐意分享一些我的看法和建议。

  总的来说，这是一个非常有趣且有价值的项目。它成功地将多个数据源整合，并提供了多种查询方式（CLI, Web, API），特别是 Cloudflare Worker 和 React
  的现代前端架构，实现得相当出色和高效。

  以下是我从几个方面提出的一些具体建议，希望能对你有所帮助：

  1. 架构与代码结构

   * 建议：统一技术栈，聚焦 Cloudflare Worker + React
       * 现状：项目目前存在两套后端实现：一套是基于 Python Flask 的 app.py，另一套是基于 Cloudflare Worker 的 api/index.js。它们的功能有很大的重叠。
       * 分析：Cloudflare Worker 的后端 (query_oier.js)
         在功能、安全性和性能上明显更先进（例如，查询强度计算、防滥用、动态查询策略等）。同时维护两套后端会增加未来迭代的复杂度和工作量。
       * 改进：可以考虑将项目的主要方向确定为 Cloudflare Worker + React 的组合。将 Python Flask 的版本作为本地运行的备选或历史参考，而新功能主要在 Worker 和 React
         应用上开发。这样可以集中精力，让核心应用变得更强大。

   * 建议：数据更新流程自动化
       * 现状：根据 README.md，更新数据的流程需要多个手动步骤（git submodule update -> cd oierdb-data -> python main.py -> cd .. -> python create_db.py）。
       * 分析：这个流程有些繁琐，容易出错或遗漏步骤。
       * 改进：可以创建一个简单的自动化脚本（例如 update_data.sh 或 Makefile），将所有数据更新命令封装起来，实现一键更新本地的
         oier_data.db。更进一步，还可以用这个脚本来触发 Cloudflare D1 数据库的更新。

  2. 功能与体验增强

   * 建议：增加数据可视化
       * 现状：项目已经有了 calculate_stats.py 来生成 contest_stats.json，但这部分数据似乎只用于后端的查询优化。
       * 分析：这些统计数据本身就很有价值。如果能在前端以图表的形式展示出来，将大大提升项目的吸引力。
       * 改进：在前端 React 应用中增加一个“数据统计”或“看板”页面，利用 contest_stats.json 的数据，使用如 Chart.js, ECharts 等库来展示：
           * 历年各省获奖人数趋势图。
           * 不同竞赛的获奖等级分布饼图。
           * 全国获奖情况的地理热力图。

   * 建议：增加选手个人主页
       * 现状：目前查询结果是一个选手列表。
       * 分析：用户在找到某个选手后，可能想了解他的所有竞赛记录。
       * 改进：在结果表格中，点击选手姓名不仅可以跳转到外部链接，也可以跳转到应用内的一个选手详情页。该页面可以展示这位选手的所有记录、成绩变化曲线等信息。

   * 建议：API 层面增加缓存
       * 现状：Cloudflare Worker 的查询直接打到 D1 数据库。
       * 分析：对于一些热门或重复的查询，每次都直接查数据库可能会造成不必要的资源消耗。
       * 改进：可以利用 Cloudflare 的 KV 存储或 Cache API，对 /query-oier 的查询结果进行缓存。例如，对于相同的查询
         payload，在几分钟或几小时内直接返回缓存的结果，可以极大地提升响应速度并降低 D1 的读取成本。

  3. 前端用户体验 (UX)

   * 建议：结果表格增强：排序与前端过滤
       * 现状：ResultsDisplay.jsx 以一个静态表格展示结果。
       * 改进：可以为表格的表头增加点击排序功能（例如按入学年份、OIerDB分数排序）。在表格上方增加一个简单的搜索框，用于在当前返回的结果中快速筛选姓名或学校。

   * 建议：查询表单增加自动补全
       * 现状：UI Builder 中的省份、竞赛类型等都需要手动输入。
       * 改进：可以根据 contest_stats.json 中的数据，为“省份”、“竞赛类型”等输入框提供自动补全建议，提升输入效率和准确性。

  4. 部署与维护

   * 建议：使用 CI/CD (如 GitHub Actions) 自动更新数据
       * 现状：数据更新是手动过程。
       * 分析：可以完全自动化这个流程，确保数据始终保持最新。
       * 改进：设置一个 GitHub Actions workflow，定时（例如每天）执行以下操作：
           1. 拉取 oierdb-data 子模块的最新代码。
           2. 运行数据生成脚本 (main.py 和 create_db.py)。
           3. 将新生成的 oier_data.db 文件（或其内容）通过 Cloudflare 的 wrangler CLI 工具自动更新到 D1 数据库。

  希望这些建议对你有所启发！这是一个非常有潜力的项目，继续完善下去会非常有价值。

                                                                                 