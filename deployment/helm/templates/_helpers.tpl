{{/*
P1-15: 组件主机名解析 —— 组件启用时用集群内 Service 名;
禁用时要求 external.*Host 显式提供外部端点(显式依赖外部 DB, 见 values.yaml external 段)。
*/}}
{{- define "xagent.postgresHost" -}}
{{- if .Values.postgres.enabled -}}
postgres
{{- else -}}
{{- required "external.postgresHost must be set when postgres.enabled=false" .Values.external.postgresHost -}}
{{- end -}}
{{- end -}}

{{- define "xagent.redisHost" -}}
{{- if .Values.redis.enabled -}}
redis
{{- else -}}
{{- required "external.redisHost must be set when redis.enabled=false" .Values.external.redisHost -}}
{{- end -}}
{{- end -}}

{{- define "xagent.qdrantHost" -}}
{{- if .Values.qdrant.enabled -}}
qdrant
{{- else -}}
{{- required "external.qdrantHost must be set when qdrant.enabled=false" .Values.external.qdrantHost -}}
{{- end -}}
{{- end -}}

{{- define "xagent.neo4jHost" -}}
{{- if .Values.neo4j.enabled -}}
neo4j
{{- else -}}
{{- required "external.neo4jHost must be set when neo4j.enabled=false" .Values.external.neo4jHost -}}
{{- end -}}
{{- end -}}
