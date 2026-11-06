#!/bin/bash
# Check the published site after a Mintlify deploy: every navigable page serves the
# sdkVersion in docs.json, and every redirect in docs.json returns 308. Each URL is
# requested several times, because CDN edges can keep an old copy after a deploy.
# Run it about 5 and 15 minutes after the "Mintlify Deployment" check succeeds.
set -uo pipefail
cd "$(dirname "$0")/.."
B=${DOCS_URL:-https://docs.dreamscalelabs.com}
read -r V PAGES REDIRECTS < <(python3 - <<'PY'
import json
c = json.load(open("docs.json"))
def walk(n):
    if isinstance(n, str): return [n]
    if isinstance(n, list): return [p for i in n for p in walk(i)]
    if isinstance(n, dict): return walk(n.get("pages", []))
    return []
pages = ["/" if p == "index" else f"/{p}" for p in walk(c["navigation"])]
print(c["variables"]["sdkVersion"], ",".join(pages), ",".join(r["source"] for r in c["redirects"]))
PY
)
bad=""
for p in ${PAGES//,/ }; do
  for i in 1 2 3; do
    # Pages may name compatibility thresholds ("0.1.0a106 or older", "0.1.0a205+");
    # only a bare version is a release pin.
    v=$(curl --connect-timeout 5 --max-time 20 -s "$B$p" | sed -E 's/0\.1\.0a[0-9]+ or older//g; s/0\.1\.0a[0-9]+\+//g' | grep -o '0\.1\.0a[0-9]*' | sort -u | tr '\n' ' ')
    [ "$v" = "$V " ] || { bad="$bad $p(${v% })"; break; }
  done
done
n=0
for p in ${REDIRECTS//,/ }; do
  n=$((n + 1))
  for i in 1 2 3; do
    c=$(curl --connect-timeout 5 --max-time 20 -s -o /dev/null -w '%{http_code}' "$B$p")
    [ "$c" = 308 ] || { bad="$bad $p[$c]"; break; }
  done
done
if [ -n "$bad" ]; then echo "STALE or wrong:$bad"; exit 1; fi
echo "OK: every page on $V, $n redirects return 308"
