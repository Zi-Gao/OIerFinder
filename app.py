from flask import Flask, render_template, request, g, redirect, url_for
import sqlite3
import yaml  # 确保导入 yaml
import json
from urllib.parse import urlencode

# 导入我们重构的模块
from utils import luogu_parser,finder_engine

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
    items = [v.strip() for v in value.split(',') if v.strip()]
    return items if items else None


# --- 路由 (保持不变) ---
@app.route('/', methods=['GET'])
def index():
    last_query = {
        'query_type': request.args.get('query_type', 'ui'),
        'yaml_content': request.args.get('yaml_content', ''),
        'luogu_content': request.args.get('luogu_content', ''),
        'enroll_min': request.args.get('enroll_min', ''),
        'enroll_max': request.args.get('enroll_max', ''),
        'grade_min': request.args.get('grade_min', ''),
        'grade_max': request.args.get('grade_max', ''),
        'records': []
    }
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
            form_data_for_redirect.update({
                'enroll_min': request.form.get('enroll_min', ''),
                'enroll_max': request.form.get('enroll_max', ''),
                'grade_min': request.form.get('grade_min', ''),
                'grade_max': request.form.get('grade_max', ''),
            })
            
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
                record_cond = {
                    'year_range': [to_int_or_none(record_years_min[i]), to_int_or_none(record_years_max[i])],
                    'rank_range': [to_int_or_none(record_ranks_min[i]), to_int_or_none(record_ranks_max[i])],
                    'score_range': [to_float_or_none(record_scores_min[i]), to_float_or_none(record_scores_max[i])],
                    'province': to_list_or_none(record_provinces[i]),
                    'contest_type': to_list_or_none(record_contests[i]),
                    'level_range': to_list_or_none(record_levels[i]),
                }
                
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
            
            form_data_for_redirect['records_json'] = json.dumps(records_for_redirect)

    except (yaml.YAMLError, TypeError) as e:
        error_msg = f"配置解析失败: {e}"
    except Exception as e:
        error_msg = f"发生未知错误: {e}"

    if error_msg:
         return render_template('results.html', error=error_msg, redirect_params=urlencode(form_data_for_redirect))

    if config:
        # 在这里过滤掉值为 None 或空列表的键，以获得更干净的 YAML 输出
        clean_config = {}
        if config.get('enroll_year_range') and any(v is not None for v in config['enroll_year_range']):
            clean_config['enroll_year_range'] = config['enroll_year_range']
        if config.get('grade_range') and any(v is not None for v in config['grade_range']):
            clean_config['grade_range'] = config['grade_range']
        
        clean_records = []
        for record in config.get('records', []):
            clean_record = {k: v for k, v in record.items() if v and (v != [None, None])}
            if clean_record:
                clean_records.append(clean_record)
        if clean_records:
            clean_config['records'] = clean_records
            
        cursor = get_db().cursor()
        results = finder_engine.find_oiers(config, cursor)
        
        # --- 核心修改：使用 yaml.dump 生成 YAML 字符串 ---
        config_str = yaml.dump(clean_config, allow_unicode=True, sort_keys=False, default_flow_style=False) if clean_config else "无有效查询条件"
        
        return render_template('results.html', oiers=results, config=config_str, redirect_params=urlencode(form_data_for_redirect))
    
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)