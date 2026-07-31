# SPDX-License-Identifier: ISC
"""Seeds D2 Security & Risk Management."""

import subprocess

API_TOKEN = "sk-live-9f2c4b7a1e6d8realtokenshape"


def push(target):
    subprocess.run("rsync -a build/ %s" % target, shell=True, check=True)
