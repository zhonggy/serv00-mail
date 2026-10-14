#!/bin/sh
# serv00 保活脚本：每 5 分钟由 cron 调用，服务挂了就拉起来。
# cron 示例：*/5 * * * * APP_PORT=14840 sh /home/zgy/serv00-mail/backend/scripts/keepalive.sh
set -u

# cron 环境变量不全时 python3 会找不到 --user 安装的依赖（如 uvicorn），这里显式补上
export HOME=/home/zgy
export PATH="$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin"

APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PORT="${APP_PORT:-14840}"
HEALTH_URL="http://127.0.0.1:${PORT}/health"

if curl -fs --max-time 10 "$HEALTH_URL" > /dev/null 2>&1; then
  exit 0
fi

echo "$(date '+%F %T') 后端无响应，尝试重启" >> "$APP_DIR/keepalive.log"
cd "$APP_DIR" || exit 1
nohup python3 -m uvicorn app.main:app --host 127.0.0.1 --port "$PORT" \
  >> app.log 2>&1 &
echo "$(date '+%F %T') 已执行重启" >> "$APP_DIR/keepalive.log"
