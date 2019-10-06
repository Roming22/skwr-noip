#!/bin/bash

PROJECT_DIR=$(cd $(dirname $0)/..; pwd)

if [[ -z "$NOIP_EMAIL" || -z "$NOIP_PASSWORD" || -z "$NOIP_DOMAINS" ]]; then
	echo "[ERROR] Configuration is incorrect.
run `configure.sh` on the module.
"
	# Prevent the service to crash and loop continuously
	sleep 300
	exit 1
fi

# Default interval of 1h
INTERVAL=${INTERVAL:-1h}

if [[ ! "$INTERVAL" =~ ^[0-9]+[mhd]$ ]]; then
	echo "Incorrect INTERVAL: '$INTERVAL'. It must be a number followed by m, h, or d. E.g: 1h"
	exit 1
fi

UNIT="${INTERVAL: -1}"
TIME="${INTERVAL:0:-1}"
case "$UNIT" in
	m) MULTIPLIER=60 ;;
	h) MULTIPLIER=3600 ;;
	d) MULTIPLIER=86400 ;;
esac
INTERVAL=$(( ${TIME}*${MULTIPLIER} ))

if [[ "${INTERVAL}" -lt 300 ]]; then
	echo "The shortest allowed INTERVAL is 5 minutes"
	exit 1
fi

USER_AGENT="rpi docker no-ip/.1 $NOIP_EMAIL"

#-----------------------------------------------------------------------------------------------------------------------

function log {
  MESSAGE="$*"
  [[ ! -z "$TIMESTAMP" ]] && MESSAGE="[`date '+%b %d %X'`] $MESSAGE"
  echo "$MESSAGE"
}

#-----------------------------------------------------------------------------------------------------------------------
# Let SKWR know that the container is up and running
echo "[`hostname -s`] Started"
while true; do
	RESPONSE=$(curl -S -s -k --user-agent "${USER_AGENT}" -u "${NOIP_EMAIL}:${NOIP_PASSWORD}" "https://dynupdate.no-ip.com/nic/update?hostname=${NOIP_DOMAINS}" 2>&1 | tr -d [:cntrl:])
	# Used by the healthcheck
	rm $RESPONSE_FILE 2>/dev/null
	echo "$RESPONSE" > $RESPONSE_FILE

	# Sometimes the API returns "nochg" without a space and ip address. It does this even if the password is incorrect.
	if [[ $RESPONSE =~ ^(good|nochg) ]]; then
		log "No-IP successfully called. Result was \"$RESPONSE\"."
		NOW=$(date +%s)
		sleep $((INTERVAL - (NOW % INTERVAL) ))
	elif [[ $RESPONSE =~ ^(nohost|badauth|badagent|abuse|!donator) ]]; then
		log "Something went wrong. Check your settings. Result was \"$RESPONSE\"."
		log "For an explanation of error codes, see http://www.noip.com/integrate/response"
		exit 2
	elif [[ $RESPONSE =~ ^911 ]]; then
		log "Server returned "911". Waiting for 30 minutes before trying again."
		sleep 30m
		continue
	else
		log "Couldn't update. Trying again in 5 minutes. Output from curl command was \"$RESPONSE\"."
		sleep 5m
  	fi
done
