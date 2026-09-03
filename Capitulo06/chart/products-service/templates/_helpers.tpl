{{- define "products-service.name" -}}
{{- .Chart.Name | trunc 63 | trimSuffix "-" -}}
{{- end }}

{{- define "products-service.fullname" -}}
{{- printf "%s" (include "products-service.name" .) | trunc 63 | trimSuffix "-" -}}
{{- end }}

{{- define "products-service.selectorLabels" -}}
app.kubernetes.io/name: {{ include "products-service.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{- define "products-service.labels" -}}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | quote }}
{{ include "products-service.selectorLabels" . }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}
