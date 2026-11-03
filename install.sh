#!/bin/sh
# Link this skill into Claude Code so it is available in every project.
set -e
ROOT=$(cd "$(dirname "$0")" && pwd)
TARGET="${CLAUDE_HOME:-$HOME/.claude}/skills"
LINK="$TARGET/brand-video-studio"
mkdir -p "$TARGET"
if [ -e "$LINK" ] && [ ! -L "$LINK" ]; then
  echo "$LINK already exists and is not a link. Move it away and run this again." >&2
  exit 1
fi
ln -sfn "$ROOT/skill" "$LINK"
echo "Installed: $LINK -> $ROOT/skill"
python3 "$ROOT/skill/scripts/doctor.py" || echo "Install what is marked MISS above before making videos."
