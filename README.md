# OIer Finder

数据/代码来自 [OIerDb-ng/OIerDb-data-generator](https://github.com/OIerDb-ng/OIerDb-data-generator)，通过提取 [OIerDb-ng/OIerDb-data-generator](https://github.com/OIerDb-ng/OIerDb-data-generator) 生成的数据放入 sqlite 之后实现 oier 筛选查询。

## 使用

安装依赖

```bash
pip install -r requirements.txt
```

### web page

直接运行 web 查询页面

```bash
python app.py
```

然后访问 `http://127.0.0.1:5000/`

### oierfinder

用于筛选出 OIer。

```bash
python oierfinder.py -c sample_config.yml
```

### luogu2yml


用于将洛谷的的奖项认证格式化为 `conditions.yaml` 格式，直接从洛谷网页上复制奖项认证的文本，例如 `sample_lgawards.txt`：

```bash
python format_lgawards.py -i sample_lgawards.txt -o config.yml
```

### 更新数据

如需更新最新的数据，首先更新 [OIerDb-ng/OIerDb-data-generator](https://github.com/OIerDb-ng/OIerDb-data-generator) 子仓库：

```bash
git submodule update --init --recursive
```

然后生成 [OIerDb-ng/OIerDb-data-generator](https://github.com/OIerDb-ng/OIerDb-data-generator) 的数据：

```bash
cd oierdb-data
python main.py
```

最后通过从 oierdb-data/dist 中提取数据：

```
python create_db.py
```