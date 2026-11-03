#!/usr/bin/env bash
# One-time setup on Ubuntu / WSL. Run:  bash setup.sh
set -e
sudo apt-get update
sudo apt-get install -y python3 python3-venv python3-pip mosquitto iproute2 iptables
sudo service mosquitto stop 2>/dev/null || true     # we start our own broker on port 1884
python3 -m venv .venv
. .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
chmod +x netem.sh
if ./netem.sh check; then
  echo "Using tc netem for network emulation."
else
  echo "netem unavailable - installing the NFQUEUE fallback emulator (emulator.py)."
  sudo apt-get install -y libnetfilter-queue-dev build-essential
  pip install NetfilterQueue
fi
echo "Setup done. Next:  source .venv/bin/activate && sudo -E env PATH=\$PATH python run_all.py baseline"
