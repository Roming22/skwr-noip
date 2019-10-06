#!/bin/bash

PROJECT_DIR=$(cd $(dirname $0)/..; pwd)

RESPONSE=$(cat /tmp/response.txt)
[[ "$RESPONSE" =~ ^(good|nochg) ]] || exit 1
