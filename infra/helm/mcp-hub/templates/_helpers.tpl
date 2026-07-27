{{- define "mcp-hub.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "mcp-hub.fullname" -}}
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

{{- define "mcp-hub.labels" -}}
helm.sh/chart: {{ include "mcp-hub.name" . }}-{{ .Chart.Version }}
{{ include "mcp-hub.selectorLabels" . }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{- define "mcp-hub.selectorLabels" -}}
app.kubernetes.io/name: {{ include "mcp-hub.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app: mcp-hub
{{- end }}
