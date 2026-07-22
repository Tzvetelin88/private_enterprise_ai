{{- define "graph-rag.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "graph-rag.fullname" -}}
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

{{- define "graph-rag.labels" -}}
helm.sh/chart: {{ include "graph-rag.name" . }}-{{ .Chart.Version }}
{{ include "graph-rag.selectorLabels" . }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{- define "graph-rag.selectorLabels" -}}
app.kubernetes.io/name: {{ include "graph-rag.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app: graph-rag
{{- end }}
