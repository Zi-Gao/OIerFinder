import yaml
import argparse
import os

# 导入重构后的核心逻辑
from utils import luogu_parser

DEFAULT_INPUT_FILE = 'luogu_awards.txt'
DEFAULT_MAPPING_FILE = 'name_mapping.yml'
DEFAULT_OUTPUT_FILE = 'config.yml'

def main():
    parser = argparse.ArgumentParser(
        description="将洛谷奖项认证格式的文本转换为 oierfinder 的 YAML 配置文件。"
    )
    parser.add_argument(
        '-i', '--input',
        default=DEFAULT_INPUT_FILE,
        help=f"输入的洛谷奖项文本文件 (默认为: {DEFAULT_INPUT_FILE})"
    )
    parser.add_argument(
        '-m', '--mapping',
        default=DEFAULT_MAPPING_FILE,
        help=f"名称映射的 YAML 文件 (默认为: {DEFAULT_MAPPING_FILE})"
    )
    parser.add_argument(
        '-o', '--output',
        default=DEFAULT_OUTPUT_FILE,
        help=f"输出的配置文件名 (默认为: {DEFAULT_OUTPUT_FILE})"
    )
    args = parser.parse_args()

    # 检查输入文件是否存在
    if not os.path.exists(args.input):
        print(f"错误: 输入文件 '{args.input}' 未找到。")
        return
        
    if not os.path.exists(args.mapping):
        print(f"错误: 映射文件 '{args.mapping}' 未找到。")
        return

    try:
        # 读取输入文件内容
        with open(args.input, 'r', encoding='utf-8') as f:
            luogu_text = f.read()

        # 调用核心转换逻辑
        config_dict = luogu_parser.convert_luogu_to_config(luogu_text, args.mapping)

        # 将返回的字典写入输出文件
        with open(args.output, 'w', encoding='utf-8') as f:
            yaml.dump(config_dict, f, allow_unicode=True, sort_keys=False)
        
        print(f"成功将 '{args.input}' 的内容转换为配置文件 '{args.output}'。")

    except Exception as e:
        print(f"处理过程中发生错误: {e}")

if __name__ == '__main__':
    main()