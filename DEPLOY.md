# AWS EC2 Deployment Guide

This guide walks through deploying the Room Detection Service to AWS EC2 using Docker.

## Prerequisites

1. AWS Account with EC2 access
2. Model weights file (`maskrcnn_best.pth`)
3. SSH key pair for EC2 access

## Step 1: Launch EC2 Instance

### Recommended Instance Type
- **t3.medium** or **t3.large** for CPU inference (~$30-60/month)
- **g4dn.xlarge** for GPU inference (~$120/month, faster)

### AMI
- Ubuntu Server 22.04 LTS (HVM)

### Security Group Rules
- **SSH (22)**: Your IP address
- **HTTP (80)**: 0.0.0.0/0 (or your IP for testing)
- **HTTPS (443)**: 0.0.0.0/0 (if using SSL)

### Storage
- 30 GB minimum (model file is ~350MB)

## Step 2: Connect to EC2 Instance

```bash
ssh -i your-key.pem ubuntu@your-ec2-public-ip
```

## Step 3: Install Dependencies

Run the automated setup script:

```bash
# Download setup script
wget https://raw.githubusercontent.com/miriamsimone/room-detector/main/scripts/setup-ec2.sh
chmod +x setup-ec2.sh
sudo ./setup-ec2.sh
```

Or install manually:

```bash
# Update system
sudo apt-get update
sudo apt-get upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker ubuntu

# Install Docker Compose
sudo apt-get install -y docker-compose

# Restart session to apply docker group
exit
# SSH back in
```

## Step 4: Clone Repository

```bash
git clone git@github.com:miriamsimone/room-detector.git
cd room-detector
```

## Step 5: Upload Model Weights

From your local machine:

```bash
scp -i your-key.pem maskrcnn_best.pth ubuntu@your-ec2-public-ip:~/room-detector/backend/
```

Or use SCP client, or download from S3:

```bash
# If stored in S3
aws s3 cp s3://your-bucket/maskrcnn_best.pth ~/room-detector/backend/
```

## Step 6: Start Services

```bash
cd ~/room-detector
docker-compose up -d
```

Check status:

```bash
docker-compose ps
docker-compose logs -f
```

## Step 7: Verify Deployment

```bash
# Check health endpoint
curl http://localhost/health

# Should return:
# {"status": "healthy", "model_loaded": true, "device": "cpu"}
```

Visit in browser: `http://your-ec2-public-ip`

## Step 8: (Optional) Configure Domain & SSL

### Point Domain to EC2

1. Add A record in DNS: `your-domain.com -> EC2-IP`
2. Wait for DNS propagation

### Install Certbot for SSL

```bash
sudo apt-get install -y certbot python3-certbot-nginx

# Stop nginx container temporarily
cd ~/room-detector
docker-compose stop nginx

# Get certificate
sudo certbot certonly --standalone -d your-domain.com

# Update nginx config to use SSL
# (Edit nginx/nginx.conf to add SSL server block)

# Restart
docker-compose up -d
```

## Updating the Application

```bash
cd ~/room-detector

# Pull latest changes
git pull

# Rebuild and restart
docker-compose down
docker-compose up -d --build

# Check logs
docker-compose logs -f
```

## Monitoring & Logs

```bash
# View logs
docker-compose logs -f backend
docker-compose logs -f nginx

# Check resource usage
docker stats

# System resources
htop
```

## Troubleshooting

### Model not loading
```bash
# Check model file exists
ls -lh backend/maskrcnn_best.pth

# Check backend logs
docker-compose logs backend
```

### Out of memory
- Upgrade to larger instance type
- Reduce batch size (already set to 1)

### Connection refused
```bash
# Check security group rules
# Verify services running
docker-compose ps
```

## Costs Estimate

- **t3.medium** (2 vCPU, 4GB RAM): ~$30/month
- **t3.large** (2 vCPU, 8GB RAM): ~$60/month
- **g4dn.xlarge** (4 vCPU, 16GB RAM, 1 GPU): ~$120/month
- **Data transfer**: ~$0.09/GB
- **Storage**: ~$0.10/GB-month

## Backup Model File

Store model in S3 for easy access:

```bash
aws s3 cp backend/maskrcnn_best.pth s3://your-bucket/models/
```

## Security Best Practices

1. Use SSH keys only (disable password auth)
2. Restrict SSH to your IP in security group
3. Enable HTTPS/SSL for production
4. Regular security updates: `sudo apt-get update && sudo apt-get upgrade`
5. Consider using AWS Systems Manager Session Manager instead of SSH
6. Set up CloudWatch monitoring
7. Regular backups

## Scaling Considerations

For production with high traffic:
- Use Application Load Balancer
- Auto Scaling Group with multiple EC2 instances
- Consider ECS/Fargate for better orchestration
- Use S3 + CloudFront for frontend
- Cache model in memory (already done)
