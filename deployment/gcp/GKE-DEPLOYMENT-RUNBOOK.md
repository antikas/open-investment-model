# GKE + Cloud SQL Deployment Runbook for agentINVEST

Complete operational guide for deploying agentINVEST to Google Kubernetes Engine with Cloud SQL backend.

## Prerequisites

- `gcloud` CLI (latest version)
- `kubectl` installed
- `helm` installed (optional, for advanced configurations)
- Sufficient GCP permissions (Compute Admin, Cloud SQL Admin, Kubernetes Admin)
- GKE and Cloud SQL APIs enabled

## Step 1: Set up environment variables

```sh
export PROJECT_ID="$(gcloud config get-value project)"
export REGION="us-central1"
export ZONE="us-central1-a"
export CLUSTER_NAME="agentinvest-gke"
export CLOUD_SQL_INSTANCE="agentinvest-sql"
export CLOUD_SQL_VERSION="POSTGRES_15"
export IMAGE_TAG="latest"
export NAMESPACE="agentinvest"
```

## Step 2: Create GKE cluster

```sh
gcloud container clusters create "${CLUSTER_NAME}" \
  --region="${REGION}" \
  --node-locations="${ZONE}" \
  --num-nodes=3 \
  --machine-type=e2-standard-2 \
  --disk-size=50 \
  --enable-autoscaling \
  --min-nodes=2 \
  --max-nodes=10 \
  --enable-stackdriver-kubernetes \
  --enable-ip-alias \
  --network="default" \
  --subnetwork="default" \
  --enable-autorepair \
  --enable-autoupgrade \
  --workload-pool="${PROJECT_ID}.svc.id.goog" \
  --addons=HorizontalPodAutoscaling,HttpLoadBalancing,GcePersistentDiskCsiDriver

# Get cluster credentials
gcloud container clusters get-credentials "${CLUSTER_NAME}" \
  --region="${REGION}"

# Verify
kubectl cluster-info
kubectl get nodes
```

## Step 3: Create Cloud SQL instance

```sh
gcloud sql instances create "${CLOUD_SQL_INSTANCE}" \
  --database-version="${CLOUD_SQL_VERSION}" \
  --region="${REGION}" \
  --tier=db-custom-2-8192 \
  --storage-type=PD_SSD \
  --storage-size=100GB \
  --availability-type=REGIONAL \
  --backup-start-time=02:00 \
  --enable-bin-log \
  --retained-backups-count=30

# Wait for instance to be ready
gcloud sql operations wait --project="${PROJECT_ID}" $(gcloud sql operations list --project="${PROJECT_ID}" --instance="${CLOUD_SQL_INSTANCE}" --filter='status!=DONE' --format='value(name)' | head -1)

# Get Cloud SQL instance connection name
export CLOUD_SQL_CONNECTION_NAME=$(gcloud sql instances describe "${CLOUD_SQL_INSTANCE}" --format='value(connectionName)')
echo "Cloud SQL Connection Name: ${CLOUD_SQL_CONNECTION_NAME}"
```

## Step 4: Create databases in Cloud SQL

```sh
# Create postgres super user (if not using default 'postgres')
gcloud sql users create agentinvest \
  --instance="${CLOUD_SQL_INSTANCE}" \
  --password="$(openssl rand -base64 32)"

# Store password in Secret Manager
AGENTINVEST_DB_PASSWORD="$(openssl rand -base64 32)"
echo -n "${AGENTINVEST_DB_PASSWORD}" | gcloud secrets create agentinvest-db-password --data-file=-

# Connect to Cloud SQL and create databases
gcloud sql connect "${CLOUD_SQL_INSTANCE}" \
  --user=postgres << EOF
CREATE DATABASE restate_state;
CREATE DATABASE canonical_db;
CREATE USER agentinvest WITH PASSWORD '${AGENTINVEST_DB_PASSWORD}';
GRANT ALL PRIVILEGES ON DATABASE restate_state TO agentinvest;
GRANT ALL PRIVILEGES ON DATABASE canonical_db TO agentinvest;
EOF

# Verify databases
gcloud sql databases list --instance="${CLOUD_SQL_INSTANCE}"
```

## Step 5: Set up Private Service Connection

```sh
# Enable the Service Networking API
gcloud services enable servicenetworking.googleapis.com

# Reserve IP range for private service connection
gcloud compute addresses create google-managed-services-default \
  --global \
  --purpose=VPC_PEERING \
  --prefix-length=16 \
  --network=default \
  || echo "IP range already exists"

# Create private service connection
gcloud services vpc-peerings connect \
  --service=servicenetworking.googleapis.com \
  --ranges=google-managed-services-default \
  --network=default \
  || echo "VPC peering already established"

# Verify private IP is assigned
gcloud sql instances describe "${CLOUD_SQL_INSTANCE}" --format='value(ipAddresses[0].ipAddress)'
```

## Step 6: Create GKE Workload Identity service accounts

```sh
# Create service accounts
kubectl create namespace "${NAMESPACE}"

kubectl create serviceaccount agentinvest-gke \
  --namespace="${NAMESPACE}"

# Create GCP service account
gcloud iam service-accounts create agentinvest-gke-sa \
  --display-name="agentINVEST GKE service account"

# Bind Kubernetes SA to GCP SA
gcloud iam service-accounts add-iam-policy-binding \
  agentinvest-gke-sa@${PROJECT_ID}.iam.gserviceaccount.com \
  --role=roles/iam.workloadIdentityUser \
  --member="serviceAccount:${PROJECT_ID}.svc.id.goog[${NAMESPACE}/agentinvest-gke]"

# Annotate Kubernetes SA
kubectl annotate serviceaccount agentinvest-gke \
  --namespace="${NAMESPACE}" \
  iam.gke.io/gcp-service-account=agentinvest-gke-sa@${PROJECT_ID}.iam.gserviceaccount.com
```

## Step 7: Grant IAM roles to Workload Identity service account

```sh
# Cloud SQL Client
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:agentinvest-gke-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/cloudsql.client"

# Secret Manager Accessor
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:agentinvest-gke-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

# Cloud Logging (write logs)
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:agentinvest-gke-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/logging.logWriter"

# Cloud Monitoring (write metrics)
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:agentinvest-gke-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/monitoring.metricWriter"

# Artifact Registry reader (pull images)
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:agentinvest-gke-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/artifactregistry.reader"
```

## Step 8: Create Cloud SQL Proxy Ingress (Cloud SQL Auth Proxy in pod)

Option A: Use Cloud SQL Auth Proxy as sidecar container (built into deployments)
Option B: Use Private IP directly (simpler, requires Private Service Connection)

For this guide, we use **Private IP + Private Service Connection** (already set up above).

Cloud SQL connection string format for private IP:
```
postgresql://agentinvest:PASSWORD@PRIVATE_IP:5432/DATABASE_NAME?sslmode=require
```

Retrieve the private IP:
```sh
export CLOUD_SQL_PRIVATE_IP=$(gcloud sql instances describe "${CLOUD_SQL_INSTANCE}" \
  --format='value(ipAddresses[0].ipAddress)')
echo "Cloud SQL Private IP: ${CLOUD_SQL_PRIVATE_IP}"
```

## Step 9: Create Kubernetes secrets

```sh
# Anthropic API key
kubectl create secret generic anthropic-credentials \
  --namespace="${NAMESPACE}" \
  --from-literal=api-key="${ANTHROPIC_API_KEY}"

# Cloud SQL credentials
CLOUD_SQL_PASSWORD=$(gcloud secrets versions access latest --secret=agentinvest-db-password)
kubectl create secret generic cloudsql-credentials \
  --namespace="${NAMESPACE}" \
  --from-literal=username=agentinvest \
  --from-literal=password="${CLOUD_SQL_PASSWORD}"

# Cloud SQL connection string
kubectl create secret generic cloudsql-connection \
  --namespace="${NAMESPACE}" \
  --from-literal=connection-string="postgresql://agentinvest:${CLOUD_SQL_PASSWORD}@${CLOUD_SQL_PRIVATE_IP}:5432/canonical_db?sslmode=require" \
  --from-literal=restate-connection-string="postgresql://agentinvest:${CLOUD_SQL_PASSWORD}@${CLOUD_SQL_PRIVATE_IP}:5432/restate_state?sslmode=require"
```

## Step 10: Build and push container images

```sh
cd /path/to/open-investment-model

# Build images
./deployment/gcp/build-images.sh

# Verify images in Artifact Registry
gcloud artifacts docker images list gcr.io/${PROJECT_ID} --include-tags
```

## Step 11: Create Kubernetes manifests

Create `deployment/gcp/kubernetes/namespace.yaml`:
```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: agentinvest
```

Create `deployment/gcp/kubernetes/restate-deployment.yaml`:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: restate
  namespace: agentinvest
spec:
  replicas: 1
  selector:
    matchLabels:
      app: restate
  template:
    metadata:
      labels:
        app: restate
    spec:
      serviceAccountName: agentinvest-gke
      containers:
      - name: restate
        image: gcr.io/${PROJECT_ID}/agentinvest-restate:latest
        imagePullPolicy: IfNotPresent
        ports:
        - containerPort: 8080
          name: ingress
        - containerPort: 9070
          name: admin
        env:
        - name: RESTATE_VERSION
          value: "1.6.2"
        - name: RESTATE_PORT
          value: "8080"
        - name: RESTATE_ADMIN_URL
          value: "http://127.0.0.1:9070"
        - name: RESTATE_INGRESS_URL
          value: "http://127.0.0.1:8080"
        - name: RESTATE_DB_DRIVER
          value: "postgres"
        - name: RESTATE_DB_HOST
          valueFrom:
            secretKeyRef:
              name: cloudsql-connection
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
---
apiVersion: v1
kind: Service
metadata:
  name: restate-service
  namespace: agentinvest
spec:
  type: ClusterIP
  selector:
    app: restate
  ports:
  - name: ingress
    port: 8080
    targetPort: 8080
  - name: admin
    port: 9070
    targetPort: 9070
```

Create similar manifests for `ts-endpoint`, `py-endpoint`, and `operator-ui`.

## Step 12: Deploy to GKE

```sh
# Create namespace and secrets
kubectl create namespace "${NAMESPACE}"

# Apply manifests
kubectl apply -f deployment/gcp/kubernetes/namespace.yaml
kubectl apply -f deployment/gcp/kubernetes/restate-deployment.yaml
kubectl apply -f deployment/gcp/kubernetes/ts-endpoint-deployment.yaml
kubectl apply -f deployment/gcp/kubernetes/py-endpoint-deployment.yaml
kubectl apply -f deployment/gcp/kubernetes/operator-ui-deployment.yaml

# Verify deployments
kubectl get deployments --namespace="${NAMESPACE}"
kubectl get pods --namespace="${NAMESPACE}"

# Check pod logs
kubectl logs -n "${NAMESPACE}" -l app=restate --tail=50
```

## Step 13: Set up Ingress for Operator UI

```bash
# Create Ingress resource
cat > deployment/gcp/kubernetes/ingress.yaml << EOF
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: agentinvest-ingress
  namespace: ${NAMESPACE}
  annotations:
    kubernetes.io/ingress.class: "gce"
    kubernetes.io/ingress.global-static-ip-name: "agentinvest-ip"
    networking.gke.io/managed-certificates: "agentinvest-cert"
    kubernetes.io/ingress.allow-http: "false"
spec:
  rules:
  - host: "agentinvest.example.com"  # Replace with your domain
    http:
      paths:
      - path: /*
        pathType: ImplementationSpecific
        backend:
          service:
            name: operator-ui-service
            port:
              number: 4180
EOF

kubectl apply -f deployment/gcp/kubernetes/ingress.yaml

# Reserve static IP
gcloud compute addresses create agentinvest-ip --global

# Get IP address
gcloud compute addresses describe agentinvest-ip --global --format='value(address)'
```

## Step 14: Verify deployment

```sh
# Wait for pods to be ready
kubectl wait --for=condition=Ready pod -l app=restate \
  --namespace="${NAMESPACE}" \
  --timeout=300s

# Port-forward to Restate admin
kubectl port-forward -n "${NAMESPACE}" svc/restate-service 9070:9070 &

# Test Restate health
curl -s http://localhost:9070/health | jq .

# Port-forward to Operator UI
kubectl port-forward -n "${NAMESPACE}" svc/operator-ui-service 4180:4180 &

# Access operator UI at http://localhost:4180
```

## Step 15: Run smoke tests

```sh
bash deployment/gcp/kubernetes/smoke-test.sh
```

## Monitoring and Logs

```sh
# Stream logs from all pods
kubectl logs -n "${NAMESPACE}" -f -l "app in (restate,ts-endpoint,py-endpoint,operator-ui)" --all-containers=true --timestamps=true

# Check Cloud Logging
gcloud logging read "resource.type=k8s_container AND resource.labels.namespace_name=${NAMESPACE}" \
  --limit=50 \
  --format=json

# View metrics in Cloud Monitoring
# Dashboard: https://console.cloud.google.com/monitoring/dashboards
```

## Troubleshooting

### Pods not starting
```sh
kubectl describe pod <pod-name> -n "${NAMESPACE}"
kubectl logs <pod-name> -n "${NAMESPACE}" --previous
```

### Cloud SQL connection issues
```sh
# Test connectivity from a pod
kubectl run -it --rm debug --image=google/cloud-sql-proxy:latest \
  --serviceaccount=agentinvest-gke \
  --namespace="${NAMESPACE}" \
  -- bash

# Inside pod:
psql "postgresql://agentinvest:PASSWORD@PRIVATE_IP:5432/canonical_db"
```

## Clean up

```sh
# Delete all GKE resources
kubectl delete namespace "${NAMESPACE}"

# Delete GKE cluster
gcloud container clusters delete "${CLUSTER_NAME}" --region="${REGION}"

# Delete Cloud SQL instance
gcloud sql instances delete "${CLOUD_SQL_INSTANCE}"

# Delete static IP
gcloud compute addresses delete agentinvest-ip --global

# Delete secrets
gcloud secrets delete agentinvest-db-password
```

## Next Steps

- [ ] Set up Cloud IAP for Operator UI authentication
- [ ] Configure Cloud Armor DDoS protection
- [ ] Enable GKE workload identity for better security
- [ ] Set up Cloud Monitoring dashboards and alerts
- [ ] Implement dbt Cloud SQL profile and test data pipeline
- [ ] Plan database backup and disaster recovery drills
- [ ] Document runbooks for operational handoff
