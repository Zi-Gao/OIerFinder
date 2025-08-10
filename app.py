from flask import Flask, render_template, request, g, redirect, url_for
import sqlite3
import yaml
import json
from urllib.parse import urlencode

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

# --- 辅助函数，处理表单数据转换 (保持不变) ---
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
    # 保证返回的是列表
    items = [v.strip() for v in value.split(',') if v.strip()]
    return items if items else None


# --- 路由 ---
@app.route('/', methods=['GET'])
def index():
    # 在 GET 请求中接收上次的查询数据
    # 'last_query' 将是一个字典，包含了所有需要恢复的表单数据
    last_query = {
        'query_type': request.args.get('query_type', 'ui'), # 默认激活UI标签
        'yaml_content': request.args.get('yaml_content', ''),
        'luogu_content': request.args.get('luogu_content', ''),
        'enroll_min': request.args.get('enroll_min', ''),
        'enroll_max': request.args.get('enroll_max', ''),
        'grade_min': request.args.get('grade_min', ''),
        'grade_max': request.args.get('grade_max', ''),
        'records': []
    }
    
    # 从 GET 参数中重建 records 列表
    # Flask 的 request.args 只能获取第一个同名参数，所以我们需要一个技巧
    # 我们将在 POST 到 /search 时将 record 数据编码为 JSON 字符串
    records_json = request.args.get('records_json', '[]')
    try:
        last_query['records'] = json.loads(records_json)
    except json.JSONDecodeError:
        last_query['records'] = []

    return render_template('index.html', last_query=last_query)

@app.route('/search', methods=['POST'])
def search():
    query_type = request.form.get('query_type')
    config = None
    error_msg = None
    
    # 保存原始输入，以便返回时恢复
    form_data_for_redirect = {'query_type': query_type}

    try:
        if query_type == 'yaml':
            yaml_content = request.form.get('yaml_content', '')
            form_data_for_redirect['yaml_content'] = yaml_content
            config = yaml.safe_load(yaml_content) if yaml_content else {}
        
        elif query_type == 'luogu':
            luogu_content = request.form.get('luogu_content', '')
            form_data_for_redirect['luogu_content'] = luogu_content
            config = luogu_parser.convert_luogu_to_config(luogu_content, MAPPING_FILE) if luogu_content else {}

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
            # 同时保存原始表单数据用于重定向
            form_data_for_redirect.update({
                'enroll_min': request.form.get('enroll_min', ''),
                'enroll_max': request.form.get('enroll_max', ''),
                'grade_min': request.form.get('grade_min', ''),
                'grade_max': request.form.get('grade_max', ''),
            })
            
            # --- 核心修改部分 ---
            record_years_min = request.form.getlist('record_year_min')
            record_years_max = request.form.getlist('record_year_max')
            record_ranks_min = request.form.getlist('record_rank_min')
            record_ranks_max = request.form.getlist('record_rank_max')
            record_scores_min = request.form.getlist('record_score_min')
            record_scores_max = request.form.getlist('record_score_max')
            record_provinces = request.form.getlist('record_province')
            record_contests = request.form.getlist('record_contest_type')
            record_levels = request.form.getlist('record_level_range')

            records_for_redirect = []
            for i in range(len(record_years_min)):
                # 为 config 构建数据
                record_cond = {
                    'year_range': [to_int_or_none(record_years_min[i]), to_int_or_none(record_years_max[i])],
                    'rank_range': [to_int_or_none(record_ranks_min[i]), to_int_or_none(record_ranks_max[i])],
                    'score_range': [to_float_or_none(record_scores_min[i]), to_float_or_none(record_scores_max[i])],
                    'province': to_list_or_none(record_provinces[i]),
                    'contest_type': to_list_or_none(record_contests[i]),
                    'level_range': to_list_or_none(record_levels[i]),
                }
                
                # 为重定向构建数据 (保持原始字符串)
                record_for_redirect = {
                    'year_min': record_years_min[i], 'year_max': record_years_max[i],
                    'rank_min': record_ranks_min[i], 'rank_max': record_ranks_max[i],
                    'score_min': record_scores_min[i], 'score_max': record_scores_max[i],
                    'province': record_provinces[i], 'contest_type': record_contests[i],
                    'level_range': record_levels[i],
                }
                records_for_redirect.append(record_for_redirect)

                is_valid_condition = any(
                    (isinstance(v, list) and v) or (v is not None and not isinstance(v, list))
                    for v in record_cond.values()
                )
                if is_valid_condition:
                   config['records'].append(record_cond)
            
            # 将复杂的 record 列表编码为 JSON 字符串以便通过 GET 传递
            form_data_for_redirect['records_json'] = json.dumps(records_for_redirect)

    except (yaml.YAMLError, TypeError) as e:
        error_msg = f"配置解析失败: {e}"
    except Exception as e:
        error_msg = f"发生未知错误: {e}"

    if error_msg:
         return render_template('results.html', error=error_msg, redirect_params=urlencode(form_data_for_redirect))

    if config:
        cursor = get_db().cursor()
        results = finder_engine.find_oiers(config, cursor)
        config_str = json.dumps(config, indent=2, ensure_ascii=False) if config else "{}"
        return render_template('results.html', oiers=results, config=config_str, redirect_params=urlencode(form_data_for_redirect))
    
    # 如果没有 config，重定向回主页
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)