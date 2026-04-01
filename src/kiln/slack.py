from __future__ import annotations

import json
import os
import subprocess
import urllib.request

DEFAULT_CHANNEL_ID = "C0AN6F2MUAH"


def send_slack_message(message: str) -> None:
    webhook = os.environ.get("KILN_SLACK_WEBHOOK_URL")
    if webhook:
        request = urllib.request.Request(
            webhook,
            data=json.dumps({"text": message}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=15):
            return

    prompt = (
        "Send the following status report to Slack channel "
        f"{DEFAULT_CHANNEL_ID} exactly as plain text:\n\n{message}"
    )
    subprocess.run(
        ["claude", "--print", prompt],
        check=True,
        text=True,
        capture_output=True,
        timeout=30,
    )
