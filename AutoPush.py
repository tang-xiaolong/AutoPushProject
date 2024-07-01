import os
import subprocess
import time
import json
from flask import Flask, request, jsonify
from threading import Thread, Lock
from datetime import datetime, timedelta

# 加载配置文件
with open('config.json', 'r') as f:
    config = json.load(f)

commit_message = config['commit_message']
heartbeat_interval = config['heartbeat_interval']
heartbeat_threshold = config['heartbeat_threshold']
commit_times = config['commit_times']
data_file = config['data_file']

# 存储注册的目录及其最后心跳时间
registered_dirs = {}
lock = Lock()

app = Flask(__name__)

def load_registered_dirs():
    if os.path.exists(data_file):
        with open(data_file, 'r') as f:
            data = json.load(f)
            for directory, timestamp in data.items():
                registered_dirs[directory] = datetime.fromisoformat(timestamp)
def save_registered_dirs():
    data = {directory: timestamp.isoformat() for directory, timestamp in registered_dirs.items()}
    with open(data_file, 'w') as f:
        json.dump(data, f)
        
@app.route('/PushInmediately', methods=['POST'])
def push_inmediately():
    data = request.get_json()
    print(data)
    directory = data.get('directory')
    if directory and os.path.isdir(directory):
        with lock:
            try:
                commit_changes_to_git(directory, commit_message)
                return jsonify({"message": "Directory push successfully."}), 200
            except Exception as e:
                return jsonify({"message": f"Error occurred in {directory}: {e}"}), 400
    else:
        return jsonify({"error": "Invalid directory."}), 400

@app.route('/register', methods=['POST'])
def register_directory():
    data = request.get_json()
    directory = data.get('directory')
    if directory and os.path.isdir(directory):
        with lock:
            if directory not in registered_dirs:
                registered_dirs[directory] = datetime.now()
                save_registered_dirs()
                return jsonify({"message": "Directory registered successfully."}), 200
            else:
                return jsonify({"message": "Directory already registered."}), 200
    else:
        return jsonify({"error": "Invalid directory."}), 400

@app.route('/heartbeat', methods=['POST'])
def heartbeat():
    data = request.get_json()
    directory = data.get('directory')
    if directory in registered_dirs:
        with lock:
            registered_dirs[directory] = datetime.now()
        return jsonify({"message": "Heartbeat received."}), 200
    else:
        return jsonify({"error": "Directory not registered."}), 400

def commit_changes_to_git(repo_path, message):
    # 添加所有改动的文件
    subprocess.run(['git', 'add', '.'], cwd=repo_path)
    # 提交改动
    subprocess.run(['git', 'commit', '-m', message], cwd=repo_path)
    # 推送到远程仓库
    subprocess.run(['git', 'push'], cwd=repo_path)

def should_commit(now):
    for commit_time in commit_times:
        commit_dt = now.replace(hour=commit_time['hour'], minute=commit_time['minute'], second=0, microsecond=0)
        if now >= commit_dt and (now - commit_dt).total_seconds() < 60:
            return True
    return False

def auto_commit():
    while True:
        now = datetime.now()
        if should_commit(now):
            with lock:
                for directory, last_heartbeat in list(registered_dirs.items()):
                    if (now - last_heartbeat).total_seconds() <= heartbeat_threshold:
                        try:
                            commit_changes_to_git(directory, commit_message)
                            print(f"Changes committed successfully in {directory}.")
                        except Exception as e:
                            print(f"Error occurred in {directory}: {e}")
                    else:
                        print(f"Skipping {directory} due to missed heartbeat.")
        time.sleep(60)  # 每分钟检查一次

if __name__ == '__main__':
    load_registered_dirs()
    # 启动自动提交线程
    commit_thread = Thread(target=auto_commit)
    commit_thread.daemon = True
    commit_thread.start()

    # 启动Flask服务器
    app.run(port=5000)