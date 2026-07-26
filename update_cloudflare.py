import subprocess
import sys
import os
import tempfile

# --- 配置 ---
# 获取脚本所在的目录，以确保路径正确
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 定义各个子目录的路径
OIERDB_DATA_DIR = os.path.join(BASE_DIR, 'oierdb-data')
CLOUDFLARE_SCRIPT_DIR = os.path.join(BASE_DIR, 'cloudflare', 'script')
CLOUDFLARE_WORKER_DIR = os.path.join(BASE_DIR, 'cloudflare', 'worker')
STATS_OUTPUT_PATH = os.path.join(CLOUDFLARE_WORKER_DIR, 'api', 'contest_stats.json')

# --- 辅助函数 ---
def print_step(message):
    """打印带有高亮效果的步骤标题"""
    print("\n" + "="*60)
    print(f"  {message}")
    print("="*60)

def run_command(command, cwd=None, env=None):
    """执行一个 shell 命令，实时打印输出，并在失败时退出"""
    print(f"""\n▶️  Executing: {' '.join(command)}""")
    print(f"   (in directory: {cwd or BASE_DIR})")
    
    process = subprocess.Popen(
        command,
        cwd=cwd or BASE_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding='utf-8',
        bufsize=1,
        env=env,
    )
    
    for line in iter(process.stdout.readline, ''):
        print(line, end='')
    
    process.wait()
    
    if process.returncode != 0:
        print(f"\n❌ ERROR: Command failed with exit code {process.returncode}.")
        sys.exit(1)
    print(f"✅ SUCCESS: Command finished successfully.")

# --- 主流程 ---
def main():
    """主函数，按顺序执行所有更新和部署步骤"""
    
    print_step("Step 1: Updating oierdb-data submodule")
    run_command(["git", "submodule", "update", "--remote", "--merge"])
    
    print_step("Step 2: Installing dependencies")
    # 需要这些包来处理数据、解析配置以及与 Cloudflare API 交互
    run_command(["uv", "pip", "install", "pypinyin", "requests", "tqdm", "pyyaml"])

    print_step("Step 3: Generating latest data files from submodule")
    run_command([sys.executable, "main.py"], cwd=OIERDB_DATA_DIR)
    
    with tempfile.TemporaryDirectory(prefix="oierfinder-") as temp_dir:
        local_db_path = os.path.join(temp_dir, "oier_data.db")
        deployment_env = os.environ.copy()
        deployment_env["OIER_DATABASE_PATH"] = local_db_path

        print_step("Step 4: Building temporary SQLite database")
        run_command(
            [sys.executable, "create_db.py"],
            env=deployment_env,
        )

        print_step("Step 5: Calculating contest stats and updating JSON")
        run_command(
            [
                sys.executable,
                "calculate_stats.py",
                "--db",
                local_db_path,
                "--output",
                STATS_OUTPUT_PATH,
            ],
            env=deployment_env,
        )

        print_step("Step 6: Uploading all new data to Cloudflare D1")
        run_command(
            [sys.executable, "upload_to_d1.py"],
            cwd=CLOUDFLARE_SCRIPT_DIR,
            env=deployment_env,
        )

        print_step("Step 7: Optimizing Database Indexes")
        # 建立索引是降低 D1 扫描行数、减少成本的关键
        run_command(
            [sys.executable, "create_indexes.py"],
            cwd=CLOUDFLARE_SCRIPT_DIR,
            env=deployment_env,
        )

        print_step("Step 8: Deploying the Cloudflare Worker")
        # 确保 npx 在你的系统 PATH 中
        run_command(
            ["npm", "run", "deploy"],
            cwd=CLOUDFLARE_WORKER_DIR,
            env=deployment_env,
        )

    print("\n" + "*"*60)
    print("🎉 All steps completed successfully! Your Cloudflare application is updated and deployed.")
    print("*"*60)


if __name__ == "__main__":
    # 提示用户需要激活虚拟环境
    if "VIRTUAL_ENV" not in os.environ:
        print("⚠️  WARNING: It looks like you are not in a virtual environment.")
        print("   Please activate your venv before running this script to ensure all dependencies are correct.")
        print("   (e.g., 'source .venv/bin/activate')")
        if input("   Continue anyway? (y/n): ").lower() != 'y':
            sys.exit(0)
            
    main()
