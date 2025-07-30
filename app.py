#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
import os
import yaml
import json
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory, session
from werkzeug.utils import secure_filename
import importlib

# 导入模块
format_lgawards = importlib.import_module('format_lgawards')
oierfinder = importlib.import_module('oierfinder')

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload size

# 确保上传目录存在
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# 全局变量存储数据文件路径
DATA_FILE = 'data/serialized_data.pkl'

@app.route('/')
def index():
    """首页"""
    return render_template('index.html')

@app.template_filter('urlencode')
def urlencode_filter(s):
    if s:
        import urllib.parse
        return urllib.parse.quote(s)
    return ''

@app.route('/format_lgawards', methods=['GET', 'POST'])
def format_lgawards_route():
    """洛谷奖项格式化页面"""
    if request.method == 'POST':
        # 处理表单提交
        input_text = request.form.get('input_text', '')
        uploaded_file = request.files.get('file')
        
        # 检查是否有文件上传
        if uploaded_file and uploaded_file.filename != '':
            filename = secure_filename(uploaded_file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            uploaded_file.save(filepath)
            
            # 读取文件内容
            with open(filepath, 'r', encoding='utf-8') as f:
                input_text = f.read()
        
        # 验证输入
        if not input_text:
            flash('请输入奖项文本或上传文件', 'error')
            return redirect(request.url)
        
        try:
            # 调用格式化函数
            awards = format_lgawards.parse_awards(input_text)
            conditions = format_lgawards.format_conditions(awards)
            
            # 转换为YAML字符串
            yaml_content = yaml.dump(conditions, allow_unicode=True, sort_keys=False)
            
            # 存储到会话中，供后续查询使用
            session['yaml_conditions'] = yaml_content
            
            return render_template('format_lgawards.html', 
                                   input_text=input_text,
                                   yaml_content=yaml_content,
                                   awards=awards)
        
        except Exception as e:
            flash(f'格式化失败: {str(e)}', 'error')
            return redirect(request.url)
    
    return render_template('format_lgawards.html')

@app.route('/find_oiers', methods=['GET', 'POST'])
def find_oiers():
    """OIer 查询页面"""
    if request.method == 'POST':
        # 处理表单提交
        yaml_content = request.form.get('yaml_content', '')
        uploaded_file = request.files.get('file')
        ui_config = request.form.get('ui_config')  # UI配置参数
        
        # 检查是否有文件上传
        if uploaded_file and uploaded_file.filename != '':
            filename = secure_filename(uploaded_file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            uploaded_file.save(filepath)
            
            # 读取文件内容
            with open(filepath, 'r', encoding='utf-8') as f:
                yaml_content = f.read()
        
        # 检查是否使用会话中的YAML
        if not yaml_content and 'yaml_conditions' in session:
            yaml_content = session['yaml_conditions']
        
        # 验证输入
        if not yaml_content and not ui_config:
            flash('请提供YAML配置或使用UI界面配置', 'error')
            return redirect(request.url)
        
        try:
            # 如果使用UI配置，解析JSON
            if ui_config:
                try:
                    config = json.loads(ui_config)
                    # 确保config是字典
                    if not isinstance(config, dict):
                        raise Exception(f"UI配置格式错误：期望字典，实际得到 {type(config).__name__}")
                except json.JSONDecodeError as e:
                    flash(f'UI配置解析失败: {str(e)}', 'error')
                    return redirect(request.url)
            else:
                # 解析YAML配置
                config = yaml.safe_load(yaml_content)
                
                # 检查YAML解析结果
                if config is None:
                    raise Exception("YAML配置为空")
                
                # 确保config是字典
                if not isinstance(config, dict):
                    raise Exception(f"YAML配置格式错误：期望字典，实际得到 {type(config).__name__}")
            
            # 调用查询函数
            results = oierfinder.find_oiers_by_yaml_config(config, DATA_FILE)
            
            # 格式化结果
            formatted_results = []
            for oier, matched_records in results:
                # 格式化匹配的记录
                formatted_matched_records = {}
                for idx, record in matched_records.items():
                    formatted_matched_records[idx] = {
                        'contest_name': record.contest.name if record.contest else '未知比赛',
                        'contest_type': record.contest.type if record.contest else '未知',
                        'year': record.contest.year if record.contest else '未知',
                        'award': record.level,
                        'score': record.score,
                        'rank': record.rank,
                        'province': record.province,
                        'school': record.school.name if record.school else '未知学校'
                    }
                
                formatted_results.append({
                    'name': oier.name,
                    'uid': oier.uid,
                    'enroll_middle': oier.enroll_middle,
                    'oierdb_score': getattr(oier, 'oierdb_score', None),
                    'ccf_score': getattr(oier, 'ccf_score', None),
                    'ccf_level': getattr(oier, 'ccf_level', None),
                    'matched_records': formatted_matched_records
                })
            
            return render_template('find_oiers.html', 
                                   yaml_content=yaml_content,
                                   results=formatted_results,
                                   conditions=config.get('conditions', []),
                                   logic=config.get('logic', {}))
        
        except Exception as e:
            flash(f'查询失败: {str(e)}', 'error')
            return redirect(request.url)
    
    return render_template('find_oiers.html')

@app.route('/download_yaml')
def download_yaml():
    """下载YAML配置文件"""
    if 'yaml_conditions' in session:
        yaml_content = session['yaml_conditions']
        
        # 使用send_file直接发送内容，而不是创建临时文件
        from flask import Response
        from io import StringIO
        
        # 创建内存中的文件
        buffer = StringIO()
        buffer.write(yaml_content)
        buffer.seek(0)
        
        return Response(
            buffer.getvalue(),
            mimetype='text/yaml',
            headers={
                'Content-Disposition': 'attachment; filename=conditions.yaml'
            }
        )
    else:
        flash('没有可下载的YAML配置', 'error')
        return redirect(url_for('format_lgawards_route'))

@app.route('/api/format_lgawards', methods=['POST'])
def api_format_lgawards():
    """API: 格式化洛谷奖项"""
    data = request.get_json()
    if not data or 'input_text' not in data:
        return jsonify({'error': '缺少输入文本'}), 400
    
    try:
        awards = format_lgawards.parse_awards(data['input_text'])
        conditions = format_lgawards.format_conditions(awards)
        yaml_content = yaml.dump(conditions, allow_unicode=True, sort_keys=False)
        
        return jsonify({
            'success': True,
            'yaml_content': yaml_content,
            'awards': awards
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/find_oiers', methods=['POST'])
def api_find_oiers():
    """API: 查询OIer"""
    data = request.get_json()
    if not data or 'yaml_content' not in data:
        return jsonify({'error': '缺少YAML配置'}), 400
    
    try:
        config = yaml.safe_load(data['yaml_content'])
        results = oierfinder.find_oiers_by_yaml_config(config, DATA_FILE)
        
        formatted_results = []
        for oier, matched_records in results:
            formatted_matched_records = {}
            for idx, record in matched_records.items():
                formatted_matched_records[idx] = {
                    'contest_name': record.contest.name if record.contest else '未知比赛',
                    'contest_type': record.contest.type if record.contest else '未知',
                    'year': record.contest.year if record.contest else '未知',
                    'award': record.level,
                    'score': record.score,
                    'rank': record.rank,
                    'province': record.province,
                    'school': record.school.name if record.school else '未知学校'
                }
            
            formatted_results.append({
                'name': oier.name,
                'uid': oier.uid,
                'enroll_middle': oier.enroll_middle,
                'oierdb_score': float(oier.oierdb_score) if hasattr(oier, 'oierdb_score') else None,
                'ccf_score': float(oier.ccf_score) if hasattr(oier, 'ccf_score') else None,
                'ccf_level': oier.ccf_level if hasattr(oier, 'ccf_level') else None,
                'matched_records': formatted_matched_records
            })
        
        return jsonify({
            'success': True,
            'results': formatted_results,
            'count': len(formatted_results)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/contests')
def api_contests():
    """API: 获取所有比赛类型"""
    # 这里应该从数据中获取，但为了简化，我们返回硬编码列表
    contests = [
        "NOI", "NOIP提高", "NOIP普及", 
        "CSP提高", "CSP入门", 
        "APIO", "WC", "CTS", "CTSC"
    ]
    return jsonify(contests)

@app.route('/api/provinces')
def api_provinces():
    """API: 获取所有省份"""
    # 这里应该从数据中获取，但为了简化，我们返回硬编码列表
    provinces = [
        "北京", "天津", "上海", "重庆",
        "河北", "山西", "辽宁", "吉林", "黑龙江",
        "江苏", "浙江", "安徽", "福建", "江西", "山东",
        "河南", "湖北", "湖南", "广东", "海南",
        "四川", "贵州", "云南", "陕西", "甘肃",
        "青海", "台湾", "内蒙古", "广西", "西藏", "宁夏",
        "新疆", "香港", "澳门"
    ]
    return jsonify(provinces)

if __name__ == '__main__':
    app.run(debug=True)