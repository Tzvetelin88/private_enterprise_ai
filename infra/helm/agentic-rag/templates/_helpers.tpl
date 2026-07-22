{{- define "agentic-rag.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "agentic-rag.fullname" -}}
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

{{- define "agentic-rag.labels" -}}
helm.sh/chart: {{ include "agentic-rag.name" . }}-{{ .Chart.Version }}
{{ include "agentic-rag.selectorLabels" . }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{- define "agentic-rag.selectorLabels" -}}
app.kubernetes.io/name: {{ include "agentic-rag.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app: agentic-rag
{{- end }}
