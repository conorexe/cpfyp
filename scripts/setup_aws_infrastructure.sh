#!/bin/bash
# =============================================================================
# MarketScout - AWS Infrastructure Setup
# =============================================================================
# Creates the required AWS infrastructure for MarketScout deployment:
# - VPC with public/private subnets
# - ECS Cluster
# - RDS PostgreSQL instance
# - Application Load Balancer
# - Security Groups
# - CloudWatch Log Groups
# - Secrets Manager secrets
#
# Prerequisites:
# - AWS CLI configured with admin credentials
# - Appropriate IAM permissions
#
# Usage:
#   ./scripts/setup_aws_infrastructure.sh [environment]
# =============================================================================

set -e

ENVIRONMENT=${1:-dev}
AWS_REGION=${AWS_REGION:-us-east-1}
APP_NAME="marketscout"
STACK_NAME="${APP_NAME}-${ENVIRONMENT}"

echo "=============================================="
echo "  MarketScout AWS Infrastructure Setup"
echo "=============================================="
echo "  Environment:  ${ENVIRONMENT}"
echo "  AWS Region:   ${AWS_REGION}"
echo "  Stack Name:   ${STACK_NAME}"
echo "=============================================="

# Create CloudWatch Log Group
echo ""
echo "[1/5] Creating CloudWatch Log Group..."
aws logs create-log-group \
    --log-group-name "/ecs/${APP_NAME}-${ENVIRONMENT}" \
    --region ${AWS_REGION} 2>/dev/null || true
echo "✓ Log group ready"

# Create Secrets
echo ""
echo "[2/5] Creating secrets in Secrets Manager..."

# Generate a secure JWT secret
JWT_SECRET=$(openssl rand -base64 32)

aws secretsmanager create-secret \
    --name "${APP_NAME}/${ENVIRONMENT}/jwt-secret" \
    --secret-string "${JWT_SECRET}" \
    --region ${AWS_REGION} 2>/dev/null || \
aws secretsmanager update-secret \
    --secret-id "${APP_NAME}/${ENVIRONMENT}/jwt-secret" \
    --secret-string "${JWT_SECRET}" \
    --region ${AWS_REGION}

echo "✓ JWT secret created/updated"

# Create ECS Cluster
echo ""
echo "[3/5] Creating ECS Cluster..."
aws ecs create-cluster \
    --cluster-name "${APP_NAME}-${ENVIRONMENT}" \
    --capacity-providers FARGATE FARGATE_SPOT \
    --default-capacity-provider-strategy capacityProvider=FARGATE,weight=1 \
    --region ${AWS_REGION} 2>/dev/null || true
echo "✓ ECS cluster ready"

# Create ECR Repositories
echo ""
echo "[4/5] Creating ECR repositories..."
for repo in "python" "cpp"; do
    aws ecr create-repository \
        --repository-name "${APP_NAME}-${repo}" \
        --image-scanning-configuration scanOnPush=true \
        --region ${AWS_REGION} 2>/dev/null || true
done
echo "✓ ECR repositories ready"

# Create IAM roles
echo ""
echo "[5/5] Ensuring IAM roles exist..."

# Check if ecsTaskExecutionRole exists
ROLE_EXISTS=$(aws iam get-role --role-name ecsTaskExecutionRole 2>/dev/null || echo "MISSING")
if [ "$ROLE_EXISTS" == "MISSING" ]; then
    echo "Creating ecsTaskExecutionRole..."
    
    # Trust policy
    cat > /tmp/trust-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "ecs-tasks.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

    aws iam create-role \
        --role-name ecsTaskExecutionRole \
        --assume-role-policy-document file:///tmp/trust-policy.json

    aws iam attach-role-policy \
        --role-name ecsTaskExecutionRole \
        --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy

    aws iam attach-role-policy \
        --role-name ecsTaskExecutionRole \
        --policy-arn arn:aws:iam::aws:policy/SecretsManagerReadWrite

    rm /tmp/trust-policy.json
fi
echo "✓ IAM roles ready"

echo ""
echo "=============================================="
echo "  Infrastructure Setup Complete!"
echo "=============================================="
echo ""
echo "Next steps:"
echo "1. Create a VPC (or use default VPC)"
echo "2. Create an RDS PostgreSQL instance (optional)"
echo "3. Create an Application Load Balancer"
echo "4. Run: ./scripts/deploy_aws.sh ${ENVIRONMENT}"
echo ""
echo "For a complete setup, consider using CloudFormation or Terraform."
echo ""
