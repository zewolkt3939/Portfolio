#!/bin/sh
set -eu

if [ "$(id -u)" -ne 0 ]; then
  echo "Run this script with sudo." >&2
  exit 1
fi

. /etc/os-release
if [ "${ID:-}" != "ubuntu" ]; then
  echo "This bootstrap script supports Ubuntu only." >&2
  exit 1
fi

deploy_user=${SUDO_USER:-ubuntu}
if ! id "$deploy_user" >/dev/null 2>&1; then
  echo "Deployment user $deploy_user does not exist." >&2
  exit 1
fi

apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y ca-certificates curl git unattended-upgrades
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc

architecture=$(dpkg --print-architecture)
codename=${UBUNTU_CODENAME:-$VERSION_CODENAME}
printf '%s\n' "deb [arch=$architecture signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $codename stable" > /etc/apt/sources.list.d/docker.list

apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
systemctl enable --now docker
usermod -aG docker "$deploy_user"

if [ ! -f /swapfile ]; then
  fallocate -l 2G /swapfile
  chmod 600 /swapfile
  mkswap /swapfile
fi
if ! swapon --show=NAME --noheadings | grep -qx '/swapfile'; then
  swapon /swapfile
fi
if ! grep -q '^/swapfile ' /etc/fstab; then
  printf '%s\n' '/swapfile none swap sw 0 0' >> /etc/fstab
fi
printf '%s\n' 'vm.swappiness=10' > /etc/sysctl.d/99-portfolio-swap.conf
sysctl --system >/dev/null

install -d -o "$deploy_user" -g "$deploy_user" /srv/portfolio

echo "Docker and a 2 GiB emergency swap file are ready."
echo "Sign out and sign in again before running Docker without sudo."

