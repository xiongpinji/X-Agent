#!/bin/sh
set -eu

: "${ENVIRONMENT:?ENVIRONMENT must be set}"
: "${CLUSTER_NAME:?CLUSTER_NAME must be set}"
: "${XAGENT_METRICS_TARGET:?XAGENT_METRICS_TARGET must be set}"

case "$ENVIRONMENT" in
  *[!A-Za-z0-9_.-]*) echo "ENVIRONMENT contains unsupported characters" >&2; exit 2 ;;
esac
case "$CLUSTER_NAME" in
  *[!A-Za-z0-9_.-]*) echo "CLUSTER_NAME contains unsupported characters" >&2; exit 2 ;;
esac
case "$XAGENT_METRICS_TARGET" in
  *[!A-Za-z0-9_.:-]*) echo "XAGENT_METRICS_TARGET contains unsupported characters" >&2; exit 2 ;;
esac

sed \
  -e "s|\${ENVIRONMENT}|${ENVIRONMENT}|g" \
  -e "s|\${CLUSTER_NAME}|${CLUSTER_NAME}|g" \
  -e "s|\${XAGENT_METRICS_TARGET}|${XAGENT_METRICS_TARGET}|g" \
  /etc/prometheus/prometheus.yml > /tmp/prometheus.rendered.yml

if [ "${PROMETHEUS_CHECK_ONLY:-false}" = "true" ]; then
  exec /bin/promtool check config /tmp/prometheus.rendered.yml
fi

exec /bin/prometheus "$@"
