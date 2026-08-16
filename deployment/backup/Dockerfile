# P1-17: X-Agent 备份工具镜像 —— 供 archive/legacy_k8s_manifests_2026-08/backup-cronjob.yaml (归档参考) 与
# deployment/helm (backup-cronjob 模板) 使用。
# 包含 backup.sh 所需的全部客户端工具: pg_dump/pg_restore、redis-cli、curl、jq。
#
# 构建(项目根目录):
#   docker build -t <registry>/xagent-backup:<immutable-tag> deployment/backup
FROM redis:7.4-bookworm@sha256:e9b2e45ecd47fbb69b877cf8d045d5cccaaaed52524b6e098b4abe8212994f73 AS redis_tools

FROM postgres:16-bookworm@sha256:60f4761b9035e0b8d5218f701a8c3382f641bf12b1604822574cf5be3baeb537

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    jq \
    awscli \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Debian bookworm 的 redis-tools 仅 7.0，无法验证 Redis 7.4 产生的
# RDB v12。从官方 7.4 镜像复用同版本工具，同时保留 PG16 客户端。
COPY --from=redis_tools /usr/local/bin/redis-cli /usr/local/bin/redis-cli
COPY --from=redis_tools /usr/local/bin/redis-server /usr/local/bin/redis-server
RUN ln -s /usr/local/bin/redis-server /usr/local/bin/redis-check-rdb

# Debian 已预置名为 backup 的系统用户；使用专用固定 UID/GID，避免
# 构建冲突并与 Helm PVC 的 fsGroup 保持一致。
RUN groupadd -g 10001 xagentbackup \
    && useradd -m -u 10001 -g 10001 xagentbackup
USER 10001:10001

COPY backup.sh /usr/local/bin/backup.sh

# 容器内直接执行脚本; CronJob 以 /bin/bash /usr/local/bin/backup.sh 调用
ENTRYPOINT ["/bin/bash", "/usr/local/bin/backup.sh"]
