# OIer Finder

数据/代码来自 [OIerDb-ng/OIerDb-data-generator](https://github.com/OIerDb-ng/OIerDb-data-generator)

## 使用

安装依赖

```bash
pip install -r requirements.txt
```

### oierfinder

用于筛选出 OIer。

```bash
python oierfinder.py --config sample_conditions.yaml --output results.csv
```

### format_lgawards


用于将洛谷的的奖项认证格式化为 `conditions.yaml` 格式：

```bash
python format_lgawards.py -i sample_lgawards.txt -o conditions.yaml
```

### generate_data

用于生成/更新 OIer 的数据。

首先更新 [OIerDb-ng/OIerDb-data-generator](https://github.com/OIerDb-ng/OIerDb-data-generator) 子仓库

```bash
git submodule update --init --recursive
```

然后

```bash
python generate_data.py
```