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
{{- else if .Values.appEnv.neo4jEnabled -}}
{{- required "external.neo4jHost must be set when neo4j.enabled=false and appEnv.neo4jEnabled=true" .Values.external.neo4jHost -}}
{{- else -}}
{{- /* P1-15: neo4j 功能关闭(appEnv.neo4jEnabled=false)时不强制外部端点, 渲染空占位 */ -}}
{{- end -}}
{{- end -}}

{{- define "xagent.imageRepository" -}}
{{- required "image.repository must be set to the audited production image repository" .Values.image.repository -}}
{{- end -}}

{{- define "xagent.imageTag" -}}
{{- $tag := required "image.tag must be set to an immutable image tag" .Values.image.tag -}}
{{- if not (regexMatch "^sha-[0-9a-f]{40}$" $tag) -}}
{{- fail "image.tag must be sha- followed by the full 40-character Git SHA" -}}
{{- end -}}
{{- $tag -}}
{{- end -}}

{{- define "xagent.backupImage" -}}
{{- $repository := required "backup.image.repository must be set when backup.enabled=true" .Values.backup.image.repository -}}
{{- $tag := required "backup.image.tag must be set when backup.enabled=true" .Values.backup.image.tag -}}
{{- if not (regexMatch "^sha-[0-9a-f]{40}$" $tag) -}}
{{- fail "backup.image.tag must be sha- followed by the full 40-character Git SHA" -}}
{{- end -}}
{{- printf "%s:%s" $repository $tag -}}
{{- end -}}

{{- define "xagent.secretName" -}}
{{- required "secrets.existingSecret must name a pre-provisioned Kubernetes Secret" .Values.secrets.existingSecret -}}
{{- end -}}

{{- define "xagent.ingressHost" -}}
{{- required "ingress.hosts[0].host must be set when ingress.enabled=true" (first .Values.ingress.hosts).host -}}
{{- end -}}

{{- define "xagent.artifactsClaim" -}}
{{- required "artifacts.existingClaim must name a shared ReadWriteMany PVC" .Values.artifacts.existingClaim -}}
{{- end -}}

{{- define "xagent.verifiedBackupId" -}}
{{- required "migration.verifiedBackupId must reference an operator-verified pre-migration backup" .Values.migration.verifiedBackupId -}}
{{- end -}}

{{- define "xagent.backupBucket" -}}
{{- if .Values.backup.s3.enabled -}}
{{- required "backup.s3.bucket must be set when S3 backup is enabled" .Values.backup.s3.bucket -}}
{{- end -}}
{{- end -}}

{{- define "xagent.backupRoleArn" -}}
{{- if .Values.backup.s3.enabled -}}
{{- required "backup.serviceAccount.roleArn must be set when S3 backup is enabled" .Values.backup.serviceAccount.roleArn -}}
{{- end -}}
{{- end -}}
