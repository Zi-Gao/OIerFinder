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
app.config['JSON_AS_ASCII'] = False

# --- 数据库连接管理 (保持不变) ---
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
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
    try: return int(value)
    except (ValueError, TypeError): return None

def to_float_or_none(value):
    if value is None or value == '': return None
    try: return float(value)
    except (ValueError, TypeError): return None

def to_list_or_none(value):
    if value is None or value == '': return None
    return [v.strip() for v in value.split(',') if v.strip()]

# --- 路由 ---
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        query_type = request.form.get('query_type')
        config = None
        error_msg = None

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
                # --- 核心修改部分 ---
                # 使用 getlist 获取所有同名表单字段的值
                record_years_min = request.form.getlist('record_year_min')
                record_years_max = request.form.getlist('record_year_max')
                record_ranks_min = request.form.getlist('record_rank_min')
                record_ranks_max = request.form.getlist('record_rank_max')
                record_scores_min = request.form.getlist('record_score_min')
                record_scores_max = request.form.getlist('record_score_max')
                record_provinces = request.form.getlist('record_province')
                record_contests = request.form.getlist('record_contest_type')
                record_levels = request.form.getlist('record_level_range')

                # 遍历记录条件组
                for i in range(len(record_years_min)):
                    record_cond = {
                        'year_range': [to_int_or_none(record_years_min[i]), to_int_or_none(record_years_max[i])],
                        'rank_range': [to_int_or_none(record_ranks_min[i]), to_int_or_none(record_ranks_max[i])],
                        'score_range': [to_float_or_none(record_scores_min[i]), to_float_or_none(record_scores_max[i])],
                        'province': to_list_or_none(record_provinces[i]),
                        'contest_type': to_list_or_none(record_contests[i]),
                        'level_range': to_list_or_none(record_levels[i]),
                    }
                    
                    # 检查是否有任何一个有效条件，避免添加空的记录组
                    is_valid_condition = any(
                        (isinstance(v, list) and v) or (v is not None and not isinstance(v, list))
                        for v in record_cond.values()
                    )

                    if is_valid_condition:
                       config['records'].append(record_cond)
        
        except (yaml.YAMLError, TypeError) as e:
            error_msg = f"配置解析失败: {e}"
        except Exception as e:
            error_msg = f"发生未知错误: {e}"

        if error_msg:
             return render_template('results.html', error=error_msg)

        if config:
            cursor = get_db().cursor()
            results = finder_engine.find_oiers(config, cursor)
            config_str = json.dumps(config, indent=2, ensure_ascii=False) if config else "{}"
            return render_template('results.html', oiers=results, config=config_str)
        
    return render_template('index.html')


if __name__ == '__main__':
    app.run(debug=True)