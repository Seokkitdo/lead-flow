#!/usr/bin/env bash
# Run once as root on the Ubuntu host with a dedicated deployment PUBLIC key.
set -euo pipefail
if [ "$(id -u)" -ne 0 ] || [ "$#" -ne 1 ]; then
  echo 'Usage as root: bash setup-production-host.sh /path/to/deploy-key.pub' >&2
  exit 2
fi
public_key_file=$(realpath "$1")
ssh-keygen -lf "$public_key_file" > /dev/null
. /etc/os-release
if [ "$ID" != ubuntu ]; then
  echo 'This bootstrap script supports Ubuntu only.' >&2
  exit 2
fi
cloud-init status --wait

if ! command -v docker > /dev/null; then
  apt-get update
  DEBIAN_FRONTEND=noninteractive apt-get install -y ca-certificates curl
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  cat > /etc/apt/sources.list.d/docker.sources <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: ${UBUNTU_CODENAME:-$VERSION_CODENAME}
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF
  apt-get update
  DEBIAN_FRONTEND=noninteractive apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi
docker compose version
systemctl enable --now docker

if ! id leadflow-deploy > /dev/null 2>&1; then
  useradd --create-home --shell /bin/bash leadflow-deploy
fi
usermod -aG docker leadflow-deploy
install -d -m 700 -o leadflow-deploy -g leadflow-deploy \
  /opt/leadflow /opt/leadflow/releases /opt/leadflow/backups \
  /home/leadflow-deploy/.ssh
python3 - "$public_key_file" <<'PY'
import pathlib
import pwd
import os
import sys

key = pathlib.Path(sys.argv[1]).read_text().strip()
if "\n" in key or not key.startswith("ssh-ed25519 "):
    raise SystemExit("Provide exactly one Ed25519 public key.")
target = pathlib.Path("/home/leadflow-deploy/.ssh/authorized_keys")
entry = "restrict " + key
lines = target.read_text().splitlines() if target.exists() else []
if entry not in lines:
    lines.append(entry)
target.write_text("\n".join(lines) + "\n")
user = pwd.getpwnam("leadflow-deploy")
os.chown(target, user.pw_uid, user.pw_gid)
target.chmod(0o600)
PY
echo 'Docker and the leadflow-deploy SSH account are ready. Configure /opt/leadflow/.env before deployment.'
