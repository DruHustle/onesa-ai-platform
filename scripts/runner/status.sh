#!/bin/bash
set -euo pipefail
limactl list onesa-portal-ci
limactl shell onesa-portal-ci -- sudo systemctl status actions.runner.DruHustle-onesa-ai-platform.onesa-platform-local-arm64.service --no-pager
gh api repos/DruHustle/onesa-ai-platform/actions/runners --jq '.runners[] | {name,status,busy,labels:[.labels[].name]}'
limactl shell onesa-portal-ci -- sudo sh -c 'df -h /; docker system df; test ! -f /var/lib/onesa-ci/lease.json || cat /var/lib/onesa-ci/lease.json'
