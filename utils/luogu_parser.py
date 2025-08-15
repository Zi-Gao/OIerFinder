# luogu_parser.py
import yaml
import re

def load_mapping(mapping_file):
    with open(mapping_file, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def convert_luogu_to_config(luogu_text, mapping_file):
    mapping = load_mapping(mapping_file)
    contest_map = mapping.get('contest_mapping', {})
    level_map = mapping.get('level_mapping', {})
    
    lines = [line.strip() for line in luogu_text.strip().splitlines() if line.strip()]
    pattern = re.compile(r"\[(\d{4})\]\s*(.*)")
    
    config_records = []
    for i in range(0, len(lines) - 1, 2):
        match = pattern.match(lines[i])
        if not match: continue
        
        year, luogu_contest = int(match.group(1)), match.group(2).strip()
        luogu_level = lines[i+1].strip()
        
        standard_contest_type, standard_level = None, level_map.get(luogu_level)
        if not standard_level: continue

        for key, value in contest_map.items():
            if key in luogu_contest:
                standard_contest_type = value
                break
        if not standard_contest_type: continue

        config_records.append({
            'year_range': [year, year],
            'contest_type': [standard_contest_type],
            'level_range': [standard_level]
        })
        
    return {
        'enroll_year_range': [None, None],
        'grade_range': [None, None],
        'records': config_records
    }