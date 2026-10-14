#!/bin/sh
# 重启后端服务（供面板 cron 一次性调用，或手动执行）。
# 显式设置 HOME/PATH：cron 环境变量不全时，python3 会找不到
# `pip install --user` 装进 ~/.local 的依赖（如 uvicorn）。
# 停旧进程用 ps+awk 取精确 PID（pgrep -f 在某些 cron 环境下匹配异常，
# 2026-10-12 实测翻车过一次），grep 用 [u]vicorn 写法避免匹配到自身。
# 用法（面板 Cron jobs，加一条临时任务，执行完删除）：
#   sh /home/zgy/serv00-mail/backend/scripts/restart.sh
set -u

export HOME=/home/zgy
export PATH="$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin"
APP_DIR="$HOME/serv00-mail/backend"
LOG="$APP_DIR/restart.log"

# 停旧进程
for p in $(ps aux | grep '[u]vicorn app.main:app' | awk '{print $2}'); do
  if kill "$p" 2>/dev/null; then
    echo "$(date '+%F %T') 停止旧进程 $p" >> "$LOG"
  fi
done
sleep 3

cd "$APP_DIR" || exit 1

# 预检：依赖是否找得到（失败则直接记录，不瞎重启）
if ! python3 -c "import uvicorn" 2>> "$LOG"; then
  echo "$(date '+%F %T') 重启中止：uvicorn 导入失败" >> "$LOG"
  exit 1
fi

nohup python3 -m uvicorn app.main:app --host 127.0.0.1 --port 14840 \
  >> app.log 2>&1 &
sleep 5
if curl -fs --max-time 10 http://127.0.0.1:14840/health > /dev/null 2>&1; then
  echo "$(date '+%F %T') 重启成功，health 正常" >> "$LOG"
else
  echo "$(date '+%F %T') 重启后 health 检查失败，请看 app.log" >> "$LOG"
  exit 1
fi
