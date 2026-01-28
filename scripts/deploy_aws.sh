#!/bin/bash
# =============================================================================
# MarketScout - AWS Deployment Script
# =============================================================================
# This script deploys MarketScout to AWS using ECS (Elastic Container Service)
#
# Prerequisites:
# - AWS CLI configured with appropriate credentials
# - Docker installed and running
# - ECR repository created
#
# Usage:
#   ./scripts/deploy_aws.sh [environment]
#   
# Environments: dev, staging, prod (default: dev)
# =============================================================================

set -e

# Configuration
ENVIRONMENT=${1:-dev}
AWS_REGION=${AWS_REGION:-us-east-1}
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_REGISTRY="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
APP_NAME="marketscout"
IMAGE_TAG="${ENVIRONMENT}-$(git rev-parse --short HEAD 2>/dev/null || echo 'latest')"

# ECS Configuration
ECS_CLUSTER="${APP_NAME}-${ENVIRONMENT}"
ECS_SERVICE="${APP_NAME}-${ENVIRONMENT}-service"
ECS_TASK_FAMILY="${APP_NAME}-${ENVIRONMENT}"

echo "=============================================="
echo "  MarketScout AWS Deployment"
echo "=============================================="
echo "  Environment:  ${ENVIRONMENT}"
echo "  AWS Region:   ${AWS_REGION}"
echo "  Image Tag:    ${IMAGE_TAG}"
echo "=============================================="

# Step 1: Build Docker images
echo ""
echo "[1/6] Building Docker images..."

docker build -t ${APP_NAME}-python:${IMAGE_TAG} -f docker/Dockerfile.python .
docker build -t ${APP_NAME}-cpp:${IMAGE_TAG} -f docker/Dockerfile.cpp .

echo "✓ Docker images built successfully"

# Step 2: Login to ECR
echo ""
echo "[2/6] Logging into Amazon ECR..."

aws ecr get-login-password --region ${AWS_REGION} | \
    docker login --username AWS --password-stdin ${ECR_REGISTRY}

echo "✓ ECR login successful"

# Step 3: Create ECR repositories if they don't exist
echo ""
echo "[3/6] Ensuring ECR repositories exist..."

for repo in "${APP_NAME}-python" "${APP_NAME}-cpp"; do
    aws ecr describe-repositories --repository-names ${repo} --region ${AWS_REGION} 2>/dev/null || \
    aws ecr create-repository --repository-name ${repo} --region ${AWS_REGION}
done

echo "✓ ECR repositories ready"

# Step 4: Tag and push images
echo ""
echo "[4/6] Pushing images to ECR..."

docker tag ${APP_NAME}-python:${IMAGE_TAG} ${ECR_REGISTRY}/${APP_NAME}-python:${IMAGE_TAG}
docker tag ${APP_NAME}-python:${IMAGE_TAG} ${ECR_REGISTRY}/${APP_NAME}-python:latest
docker push ${ECR_REGISTRY}/${APP_NAME}-python:${IMAGE_TAG}
docker push ${ECR_REGISTRY}/${APP_NAME}-python:latest

docker tag ${APP_NAME}-cpp:${IMAGE_TAG} ${ECR_REGISTRY}/${APP_NAME}-cpp:${IMAGE_TAG}
docker tag ${APP_NAME}-cpp:${IMAGE_TAG} ${ECR_REGISTRY}/${APP_NAME}-cpp:latest
docker push ${ECR_REGISTRY}/${APP_NAME}-cpp:${IMAGE_TAG}
docker push ${ECR_REGISTRY}/${APP_NAME}-cpp:latest

echo "✓ Images pushed to ECR"

# Step 5: Update ECS task definition
echo ""
echo "[5/6] Updating ECS task definition..."

# Generate task definition JSON
cat > /tmp/task-definition.json << EOF
{
  "family": "${ECS_TASK_FAMILY}",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "512",
  "memory": "1024",
  "executionRoleArn": "arn:aws:iam::${AWS_ACCOUNT_ID}:role/ecsTaskExecutionRole",
  "containerDefinitions": [
    {
      "name": "app",
      "image": "${ECR_REGISTRY}/${APP_NAME}-python:${IMAGE_TAG}",
      "essential": true,
      "portMappings": [
        {
          "containerPort": 8000,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {"name": "MODE", "value": "simulation"},
        {"name": "WEB_HOST", "value": "0.0.0.0"},
        {"name": "WEB_PORT", "value": "8000"}
      ],
      "secrets": [
        {
          "name": "JWT_SECRET",
          "valueFrom": "arn:aws:secretsmanager:${AWS_REGION}:${AWS_ACCOUNT_ID}:secret:${APP_NAME}/${ENVIRONMENT}/jwt-secret"
        },
        {
          "name": "DATABASE_URL",
          "valueFrom": "arn:aws:secretsmanager:${AWS_REGION}:${AWS_ACCOUNT_ID}:secret:${APP_NAME}/${ENVIRONMENT}/database-url"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/${APP_NAME}-${ENVIRONMENT}",
          "awslogs-region": "${AWS_REGION}",
          "awslogs-stream-prefix": "app"
        }
      },
      "healthCheck": {
        "command": ["CMD-SHELL", "curl -f http://localhost:8000/api/health || exit 1"],
        "interval": 30,
        "timeout": 10,
        "retries": 3,
        "startPeriod": 60
      }
    }
  ]
}
EOF

# Register new task definition
TASK_REVISION=$(aws ecs register-task-definition \
    --cli-input-json file:///tmp/task-definition.json \
    --region ${AWS_REGION} \
    --query 'taskDefinition.revision' \
    --output text)

echo "✓ Task definition registered (revision: ${TASK_REVISION})"

# Step 6: Update ECS service
echo ""
echo "[6/6] Updating ECS service..."

# Check if service exists
SERVICE_EXISTS=$(aws ecs describe-services \
    --cluster ${ECS_CLUSTER} \
    --services ${ECS_SERVICE} \
    --region ${AWS_REGION} \
    --query 'services[0].status' \
    --output text 2>/dev/null || echo "MISSING")

if [ "$SERVICE_EXISTS" == "MISSING" ] || [ "$SERVICE_EXISTS" == "None" ]; then
    echo "Service doesn't exist, skipping update."
    echo "Create the ECS service manually or use CloudFormation/Terraform."
else
    aws ecs update-service \
        --cluster ${ECS_CLUSTER} \
        --service ${ECS_SERVICE} \
        --task-definition ${ECS_TASK_FAMILY}:${TASK_REVISION} \
        --force-new-deployment \
        --region ${AWS_REGION} \
        > /dev/null

    echo "✓ ECS service updated"
    
    # Wait for deployment
    echo ""
    echo "Waiting for deployment to stabilize..."
    aws ecs wait services-stable \
        --cluster ${ECS_CLUSTER} \
        --services ${ECS_SERVICE} \
        --region ${AWS_REGION}
    
    echo "✓ Deployment complete!"
fi

# Cleanup
rm -f /tmp/task-definition.json

echo ""
echo "=============================================="
echo "  Deployment Summary"
echo "=============================================="
echo "  Environment:  ${ENVIRONMENT}"
echo "  Image Tag:    ${IMAGE_TAG}"
echo "  Task Rev:     ${TASK_REVISION}"
echo "=============================================="
echo ""
echo "To check status:"
echo "  aws ecs describe-services --cluster ${ECS_CLUSTER} --services ${ECS_SERVICE}"
echo ""
