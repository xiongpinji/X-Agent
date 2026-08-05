# P1-17: X-Agent 备份工具镜像 —— 供 archive/legacy_k8s_manifests_2026-08/backup-cronjob.yaml (归档参考) 与
# deployment/helm (backup-cronjob 模板) 使用。
# 包含 backup.sh 所需的全部客户端工具: pg_dump/pg_restore、redis-cli、curl、jq。
#
# 构建(项目根目录):
#   docker build -t <registry>/xagent-backup:latest -f deployment/backup/Dockerfile .
FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    redis-tools \
    curl \
    jq \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# 非 root 运行(与主镜像安全基线一致)
RUN useradd -m -u 1000 backup
USER backup

COPY deployment/backup/backup.sh /usr/local/bin/backup.sh

# 容器内直接执行脚本; CronJob 以 /bin/bash /usr/local/bin/backup.sh 调用
ENTRYPOINT ["/bin/bash", "/usr/local/bin/backup.sh"]
