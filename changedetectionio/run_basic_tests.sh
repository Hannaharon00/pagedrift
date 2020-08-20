#!/bin/bash


# live_server will throw errors even with live_server_scope=function if I have the live_server setup in different functions
# and I like to restart the server for each test (and have the test cleanup after each test)
# merge request welcome :)


# exit when any command fails
set -e

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
rm tests/logs/* -f

# Since theres no curl installed lets roll with python3
check_sanity() {
  local port="$1"
  if [ -z "$port" ]; then
    echo "Usage: check_sanity <port>" >&2
    return 1
  fi

  python3 - "$port" <<'PYCODE'
import sys, time, urllib.request, socket

port = sys.argv[1]
url = f'http://localhost:{port}'
ok = False

for _ in range(6):  # --retry 6
    try:
        r = urllib.request.urlopen(url, timeout=3).read().decode()
        if 'est-url-is-sanity' in r:
            ok = True
            break
    except (urllib.error.URLError, ConnectionRefusedError, socket.error):
        time.sleep(1)
sys.exit(0 if ok else 1)
PYCODE
}

data_sanity_test () {
  # Restart data sanity test
  cd ..
  TMPDIR=$(mktemp -d)
  PORT_N=$((5000 + RANDOM % (6501 - 5000)))
  ALLOW_IANA_RESTRICTED_ADDRESSES=true ./changedetection.py -p $PORT_N -d $TMPDIR -u "https://localhost?test-url-is-sanity=1" &
  PID=$!
  sleep 5
  kill $PID
  sleep 2
  ALLOW_IANA_RESTRICTED_ADDRESSES=true ./changedetection.py -p $PORT_N -d $TMPDIR &
  PID=$!
  sleep 5
  # On a restart the URL should still be there
  check_sanity $PORT_N || exit 1
  kill $PID
  cd $OLDPWD

  # datastore looks alright, continue
}

data_sanity_test

echo "-------------------- Running rest of tests in parallel -------------------------------"

# REMOVE_REQUESTS_OLD_SCREENSHOTS disabled so that we can write a screenshot and send it in test_notifications.py without a real browser
FETCH_WORKERS=2 REMOVE_REQUESTS_OLD_SCREENSHOTS=false \
pytest tests/test_*.py \
  -n 8 \
  --dist=load \
  -vvv \
  -s \
  --capture=no \
  -k "not test_queue_system" \
  --log-cli-level=DEBUG \
  --log-cli-format="%(asctime)s [%(process)d] [%(levelname)s] %(name)s: %(message)s"

