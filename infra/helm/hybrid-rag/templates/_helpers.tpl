{{- define "hybrid-rag.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "hybrid-rag.fullname" -}}
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

{{- define "hybrid-rag.labels" -}}
helm.sh/chart: {{ include "hybrid-rag.name" . }}-{{ .Chart.Version }}
{{ include "hybrid-rag.selectorLabels" . }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{- define "hybrid-rag.selectorLabels" -}}
app.kubernetes.io/name: {{ include "hybrid-rag.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app: hybrid-rag
{{- end }}
