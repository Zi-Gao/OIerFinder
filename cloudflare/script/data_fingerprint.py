import argparse
import hashlib
import json
from pathlib import Path

if __package__:
    from .upstream_data import GENERATOR_DIR, load_encoding_tables
else:
    from upstream_data import GENERATOR_DIR, load_encoding_tables


FINGERPRINT_VERSION = b"oierfinder-source-data-v2\0"


def _add_payload(digest, name, payload):
    encoded_name = name.encode("utf-8")
    digest.update(len(encoded_name).to_bytes(4, "big"))
    digest.update(encoded_name)
    digest.update(len(payload).to_bytes(8, "big"))
    digest.update(payload)


def calculate_source_data_hash(static_path, result_path, encoding_tables):
    """计算上游生成数据的稳定 SHA-256 指纹。"""
    static_path = Path(static_path)
    result_path = Path(result_path)

    with static_path.open("r", encoding="utf-8") as source:
        static_data = json.load(source)
    canonical_static = json.dumps(
        static_data,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")

    digest = hashlib.sha256(FINGERPRINT_VERSION)
    _add_payload(digest, "static.json", canonical_static)
    _add_payload(digest, "result.txt", result_path.read_bytes())
    _add_payload(
        digest,
        "encoding_tables.json",
        json.dumps(
            encoding_tables,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8"),
    )
    return digest.hexdigest()


def parse_args():
    parser = argparse.ArgumentParser(description="计算 OIerDB 上游数据内容指纹")
    parser.add_argument(
        "--static",
        default=str(GENERATOR_DIR / "dist/static.json"),
        help="生成的 static.json 路径",
    )
    parser.add_argument(
        "--result",
        default=str(GENERATOR_DIR / "dist/result.txt"),
        help="生成的 result.txt 路径",
    )
    parser.add_argument(
        "--generator-dir",
        default=str(GENERATOR_DIR),
        help="生成器目录，用于读取同一上游版本 util.py 中的编号表",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    encodings = load_encoding_tables(args.generator_dir)
    print(calculate_source_data_hash(args.static, args.result, encodings))


if __name__ == "__main__":
    main()
