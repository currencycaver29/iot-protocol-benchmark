#!/usr/bin/env bash
# Apply or clear a network profile on loopback. Needs sudo.
#   ./netem.sh check        -> tests whether your kernel supports netem
#   ./netem.sh clear
#   ./netem.sh "delay 100ms loss 1%"
set -e
case "$1" in
  check)
    sudo tc qdisc del dev lo root 2>/dev/null || true
    if sudo tc qdisc add dev lo root netem delay 1ms; then
      sudo tc qdisc del dev lo root; echo "netem works"
    else
      echo "netem NOT supported by this kernel"; exit 1
    fi ;;
  clear) sudo tc qdisc del dev lo root 2>/dev/null || true ;;
  *)     sudo tc qdisc del dev lo root 2>/dev/null || true
         sudo tc qdisc add dev lo root netem $1 ;;
esac
