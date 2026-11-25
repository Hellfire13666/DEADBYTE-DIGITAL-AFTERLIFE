#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
APP="$HOME/.local/share/deadbyte"
HEX="$HOME/.local/share/deadbyte-hexcodex"
BIN="$HOME/.local/bin/deadbyte"
RECIPE="$HEX/DEADBYTE-HEXCODEX-GUEST-20-RECIPES.html"

command -v python3 >/dev/null 2>&1 || {
    echo "ERROR // Python 3 required"
    exit 1
}

command -v install >/dev/null 2>&1 || {
    echo "ERROR // install utility required"
    exit 1
}

# Never overwrite an existing installation or private research vault.
if [ -e "$APP" ] || [ -L "$APP" ] ||
   [ -e "$BIN" ] || [ -L "$BIN" ] ||
   [ -e "$RECIPE" ] || [ -L "$RECIPE" ]; then
    echo "STOP // Existing DEADBYTE files detected."
    echo "No files were changed."
    exit 1
fi

for file in "$ROOT"/app/*; do
    [ -f "$file" ] && [ ! -L "$file" ] || {
        echo "ERROR // Invalid source package"
        exit 1
    }
done

install -d -m 700 "$APP" "$HEX" "$HOME/.local/bin"

for file in "$ROOT"/app/*; do
    install -m 600 "$file" "$APP/$(basename "$file")"
done

install -m 600 \
    "$ROOT/recipes/DEADBYTE-HEXCODEX-GUEST-20-RECIPES.html" \
    "$RECIPE"

cat > "$BIN" <<'LAUNCHER'
#!/bin/sh
exec python3 "$HOME/.local/share/deadbyte/deadbyte" "$@"
LAUNCHER
chmod 700 "$BIN"

echo "DEADBYTE // FILES INSTALLED"
echo "START COMMAND // deadbyte"
echo "If needed, add ~/.local/bin to your PATH."
