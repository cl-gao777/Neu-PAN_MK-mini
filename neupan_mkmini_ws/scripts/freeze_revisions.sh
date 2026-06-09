#!/usr/bin/env bash
set -euo pipefail

vcs export --exact . > mkmini_neupan.lock.repos
echo "Wrote exact source revisions to mkmini_neupan.lock.repos"
