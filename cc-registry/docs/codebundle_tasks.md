
## web-triage


- Validate Platform Egress
- Perform Inspection On URL



## aws-ec2-securitycheck


- Check For Untagged instances
- Check For Dangling Volumes
- Check For Open Routes
- Check For Overused Instances
- Check For Underused Instances
- Check For Underused Volumes
- Check For Overused Volumes



## github-get-repos-latency


- Check Latency When Creating a New GitHub Issue



## k8s-troubleshoot-deployment


- Troubleshoot Resourcing
- Troubleshoot Events
- Troubleshoot PVC
- Troubleshoot Pods



## gcp-opssuite-logquery-dashboard


- Get GCP Log Dashboard URL For Given Log Query



## k8s-postgres-triage


- Get Standard Resources
- Describe Custom Resources
- Get Pod Logs & Events
- Get Pod Resource Utilization
- Get Running Configuration
- Get Patroni Output
- Run DB Queries



## k8s-kubectl-run


- Running Kubectl And Adding Stdout To Report



## msteams-send-message


- Send a Message to an MS Teams Channel



## k8s-cortexmetrics-ingestor-health


- Fetch Ingestor Ring Member List and Status



## jira-search-issues-latency


- Create a new Jira Issue



## k8s-decommission-workloads


- Generate Decomission Commands



## twitter-query-tweets


- Query Twitter



## aws-cloudwatch-metricquery-dashboard


- Get CloudWatch MetricQuery Insights URL



## curl-generic


- Run Curl Command and Add to Report



## k8s-postgres-query


- Run Postgres Query And Results to Report



## k8s-kubectl-namespace-healthcheck


- Trace Namespace Errors
- Fetch Unready Pods
- Triage Namespace
- Object Condition Check
- Namespace Get All



## k8s-patroni-lag


- Determine Patroni Health



## slack-sendmessage


- Send Chat Message



## aws-s3-stalecheck


- Create Report For Stale Buckets



## gitlab-availability


- Check GitLab Server Status



## discord-sendmessage


- Send Chat Message



## rocketchat-sendmessage


- Send Chat Message



## googlechat-sendmessage


- Send Chat Message



## k8s-triage-patroni


- Get Patroni Status
- Get Pods Status
- Fetch Logs



## grpc-grpcurl-unary


- Run gRPCurl Command and Show Output



## k8s-triage-statefulset


- Check StatefulSets Replicas Ready
- Get Events For The StatefulSet
- Get StatefulSet Logs
- Get StatefulSet Manifests Dump



## aws-billing-costsacrosstags


- Get All Billing Sliced By Tags



## gcp-gcloudcli-generic


- Run Gcloud CLI Command and Push metric



## aws-vm-triage


- Get Max VM CPU Utilization In Last 3 Hours
- Get Lowest VM CPU Credits In Last 3 Hours
- Get Max VM CPU Credit Usage In Last 3 hours
- Get Max VM Memory Utilization In Last 3 Hours
- Get Max VM Volume Usage In Last 3 Hours



## aws-account-limit


- Get The Recently Created AWS Accounts



## k8s-triage-deploymentreplicas


- Fetch Logs
- Get Related Events
- Check Deployment Replicas



## aws-cloudformation-triage


- Get All Recent Stack Events



## opsgenie-alert


- Get Opsgenie System Info
- Create An Alert



## k8s-cluster-node-health


- Check for Node Restarts in Cluster `${CONTEXT}`



## k8s-jenkins-healthcheck


- Query The Jenkins Kubernetes Workload HTTP Endpoint
- Query For Stuck Jenkins Jobs



## k8s-gitops-gh-remediate


- Remediate Readiness and Liveness Probe GitOps Manifests in Namespace `${NAMESPACE}`
- Increase ResourceQuota for Namespace `${NAMESPACE}`
- Adjust Pod Resources to Match VPA Recommendation in `${NAMESPACE}`
- Expand Persistent Volume Claims in Namespace `${NAMESPACE}`



## aws-lambda-health


- List Lambda Versions and Runtimes
- Analyze AWS Lambda Invocation Errors
- Monitor AWS Lambda Performance Metrics



## k8s-fluxcd-reconcile


- Health Check Flux Reconciliation



## gcp-bucket-health


- Fetch GCP Bucket Storage Utilization for `${PROJECT_IDS}`
- Add GCP Bucket Storage Configuration for `${PROJECT_IDS}` to Report
- Check GCP Bucket Security Configuration for `${PROJECT_IDS}`
- Fetch GCP Bucket Storage Operations Rate for `${PROJECT_IDS}`



## k8s-deployment-healthcheck


- Check Deployment Log For Issues with `${DEPLOYMENT_NAME}`
- Fetch Deployments Logs for `${DEPLOYMENT_NAME}` and Add to Report
- Check Liveness Probe Configuration for Deployment `${DEPLOYMENT_NAME}`
- Check Readiness Probe Configuration for Deployment `${DEPLOYMENT_NAME}`
- Inspect Container Restarts for Deployment `${DEPLOYMENT_NAME}` Namespace `${NAMESPACE}`
- Inspect Deployment Warning Events for `${DEPLOYMENT_NAME}`
- Get Deployment Workload Details For `${DEPLOYMENT_NAME}` and Add to Report
- Inspect Deployment Replicas for `${DEPLOYMENT_NAME}`
- Check Deployment Event Anomalies for `${DEPLOYMENT_NAME}`
- Check ReplicaSet Health for Deployment `${DEPLOYMENT_NAME}`



## k8s-chaos-namespace


- Kill Random Pods In Namespace `${NAMESPACE}`
- OOMKill Pods In Namespace `${NAMESPACE}`
- Mangle Service Selector In Namespace `${NAMESPACE}`
- Mangle Service Port In Namespace `${NAMESPACE}`
- Fill Random Pod Tmp Directory In Namespace `${NAMESPACE}`



## k8s-statefulset-healthcheck


- Check Readiness Probe Configuration for StatefulSet `${STATEFULSET_NAME}`
- Check Liveness Probe Configuration for StatefulSet `${STATEFULSET_NAME}`
- Troubleshoot StatefulSet Warning Events for `${STATEFULSET_NAME}`
- Check StatefulSet Event Anomalies for `${STATEFULSET_NAME}`
- Fetch StatefulSet Logs for `${STATEFULSET_NAME}` and Add to Report
- Get Related StatefulSet `${STATEFULSET_NAME}` Events
- Fetch Manifest Details for StatefulSet `${STATEFULSET_NAME}`
- List StatefulSets with Unhealthy Replica Counts In Namespace `${NAMESPACE}`



## aws-cloudwatch-overused-ec2


- Check For Overutilized Ec2 Instances



## k8s-redis-healthcheck


- Ping `${DEPLOYMENT_NAME}` Redis Workload
- Verify `${DEPLOYMENT_NAME}` Redis Read Write Operation



## cmd-test


- Run CLI Command
- Run Bash File
- Log Suggestion



## k8s-podresources-health


- Show Pods Without Resource Limit or Resource Requests Set in Namespace `${NAMESPACE}`
- Get Pod Resource Utilization with Top in Namespace `${NAMESPACE}`
- Identify VPA Pod Resource Recommendations in Namespace `${NAMESPACE}`
- Identify Resource Constrained Pods In Namespace `${NAMESPACE}`



## gcloud-log-inspection


- Inspect GCP Logs For Common Errors



## gcloud-node-preempt


- List all nodes in an active prempt operation for GCP Project `${GCP_PROJECT_ID}`



## k8s-deployment-ops


- Restart Deployment `${DEPLOYMENT_NAME}` in Namespace `${NAMESPACE}`
- Force Delete Pods in Deployment `${DEPLOYMENT_NAME}` in Namespace `${NAMESPACE}`
- Rollback Deployment `${DEPLOYMENT_NAME}` in Namespace `${NAMESPACE}` to Previous Version
- Scale Down Deployment `${DEPLOYMENT_NAME}` in Namespace `${NAMESPACE}`
- Scale Up Deployment `${DEPLOYMENT_NAME}` in Namespace `${NAMESPACE}` by ${SCALE_UP_FACTOR}x
- Clean Up Stale ReplicaSets for Deployment `${DEPLOYMENT_NAME}` in Namespace `${NAMESPACE}`
- Scale Down Stale ReplicaSets for Deployment `${DEPLOYMENT_NAME}` in Namespace `${NAMESPACE}`



## k8s-flux-suspend-namespace


- Flux Suspend Namespace ${NAMESPACE}
- Unsuspend Flux for Namespace ${NAMESPACE}



## azure-appgateway-health


- Check for Resource Health Issues Affecting Application Gateway `${APP_GATEWAY_NAME}` In Resource Group `${AZ_RESOURCE_GROUP}`
- Check Configuration Health of Application Gateway `${APP_GATEWAY_NAME}` In Resource Group `${AZ_RESOURCE_GROUP}`
- Check Backend Pool Health for Application Gateway `${APP_GATEWAY_NAME}` In Resource Group `${AZ_RESOURCE_GROUP}`



## gh-actions-artifact-analysis


- Analyze artifact from GitHub workflow `${WORKFLOW_NAME}` in repository `${GITHUB_REPO}`



## k8s-argocd-helm-health


- Fetch all available ArgoCD Helm releases in namespace `${NAMESPACE}`
- Fetch Installed ArgoCD Helm release versions in namespace `${NAMESPACE}`



## k8s-serviceaccount-check


- Test Service Account Access to Kubernetes API Server in Namespace `${NAMESPACE}`



## terraform-cloud-workspace-lock-check


- Checking whether the Terraform Cloud Workspace is in a locked state



## k8s-app-troubleshoot


- Get `${CONTAINER_NAME}` Application Logs
- Scan `${CONTAINER_NAME}` Application For Misconfigured Environment
- Tail `${CONTAINER_NAME}` Application Logs For Stacktraces



## azure-appservice-triage


- Check for Resource Health Issues Affecting App Service `${APP_SERVICE_NAME}` In Resource Group `${AZ_RESOURCE_GROUP}`
- Check App Service `${APP_SERVICE_NAME}` Health Check Metrics In Resource Group `${AZ_RESOURCE_GROUP}`
- Fetch App Service `${APP_SERVICE_NAME}` Utilization Metrics In Resource Group `${AZ_RESOURCE_GROUP}`
- Get App Service `${APP_SERVICE_NAME}` Logs In Resource Group `${AZ_RESOURCE_GROUP}`
- Check Configuration Health of App Service `${APP_SERVICE_NAME}` In Resource Group `${AZ_RESOURCE_GROUP}`
- Check Deployment Health of App Service `${APP_SERVICE_NAME}` In Resource Group `${AZ_RESOURCE_GROUP}`
- Fetch App Service `${APP_SERVICE_NAME}` Activities In Resource Group `${AZ_RESOURCE_GROUP}`
- Check Logs for Errors in App Service `${APP_SERVICE_NAME}` In Resource Group `${AZ_RESOURCE_GROUP}`



## k8s-pvc-healthcheck


- Fetch Events for Unhealthy Kubernetes PersistentVolumeClaims in Namespace `${NAMESPACE}`
- List PersistentVolumeClaims in Terminating State in Namespace `${NAMESPACE}`
- List PersistentVolumes in Terminating State in Namespace `${NAMESPACE}`
- List Pods with Attached Volumes and Related PersistentVolume Details in Namespace `${NAMESPACE}`
- Fetch the Storage Utilization for PVC Mounts in Namespace `${NAMESPACE}`
- Check for RWO Persistent Volume Node Attachment Issues in Namespace `${NAMESPACE}`



## k8s-chaos-workload


- Test `${WORKLOAD_NAME}` High Availability
- OOMKill `${WORKLOAD_NAME}` Pod
- Mangle Service Selector For `${WORKLOAD_NAME}`
- Mangle Service Port For `${WORKLOAD_NAME}`
- Fill Tmp Directory Of Pod From `${WORKLOAD_NAME}`



## curl-gmp-nginx-ingress-inspection


- Fetch Nginx HTTP Errors From GMP for Ingress `${INGRESS_OBJECT_NAME}`
- Find Owner and Service Health for Ingress `${INGRESS_OBJECT_NAME}`



## curl-http-ok


- Checking HTTP URL Is Available And Timely



## k8s-prometheus-healthcheck


- Check Prometheus Service Monitors
- Check For Successful Rule Setup
- Verify Prometheus RBAC Can Access ServiceMonitors
- Identify Endpoint Scraping Errors
- Check Prometheus API Healthy



## k8s-artifactory-health


- Check Artifactory Liveness and Readiness Endpoints



## k8s-fluxcd-kustomization-health


- List all available Kustomization objects in Namespace `${NAMESPACE}`
- Get details for unready Kustomizations in Namespace `${NAMESPACE}`



## azure-vmss-triage


- Check Scale Set `${VMSCALESET}` Key Metrics In Resource Group `${AZ_RESOURCE_GROUP}`
- Fetch VM Scale Set `${VMSCALESET}` Config In Resource Group `${AZ_RESOURCE_GROUP}`
- Fetch Activities for VM Scale Set `${VMSCALESET}` In Resource Group `${AZ_RESOURCE_GROUP}`



## test-issue


- Raise Full Issue



## k8s-tail-logs-dynamic


- Get `${CONTAINER_NAME}` Application Logs
- Tail `${CONTAINER_NAME}` Application Logs For Stacktraces



## k8s-jaeger-http-query


- Query Traces in Jaeger for Unhealthy HTTP Response Codes in Namespace `${NAMESPACE}`



## cli-test


- Run CLI and Parse Output For Issues
- Exec Test
- Local Process Test



## k8s-restart-resource


- Get Current Resource State with Labels `${LABELS}`
- Get Resource Logs with Labels `${LABELS}`
- Restart Resource with Labels `${LABELS}`



## k8s-argocd-application-health


- Fetch ArgoCD Application Sync Status & Health for `${APPLICATION}`
- Fetch ArgoCD Application Last Sync Operation Details for `${APPLICATION}`
- Fetch Unhealthy ArgoCD Application Resources for `${APPLICATION}`
- Scan For Errors in Pod Logs Related to ArgoCD Application `${APPLICATION}`
- Fully Describe ArgoCD Application `${APPLICATION}`



## aws-eks-health


- Check EKS Fargate Cluster Health Status
- Check EKS Cluster Health Status
- List EKS Cluster Metrics



## k8s-daemonset-healthcheck


- Get DaemonSet Logs for `${DAEMONSET_NAME}` and Add to Report
- Get Related Daemonset `${DAEMONSET_NAME}` Events
- Check Daemonset `${DAEMONSET_NAME}` Replicas



## gcp-cloud-function-health


- List Unhealhy Cloud Functions in GCP Project `${GCP_PROJECT_ID}`
- Get Error Logs for Unhealthy Cloud Functions in GCP Project `${GCP_PROJECT_ID}`



## aws-elasticache-redis-health


- Scan AWS Elasticache Redis Status



## k8s-ingress-healthcheck


- Fetch Ingress Object Health in Namespace `${NAMESPACE}`
- Check for Ingress and Service Conflicts in Namespace `${NAMESPACE}`



## k8s-loki-healthcheck


- Check Loki Ring API
- Check Loki API Ready



## k8s-cluster-resource-health


- Identify High Utilization Nodes for Cluster `${CONTEXT}`
- Identify Pods Causing High Node Utilization in Cluster `${CONTEXT}`



## k8s-vault-healthcheck


- Fetch Vault CSI Driver Logs
- Get Vault CSI Driver Warning Events
- Check Vault CSI Driver Replicas
- Fetch Vault Logs
- Get Related Vault Events
- Fetch Vault StatefulSet Manifest Details
- Fetch Vault DaemonSet Manifest Details
- Verify Vault Availability
- Check Vault StatefulSet Replicas



## curl-gmp-kong-ingress-inspection


- Check If Kong Ingress HTTP Error Rate Violates HTTP Error Threshold
- Check If Kong Ingress HTTP Request Latency Violates Threshold
- Check If Kong Ingress Controller Reports Upstream Errors



## azure-aks-triage


- Check for Resource Health Issues Affecting AKS Cluster `${AKS_CLUSTER}` In Resource Group `${AZ_RESOURCE_GROUP}`
- Check Configuration Health of AKS Cluster `${AKS_CLUSTER}` In Resource Group `${AZ_RESOURCE_GROUP}`
- Check Network Configuration of AKS Cluster `${AKS_CLUSTER}` In Resource Group `${AZ_RESOURCE_GROUP}`
- Fetch Activities for AKS Cluster `${AKS_CLUSTER}` In Resource Group `${AZ_RESOURCE_GROUP}`



## k8s-namespace-healthcheck


- Inspect Warning Events in Namespace `${NAMESPACE}`
- Inspect Container Restarts In Namespace `${NAMESPACE}`
- Inspect Pending Pods In Namespace `${NAMESPACE}`
- Inspect Failed Pods In Namespace `${NAMESPACE}`
- Inspect Workload Status Conditions In Namespace `${NAMESPACE}`
- Get Listing Of Resources In Namespace `${NAMESPACE}`
- Check Event Anomalies in Namespace `${NAMESPACE}`
- Check Missing or Risky PodDisruptionBudget Policies in Namepace `${NAMESPACE}`
- Check Resource Quota Utilization in Namespace `${NAMESPACE}`



## azure-loadbalancer-triage


- Check Activity Logs for Azure Load Balancer `${AZ_LB_NAME}`



## k8s-ingress-gce-healthcheck


- Search For GCE Ingress Warnings in GKE
- Identify Unhealthy GCE HTTP Ingress Backends
- Validate GCP HTTP Load Balancer Configurations
- Fetch Network Error Logs from GCP Operations Manager for Ingress Backends
- Review GCP Operations Logging Dashboard



## aws-eks-node-reboot


- Check EKS Nodegroup Status



## azure-acr-image-sync


- Sync Container Images into Azure Container Registry `${ACR_REGISTRY}`



## k8s-fluxcd-helm-health


- List all available FluxCD Helmreleases in Namespace `${NAMESPACE}`
- Fetch Installed FluxCD Helmrelease Versions in Namespace `${NAMESPACE}`
- Fetch Mismatched FluxCD HelmRelease Version in Namespace `${NAMESPACE}`
- Fetch FluxCD HelmRelease Error Messages in Namespace `${NAMESPACE}`
- Check for Available Helm Chart Updates in Namespace `${NAMESPACE}`



## k8s-certmanager-healthcheck


- Get Namespace Certificate Summary for Namespace `${NAMESPACE}`
- Find Unhealthy Certificates in Namespace `${NAMESPACE}`
- Find Failed Certificate Requests and Identify Issues for Namespace `${NAMESPACE}`



## k8s-otelcollector


- Query Collector Queued Spans in Namespace `${NAMESPACE}`
- Check OpenTelemetry Collector Logs For Errors In Namespace `${NAMESPACE}`
- Scan OpenTelemetry Logs For Dropped Spans In Namespace `${NAMESPACE}`



## k8s-postgres-healthcheck


- List Resources Related to Postgres Cluster `${OBJECT_NAME}` in Namespace `${NAMESPACE}`
- Get Postgres Pod Logs & Events for Cluster `${OBJECT_NAME}` in Namespace `${NAMESPACE}`
- Get Postgres Pod Resource Utilization for Cluster `${OBJECT_NAME}` in Namespace `${NAMESPACE}`
- Get Running Postgres Configuration for Cluster `${OBJECT_NAME}` in Namespace `${NAMESPACE}`
- Get Patroni Output and Add to Report for Cluster `${OBJECT_NAME}` in Namespace `${NAMESPACE}`
- Fetch Patroni Database Lag for Cluster `${OBJECT_NAME}` in Namespace `${NAMESPACE}`
- Check Database Backup Status for Cluster `${OBJECT_NAME}` in Namespace `${NAMESPACE}`
- Run DB Queries for Cluster `${OBJECT_NAME}` in Namespace `${NAMESPACE}`



## k8s-kubectl-cmd


- Run User Provided Kubectl Command



## aws-s3-bucket-storage-report


- Check AWS S3 Bucket Storage Utilization



## k8s-chaos-flux


- Suspend the Flux Resource Reconciliation
- Find Random FluxCD Workload as Chaos Target
- Execute Chaos Command
- Execute Additional Chaos Command
- Resume Flux Resource Reconciliation



## k8s-image-check


- Check Image Rollover Times for Namespace `${NAMESPACE}`
- List Images and Tags for Every Container in Running Pods for Namespace `${NAMESPACE}`
- List Images and Tags for Every Container in Failed Pods for Namespace `${NAMESPACE}`
- List ImagePullBackOff Events and Test Path and Tags for Namespace `${NAMESPACE}`



## gcloud-stdout-issue


- ${TASK_TITLE}



## azure-stdout-issue


- ${TASK_TITLE}



## curl-stdout-issue


- ${TASK_TITLE}



## curl-cmd


- ${TASK_TITLE}



## aws-stdout-issue


- ${TASK_TITLE}



## azure-cmd


- ${TASK_TITLE}



## k8s-stdout-issue


- ${TASK_TITLE}



## gcloud-cmd


- ${TASK_TITLE}



## aws-cmd


- ${TASK_TITLE}



## k8s-kubectl-cmd


- ${TASK_TITLE}



## azure-rw-acr-helm-update


- Apply Available RunWhen Helm Images in ACR Registry`${REGISTRY_NAME}`



## pagerduty-webhook-handler


- Run SLX Tasks with matching PagerDuty Webhook Service ID



## azure-rw-acr-sync


- Sync CodeCollection Images to ACR Registry `${REGISTRY_NAME}`
- Sync RunWhen Local Image Updates to ACR Registry`${REGISTRY_NAME}`



## alertmanager-webbook-handler


- Run SLX Tasks with matching AlertManager Webhook commonLabels



## rds-mysql-conn-count


- Run Bash File



## aws-c7n-network-health


- List Publicly Accessible Security Groups in AWS account `${AWS_ACCOUNT_ID}`
- List unused Elastic IPs in AWS account `${AWS_ACCOUNT_ID}`
- List unused ELBs in AWS account `${AWS_ACCOUNT_ID}`
- List VPCs with Flow Logs Disabled in AWS account `${AWS_ACCOUNT_ID}`



## aws-c7n-ec2-health


- List stale AWS EC2 instances in AWS Region `${AWS_REGION}` in AWS account `${AWS_ACCOUNT_ID}`
- List stopped AWS EC2 instances in AWS Region `${AWS_REGION}` in AWS account `${AWS_ACCOUNT_ID}`
- List invalid AWS Auto Scaling Groups in AWS Region ${AWS_REGION} in AWS account ${AWS_ACCOUNT_ID}



## aws-c7n-monitoring-health


- List CloudWatch Log Groups Without Retention Period in AWS Region `${AWS_REGION}` in AWS Account `${AWS_ACCOUNT_ID}`
- Check CloudTrail Configuration in AWS Region `${AWS_REGION}` in AWS Account `${AWS_ACCOUNT_ID}`
-  Check for CloudTrail integration with CloudWatch Logs in AWS Region `${AWS_REGION}` in AWS Account `${AWS_ACCOUNT_ID}`



## aws-c7n-s3-health


- List S3 Buckets With Public Access in AWS Account `${AWS_ACCOUNT_NAME}`



## aws-c7n-rds-health


- List Unencrypted RDS Instances in AWS Region `${AWS_REGION}` in AWS Account `${AWS_ACCOUNT_ID}`
- List Publicly Accessible RDS Instances in AWS Region `${AWS_REGION}` in AWS Account `${AWS_ACCOUNT_ID}`
- List RDS Instances with Backups Disabled in AWS Region `${AWS_REGION}` in AWS Account `${AWS_ACCOUNT_ID}`



## aws-c7n-ebs-health


- List Unattached EBS Volumes in AWS Region `${AWS_REGION}` in AWS account `${AWS_ACCOUNT_ID}`
- List Unencrypted EBS Volumes in AWS Region `${AWS_REGION}` in AWS account `${AWS_ACCOUNT_ID}`
- List Unused EBS Snapshots in AWS Region `${AWS_REGION}` in AWS account `${AWS_ACCOUNT_ID}`


