#!/bin/bash
set -e

echo "=================================="
echo "Room Detection Service - EC2 Setup"
echo "=================================="
echo ""

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root (use sudo)"
   exit 1
fi

echo "Step 1: Updating system packages..."
apt-get update
apt-get upgrade -y

echo ""
echo "Step 2: Installing Docker..."
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
    rm get-docker.sh
    usermod -aG docker ubuntu
    echo "Docker installed successfully"
else
    echo "Docker already installed"
fi

echo ""
echo "Step 3: Installing Docker Compose..."
if ! command -v docker-compose &> /dev/null; then
    apt-get install -y docker-compose
    echo "Docker Compose installed successfully"
else
    echo "Docker Compose already installed"
fi

echo ""
echo "Step 4: Installing useful tools..."
apt-get install -y git curl wget htop

echo ""
echo "Step 5: Configuring system..."
# Increase file watchers for better performance
sysctl -w fs.inotify.max_user_watches=524288
echo "fs.inotify.max_user_watches=524288" >> /etc/sysctl.conf

# Optimize for ML workloads
sysctl -w vm.swappiness=10
echo "vm.swappiness=10" >> /etc/sysctl.conf

echo ""
echo "Step 6: Setting up firewall..."
if command -v ufw &> /dev/null; then
    ufw allow 22/tcp
    ufw allow 80/tcp
    ufw allow 443/tcp
    echo "y" | ufw enable
    echo "Firewall configured"
else
    echo "UFW not found, skipping firewall setup (use AWS Security Groups)"
fi

echo ""
echo "=================================="
echo "Setup Complete!"
echo "=================================="
echo ""
echo "Next steps:"
echo "1. Logout and login again (or run: newgrp docker)"
echo "2. Clone repository: git clone git@github.com:miriamsimone/room-detector.git"
echo "3. Upload model weights to backend/maskrcnn_best.pth"
echo "4. Run: docker-compose up -d"
echo ""
echo "See DEPLOY.md for detailed instructions"
