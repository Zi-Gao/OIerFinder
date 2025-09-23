import requests
import yaml
import json

def load_config():
    """读取配置文件"""
    with open("config.yml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def query_d1(cfg, sql):
    """执行 SQL 查询并返回原始结果"""
    url = f"https://api.cloudflare.com/client/v4/accounts/{cfg['cloudflare']['account_id']}/d1/database/{cfg['cloudflare']['database_id']}/raw"
    headers = {
        "Authorization": f"Bearer {cfg['cloudflare']['api_token']}",
        "Content-Type": "application/json"
    }
    payload = {
        "sql": sql
    }

    resp = requests.post(url, headers=headers, data=json.dumps(payload))
    if resp.status_code != 200:
        print(f"❌ 请求失败: HTTP {resp.status_code}")
        print(resp.text)
        return None
    
    data = resp.json()
    return data

def main():
    cfg = load_config()
    # 测试 SQL：从 OIer 表取前 5 条
    sql = "SELECT * FROM OIer;"
    print(f"▶ 执行查询: {sql}")
    result = query_d1(cfg, sql)

    if result:
        print("✅ 查询成功，完整返回如下：")
        print(json.dumps(result["result"][0]["meta"], indent=2, ensure_ascii=False))
    else:
        print("⚠ 查询失败")

if __name__ == "__main__":
    main()