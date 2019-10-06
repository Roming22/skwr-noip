#!/bin/bash -e
SCRIPT_DIR="$(dirname "$(realpath "$0")")"
SRC_DIR="${SCRIPT_DIR}/k8s"
for MANIFEST in configmaps.yml.secret secrets.yml.secret cronjob.yml; do\
    kubectl apply -f "${SRC_DIR}/${MANIFEST}"
done
# kubectl create job "no-ip-manual-$(date +%s)" --namespace kube-system --from cronjob/no-ip