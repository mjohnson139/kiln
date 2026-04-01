#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "$0")/.." && pwd)"
python_cmd="${PYTHON_CMD:-python3}"
tmpfile="$(mktemp)"

tick_line="* * * * * cd ${repo_root} && PYTHONPATH=src ${python_cmd} -m kiln.cli tick >> /tmp/kiln-tick.log 2>&1"
report_line="*/15 * * * * cd ${repo_root} && PYTHONPATH=src ${python_cmd} -m kiln.cli report --slack >> /tmp/kiln-report.log 2>&1"

crontab -l > "${tmpfile}" 2>/dev/null || true
grep -F -v "${repo_root} && PYTHONPATH=src ${python_cmd} -m kiln.cli tick" "${tmpfile}" | \
  grep -F -v "${repo_root} && PYTHONPATH=src ${python_cmd} -m kiln.cli report --slack" > "${tmpfile}.next" || true
printf "%s\n%s\n" "${tick_line}" "${report_line}" >> "${tmpfile}.next"
crontab "${tmpfile}.next"
rm -f "${tmpfile}" "${tmpfile}.next"
printf "Installed cron entries for kiln in %s\n" "${repo_root}"
