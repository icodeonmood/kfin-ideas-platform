#!/usr/bin/env bash
# Wait for one GitHub Actions run to finish. This is the only way lanes wait for CI (crunch rule 11): one check every
# 120 seconds, one waiter per run, and no `gh run watch` or loops of your own.
#
#   scripts/ci-wait.sh <run-id>
#
# Prints a line when the run's status changes, then the result. Exits 0 if the run concluded success, 1 for any other
# conclusion or a run that can't be read, and 2 for bad usage. "API rate limit exceeded", network errors and GitHub's
# own 5xx answers are waits, not failures: the script checks again 120 seconds later.
set -u

if [ "$#" -ne 1 ] || ! [[ "$1" =~ ^[0-9]+$ ]]; then
  echo "usage: scripts/ci-wait.sh <run-id>" >&2
  exit 2
fi
id="$1"
interval=120
retryable='rate limit|HTTP 429|HTTP 50[0-9]|error connecting|dial tcp|no such host|could not resolve|i/o timeout|timed out|timeout|connection (reset|refused)|TLS handshake|unexpected EOF|context deadline|network is unreachable|ENOTFOUND|ECONNRESET'

last=""
while :; do
  # The shell's GITHUB_TOKEN may be stale; gh's keyring login is the one that works.
  if out=$(env -u GITHUB_TOKEN gh run view "$id" --json status,conclusion --jq '"\(.status) \(.conclusion)"' 2>&1); then
    status="${out%% *}"
    conclusion="${out#* }"
    if [ "$status" = "completed" ]; then
      echo "$(date +%H:%M:%S) run $id completed: ${conclusion:-unknown}"
      [ "$conclusion" = "success" ] && exit 0
      exit 1
    fi
    if [ "$status" != "$last" ]; then
      echo "$(date +%H:%M:%S) run $id $status"
      last="$status"
    fi
  elif printf '%s' "$out" | grep -Eiq "$retryable"; then
    echo "$(date +%H:%M:%S) run $id: GitHub didn't answer ($(printf '%s' "$out" | head -1 | cut -c1-120)); checking again in ${interval}s"
  else
    echo "$(date +%H:%M:%S) run $id can't be read: $(printf '%s' "$out" | head -1 | cut -c1-200)" >&2
    exit 1
  fi
  sleep "$interval"
done
