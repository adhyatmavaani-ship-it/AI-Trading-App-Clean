{{/*
Expand the name of the chart.
*/}}
{{- define "trading-backend.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "trading-backend.fullname" -}}
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

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "trading-backend.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "trading-backend.labels" -}}
helm.sh/chart: {{ include "trading-backend.chart" . }}
{{ include "trading-backend.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "trading-backend.selectorLabels" -}}
app.kubernetes.io/name: {{ include "trading-backend.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Track-aware selector labels.
*/}}
{{- define "trading-backend.trackSelectorLabels" -}}
{{- $root := index . "root" -}}
{{- $track := default "stable" (index . "track") -}}
{{ include "trading-backend.selectorLabels" $root }}
rollout.track: {{ $track }}
{{- end }}

{{/*
Track-aware resource naming.
*/}}
{{- define "trading-backend.resourceName" -}}
{{- $root := index . "root" -}}
{{- $track := default "stable" (index . "track") -}}
{{- if eq $track "stable" -}}
{{ include "trading-backend.fullname" $root }}
{{- else -}}
{{ printf "%s-%s" (include "trading-backend.fullname" $root) $track | trunc 63 | trimSuffix "-" }}
{{- end -}}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "trading-backend.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "trading-backend.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}
