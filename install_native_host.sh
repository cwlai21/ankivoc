#!/bin/bash
# Installs (or updates) the native messaging host for Anki Vocab Builder.
# Run once after cloning, or whenever the extension ID changes.

set -e

MANIFEST_SRC="$(cd "$(dirname "$0")" && pwd)/com.ankivoc.server.json"
DEST_DIR="$HOME/Library/Application Support/Google/Chrome/NativeMessagingHosts"

mkdir -p "$DEST_DIR"
cp "$MANIFEST_SRC" "$DEST_DIR/com.ankivoc.server.json"

echo "✅ Native messaging host installed at:"
echo "   $DEST_DIR/com.ankivoc.server.json"
echo ""
echo "If the extension ID changed, update allowed_origins in com.ankivoc.server.json"
echo "then re-run this script."
