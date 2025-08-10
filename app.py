# app.py
from flask import Flask, render_template, request, g
import sqlite3
import yaml
import json

# 导入我们重构的模块
import finder_engine
import luogu_parser

DATABASE = 'oier_data.db'
MAPPING_FILE = 'name_mapping.yml'

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False # 让json.dumps正确处理中文

# --- 数据库连接管理 ---
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        # 让返回结果像字典一样可以通过列名访问
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

# --- 辅助函数，处理表单数据转换 ---
def to_int_or_none(value):
    if value is None or value == '': return None
    return int(value)

def to_list_or_none(value):
    if value is None or value == '': return None
    return [v.strip() for v in value.split(',')]

# --- 路由 ---
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        query_type = request.form.get('query_type')
        config = None

        try:
            if query_type == 'yaml':
                yaml_content = request.form.get('yaml_content')
                config = yaml.safe_load(yaml_content)
            
            elif query_type == 'luogu':
                luogu_content = request.form.get('luogu_content')
                config = luogu_parser.convert_luogu_to_config(luogu_content, MAPPING_FILE)

            elif query_type == 'ui':
                config = {
                    'enroll_year_range': [
                        to_int_or_none(request.form.get('enroll_min')),
                        to_int_or_none(request.form.get('enroll_max'))
                    ],
                    'grade_range': [
                        to_int_or_none(request.form.get('grade_min')),
                        to_int_or_none(request.form.get('grade_max'))
                    ],
                    'records': []
                }
                # 处理动态添加的 record 条件
                record_years_min = request.form.getlist('record_year_min')
                record_years_max = request.form.getlist('record_year_max')
                record_contests = request.form.getlist('record_contest_type')
                record_levels = request.form.getlist('record_level_range')

                for i in range(len(record_years_min)):
                    record_cond = {
                        'year_range': [to_int_or_none(record_years_min[i]), to_int_or_none(record_years_max[i])],
                        'contest_type': to_list_or_none(record_contests[i]),
                        'level_range': to_list_or_none(record_levels[i]),
                    }
                    # 只有在至少有一个条件非空时才添加
                    if any(val for key, val in record_cond.items() if val != [None, None]):
                       config['records'].append(record_cond)
        
        except (yaml.YAMLError, TypeError) as e:
            return render_template('results.html', error=f"配置解析失败: {e}")
        except Exception as e:
            return render_template('results.html', error=f"发生未知错误: {e}")

        if config:
            cursor = get_db().cursor()
            results = finder_engine.find_oiers(config, cursor)
            return render_template('results.html', oiers=results, config=json.dumps(config, indent=2, ensure_ascii=False))
        
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)