#!/usr/bin/env bash
# Kubernetes manifest generator for agentINVEST GKE deployment
# This script creates all necessary Kubernetes manifests from templates

set -euo pipefail

PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project)}"
REGION="${REGION:-us-central1}"
NAMESPACE="${NAMESPACE:-agentinvest}"
IMAGE_TAG="${IMAGE_TAG:-latest}"

mkdir -p deployment/gcp/kubernetes

cat > deployment/gcp/kubernetes/namespace.yaml << 'EOF'
apiVersion: v1
kind: Namespace
metadata:
  name: agentinvest
  labels:
    app.kubernetes.io/name: agentinvest
    app.kubernetes.io/version: "1.0"
EOF

cat > deployment/gcp/kubernetes/service-account.yaml << 'EOF'
apiVersion: v1
kind: ServiceAccount
metadata:
  name: agentinvest-gke
  namespace: agentinvest
  annotations:
    iam.gke.io/gcp-service-account: agentinvest-gke-sa@PROJECT_ID.iam.gserviceaccount.com
EOF

cat > deployment/gcp/kubernetes/restate-deployment.yaml << 'EOF'
apiVersion: apps/v1
kind: Deployment
metadata:
  name: restate
  namespace: agentinvest
  labels:
    app: restate
    version: "1.6.2"
spec:
  replicas: 1
  selector:
    matchLabels:
      app: restate
  template:
    metadata:
      labels:
        app: restate
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: "9070"
        prometheus.io/path: "/metrics"
    spec:
      serviceAccountName: agentinvest-gke
      containers:
      - name: restate
        image: gcr.io/PROJECT_ID/agentinvest-restate:IMAGE_TAG
        imagePullPolicy: IfNotPresent
        ports:
        - name: ingress
          containerPort: 8080
          protocol: TCP
        - name: admin
          containerPort: 9070
          protocol: TCP
        - name: metrics
          containerPort: 5122
          protocol: TCP
        env:
        - name: RESTATE_VERSION
          value: "1.6.2"
        - name: RESTATE_PORT
          value: "8080"
        - name: RESTATE_ADMIN_URL
          value: "http://127.0.0.1:9070"
        - name: RESTATE_INGRESS_URL
          value: "http://127.0.0.1:8080"
        # Cloud SQL configuration
        - name: RESTATE_DB_DRIVER
          value: "postgres"
        - name: RESTATE_DB_HOST
          valueFrom:
            secretKeyRef:
              name: cloudsql-credentials
              key: host
        - name: RESTATE_DB_PORT
          value: "5432"
        - name: RESTATE_DB_USER
          valueFrom:
            secretKeyRef:
              name: cloudsql-credentials
              key: username
        - name: RESTATE_DB_PASSWORD
          valueFrom:
            secretKeyRef:
              name: cloudsql-credentials
              key: password
        - name: RESTATE_DB_NAME
          value: "restate_state"
        - name: RESTATE_DB_SSL_MODE
          value: "require"
        resources:
          requests:
            memory: "2Gi"
            cpu: "2"
          limits:
            memory: "2Gi"
            cpu: "2"
        livenessProbe:
          httpGet:
            path: /health
            port: admin
          initialDelaySeconds: 30
          periodSeconds: 10
          timeoutSeconds: 5
          failureThreshold: 3
        readinessProbe:
          httpGet:
            path: /health
            port: admin
          initialDelaySeconds: 10
          periodSeconds: 5
          timeoutSeconds: 3
          failureThreshold: 2
        securityContext:
          allowPrivilegeEscalation: false
          runAsNonRoot: true
          runAsUser: 1000
          readOnlyRootFilesystem: false
---
apiVersion: v1
kind: Service
metadata:
  name: restate-service
  namespace: agentinvest
  labels:
    app: restate
spec:
  type: ClusterIP
  selector:
    app: restate
  ports:
  - name: ingress
    port: 8080
    targetPort: 8080
    protocol: TCP
  - name: admin
    port: 9070
    targetPort: 9070
    protocol: TCP
  - name: metrics
    port: 5122
    targetPort: 5122
    protocol: TCP
EOF

cat > deployment/gcp/kubernetes/ts-endpoint-deployment.yaml << 'EOF'
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ts-endpoint
  namespace: agentinvest
  labels:
    app: ts-endpoint
spec:
  replicas: 2
  selector:
    matchLabels:
      app: ts-endpoint
  template:
    metadata:
      labels:
        app: ts-endpoint
    spec:
      serviceAccountName: agentinvest-gke
      containers:
      - name: ts-endpoint
        image: gcr.io/PROJECT_ID/agentinvest-ts-endpoint:IMAGE_TAG
        imagePullPolicy: IfNotPresent
        ports:
        - name: rpc
          containerPort: 9090
          protocol: TCP
        env:
        - name: RESTATE_URL
          value: "http://restate-service:8080"
        - name: RESTATE_ADMIN_URL
          value: "http://restate-service:9070"
        - name: AGENTINVEST_ENDPOINT_PORT
          value: "9090"
        - name: AGENTINVEST_ENDPOINT_HOST
          value: "0.0.0.0"
        - name: NODE_ENV
          value: "production"
        resources:
          requests:
            memory: "1Gi"
            cpu: "1"
          limits:
            memory: "1Gi"
            cpu: "1"
        livenessProbe:
          tcpSocket:
            port: 9090
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          tcpSocket:
            port: 9090
          initialDelaySeconds: 10
          periodSeconds: 5
        securityContext:
          allowPrivilegeEscalation: false
          runAsNonRoot: true
          runAsUser: 1000
---
apiVersion: v1
kind: Service
metadata:
  name: ts-endpoint-service
  namespace: agentinvest
  labels:
    app: ts-endpoint
spec:
  type: ClusterIP
  selector:
    app: ts-endpoint
  ports:
  - name: rpc
    port: 9090
    targetPort: 9090
    protocol: TCP
EOF

cat > deployment/gcp/kubernetes/py-endpoint-deployment.yaml << 'EOF'
apiVersion: apps/v1
kind: Deployment
metadata:
  name: py-endpoint
  namespace: agentinvest
  labels:
    app: py-endpoint
spec:
  replicas: 2
  selector:
    matchLabels:
      app: py-endpoint
  template:
    metadata:
      labels:
        app: py-endpoint
    spec:
      serviceAccountName: agentinvest-gke
      containers:
      - name: py-endpoint
        image: gcr.io/PROJECT_ID/agentinvest-py-endpoint:IMAGE_TAG
        imagePullPolicy: IfNotPresent
        ports:
        - name: rpc
          containerPort: 9091
          protocol: TCP
        env:
        - name: RESTATE_URL
          value: "http://restate-service:8080"
        - name: RESTATE_ADMIN_URL
          value: "http://restate-service:9070"
        - name: AGENTINVEST_PY_ENDPOINT_PORT
          value: "9091"
        - name: AGENTINVEST_PY_ENDPOINT_HOST
          value: "0.0.0.0"
        - name: AGENTINVEST_DUCKDB_PATH
          value: "/tmp/agentinvest/canonical.db"
        - name: ANTHROPIC_API_KEY
          valueFrom:
            secretKeyRef:
              name: anthropic-credentials
              key: api-key
        - name: CANONICAL_DB_CONNECTION_STRING
          valueFrom:
            secretKeyRef:
              name: cloudsql-connection
              key: connection-string
        - name: CANONICAL_DB_HOST
          valueFrom:
            secretKeyRef:
              name: cloudsql-credentials
              key: host
        - name: CANONICAL_DB_USER
          valueFrom:
            secretKeyRef:
              name: cloudsql-credentials
              key: username
        - name: CANONICAL_DB_PASSWORD
          valueFrom:
            secretKeyRef:
              name: cloudsql-credentials
              key: password
        - name: CANONICAL_DB_NAME
          value: "canonical_db"
        resources:
          requests:
            memory: "2Gi"
            cpu: "2"
          limits:
            memory: "2Gi"
            cpu: "2"
        livenessProbe:
          tcpSocket:
            port: 9091
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          tcpSocket:
            port: 9091
          initialDelaySeconds: 10
          periodSeconds: 5
        securityContext:
          allowPrivilegeEscalation: false
          runAsNonRoot: true
          runAsUser: 1000
---
apiVersion: v1
kind: Service
metadata:
  name: py-endpoint-service
  namespace: agentinvest
  labels:
    app: py-endpoint
spec:
  type: ClusterIP
  selector:
    app: py-endpoint
  ports:
  - name: rpc
    port: 9091
    targetPort: 9091
    protocol: TCP
EOF

cat > deployment/gcp/kubernetes/operator-ui-deployment.yaml << 'EOF'
apiVersion: apps/v1
kind: Deployment
metadata:
  name: operator-ui
  namespace: agentinvest
  labels:
    app: operator-ui
spec:
  replicas: 2
  selector:
    matchLabels:
      app: operator-ui
  template:
    metadata:
      labels:
        app: operator-ui
    spec:
      serviceAccountName: agentinvest-gke
      containers:
      - name: operator-ui
        image: gcr.io/PROJECT_ID/agentinvest-operator-ui:IMAGE_TAG
        imagePullPolicy: IfNotPresent
        ports:
        - name: http
          containerPort: 4180
          protocol: TCP
        env:
        - name: NODE_ENV
          value: "production"
        - name: RESTATE_ADMIN_URL
          value: "http://restate-service:9070"
        - name: CANONICAL_DB_CONNECTION_STRING
          valueFrom:
            secretKeyRef:
              name: cloudsql-connection
              key: connection-string
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "512Mi"
            cpu: "1"
        livenessProbe:
          httpGet:
            path: /health
            port: http
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: http
          initialDelaySeconds: 10
          periodSeconds: 5
        securityContext:
          allowPrivilegeEscalation: false
          runAsNonRoot: true
          runAsUser: 1000
---
apiVersion: v1
kind: Service
metadata:
  name: operator-ui-service
  namespace: agentinvest
  labels:
    app: operator-ui
spec:
  type: ClusterIP
  selector:
    app: operator-ui
  ports:
  - name: http
    port: 4180
    targetPort: 4180
    protocol: TCP
EOF

cat > deployment/gcp/kubernetes/hpa.yaml << 'EOF'
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: ts-endpoint-hpa
  namespace: agentinvest
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: ts-endpoint
  minReplicas: 1
  maxReplicas: 5
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: py-endpoint-hpa
  namespace: agentinvest
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: py-endpoint
  minReplicas: 1
  maxReplicas: 4
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 75
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 85
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: operator-ui-hpa
  namespace: agentinvest
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: operator-ui
  minReplicas: 1
  maxReplicas: 3
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 80
EOF

cat > deployment/gcp/kubernetes/network-policy.yaml << 'EOF'
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: agentinvest-deny-all
  namespace: agentinvest
spec:
  podSelector: {}
  policyTypes:
  - Ingress
  - Egress
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: restate-allow
  namespace: agentinvest
spec:
  podSelector:
    matchLabels:
      app: restate
  policyTypes:
  - Ingress
  ingress:
  - from:
    - podSelector:
        matchLabels:
          app: ts-endpoint
    ports:
    - protocol: TCP
      port: 8080
  - from:
    - podSelector:
        matchLabels:
          app: py-endpoint
    ports:
    - protocol: TCP
      port: 8080
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: endpoints-allow-egress
  namespace: agentinvest
spec:
  podSelector:
    matchExpressions:
    - key: app
      operator: In
      values:
      - ts-endpoint
      - py-endpoint
  policyTypes:
  - Egress
  egress:
  - to:
    - podSelector:
        matchLabels:
          app: restate
    ports:
    - protocol: TCP
      port: 8080
  - to:
    - namespaceSelector: {}
    ports:
    - protocol: TCP
      port: 53  # DNS
    - protocol: UDP
      port: 53  # DNS
  - to:
    - namespaceSelector: {}
    ports:
    - protocol: TCP
      port: 5432  # Cloud SQL
EOF

echo "Kubernetes manifests created in deployment/gcp/kubernetes/"
echo ""
echo "Usage:"
echo "  kubectl apply -f deployment/gcp/kubernetes/namespace.yaml"
echo "  kubectl apply -f deployment/gcp/kubernetes/*.yaml"
echo ""
echo "To substitute variables (PROJECT_ID, IMAGE_TAG), use:"
echo "  envsubst < deployment/gcp/kubernetes/restate-deployment.yaml | kubectl apply -f -"
