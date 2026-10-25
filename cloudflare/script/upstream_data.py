import ast
from pathlib import Path


GENERATOR_DIR = Path(__file__).resolve().parents[2] / 'oierdb-data' / 'generator'


def load_encoding_tables(generator_dir=GENERATOR_DIR):
    """读取同一上游版本的编号表，不执行 util.py 的数据生成逻辑。"""
    required = {'provinces', 'award_levels', 'contest_types'}
    source = (Path(generator_dir) / 'util.py').read_text(encoding='utf-8')
    tables = {}
    for node in ast.parse(source).body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id in required:
                values = ast.literal_eval(node.value)
                if not isinstance(values, list) or not values or not all(
                    isinstance(value, str) and value for value in values
                ):
                    raise ValueError(f'Invalid upstream encoding table: {target.id}')
                tables[target.id] = values
    missing = required - tables.keys()
    if missing:
        raise ValueError(f'Missing upstream encoding tables: {sorted(missing)}')
    return tables
