{{- define "mcp-client.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "mcp-client.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{- define "mcp-client.labels" -}}
helm.sh/chart: {{ include "mcp-client.name" . }}-{{ .Chart.Version }}
{{ include "mcp-client.selectorLabels" . }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{- define "mcp-client.selectorLabels" -}}
app.kubernetes.io/name: {{ include "mcp-client.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app: mcp-client
{{- end }}
