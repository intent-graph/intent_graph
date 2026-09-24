#!/usr/bin/env zsh
# bootstrap.sh — idempotent installer for the IntentGraph VS Code extension.
#
# Re-running this script is safe: each step checks current state and only
# acts if the system has drifted from the target state.
#
# Usage:
#   ./bootstrap.sh              # interactive
#   ./bootstrap.sh --yes        # accept all prompts (CI / scripted re-run)
#   ./bootstrap.sh --no-build   # skip npm install/build (use when dist/ committed)
#   ./bootstrap.sh --uninstall  # remove all symlinks (CLI install untouched)

set -euo pipefail

# --- Resolve paths (the script lives in the extension folder) ---
SCRIPT_DIR="${0:A:h}"                                # absolute, symlink-resolved
EXT_DIR="$SCRIPT_DIR"
EXT_NAME="intentgraph.intentgraph-0.0.1"             # must match package.json publisher.name-version
IG_REPO="${EXT_DIR}/../.."                           # intent_graph/ (repo root)
IG_REPO="${IG_REPO:A}"
IG_TOOL_PYPROJECT="${IG_REPO}"                       # source for `uv tool install -e`
if ! grep -qs '^name = "intentgraph-tools"' "${IG_TOOL_PYPROJECT}/pyproject.toml"; then
  print -u2 "bootstrap.sh: no intentgraph-tools pyproject.toml at ${IG_TOOL_PYPROJECT}"
  print -u2 "  (expected layout: intent_graph/vscode_extension/intentgraph-vscode/)"
  exit 1
fi

# --- Flags ---
ASSUME_YES=0
SKIP_BUILD=0
UNINSTALL=0
for arg in "$@"; do
  case "$arg" in
    --yes|-y) ASSUME_YES=1 ;;
    --no-build) SKIP_BUILD=1 ;;
    --uninstall) UNINSTALL=1 ;;
    -h|--help)
      sed -n '2,12p' "$0"; exit 0 ;;
    *) echo "Unknown arg: $arg" >&2; exit 2 ;;
  esac
done

# --- Pretty output ---
say()  { print -P "%F{cyan}==>%f $*"; }
ok()   { print -P "%F{green}  ✓%f $*"; }
skip() { print -P "%F{yellow}  ·%f $*"; }
warn() { print -P "%F{yellow}  ⚠%f $*"; }
err()  { print -P "%F{red}  ✗%f $*" >&2; }

confirm() {
  # confirm "prompt" → returns 0 (yes) or 1 (no). Respects --yes.
  (( ASSUME_YES )) && return 0
  local reply
  read -q "reply?$1 [y/N] " || { print; return 1; }
  print
  return 0
}

# --- Editor detection ---
# Each entry: "name|extensions_dir|cli_binary"
typeset -a EDITORS
EDITORS=(
  "VS Code|$HOME/.vscode/extensions|code"
  "VS Code Insiders|$HOME/.vscode-insiders/extensions|code-insiders"
  "Cursor|$HOME/.cursor/extensions|cursor"
  "VSCodium|$HOME/.vscode-oss/extensions|codium"
  "Windsurf|$HOME/.windsurf/extensions|windsurf"
)

# ========== UNINSTALL PATH ==========
if (( UNINSTALL )); then
  say "Uninstalling symlinks (CLI install via uv left intact)"
  for entry in "${EDITORS[@]}"; do
    local name="${entry%%|*}"
    local rest="${entry#*|}"
    local ext_dir="${rest%%|*}"
    local link_path="${ext_dir}/${EXT_NAME}"
    if [[ -L "$link_path" ]]; then
      local target="$(readlink "$link_path")"
      if [[ "${target:A}" == "${EXT_DIR:A}" ]]; then
        rm "$link_path"
        ok "$name: removed $link_path"
      else
        skip "$name: symlink at $link_path points elsewhere ($target), not touching"
      fi
    elif [[ -e "$link_path" ]]; then
      skip "$name: $link_path is not a symlink, not touching"
    else
      skip "$name: no install found"
    fi
  done
  ok "Uninstall complete. Reload your editor windows."
  exit 0
fi

# ========== PREREQ CHECKS ==========
say "Checking prerequisites"

if ! command -v uv >/dev/null 2>&1; then
  err "uv not found. Install: curl -LsSf https://astral.sh/uv/install.sh | sh"
  exit 1
fi
ok "uv: $(uv --version)"

if (( ! SKIP_BUILD )); then
  if ! command -v npm >/dev/null 2>&1; then
    err "npm not found. Install Node 18+ (https://nodejs.org) or re-run with --no-build if dist/ is committed."
    exit 1
  fi
  ok "npm: $(npm --version)"
fi

# ========== STEP 1: ig-tool installed editably and points at this repo ==========
say "Step 1/4: ig-tool (editable install from this repo)"

needs_install=1
if uv tool list 2>/dev/null | grep -q '^intentgraph-tools '; then
  # uv tool list shows packages; we need to verify the install is editable
  # AND points at *this* clone. Check via the resolved entry-point script.
  if command -v ig-tool >/dev/null 2>&1; then
    # Resolve via uv's tool dir; an editable install will have a .pth or
    # equivalent pointing back at IG_TOOL_PYPROJECT.
    ig_tool_venv_site="$(uv tool dir 2>/dev/null)/intentgraph-tools/lib/python*/site-packages"
    # zsh glob: expand to first match
    setopt local_options nullglob
    sites=(${~ig_tool_venv_site})
    if (( ${#sites} )); then
      if grep -rqsF "$IG_TOOL_PYPROJECT" "${sites[1]}" 2>/dev/null; then
        skip "ig-tool already installed editably from $IG_TOOL_PYPROJECT"
        needs_install=0
      else
        warn "ig-tool installed but not from this repo — will reinstall"
      fi
    fi
  fi
fi

if (( needs_install )); then
  uv tool install -e "$IG_TOOL_PYPROJECT" --reinstall
  ok "ig-tool installed from $IG_TOOL_PYPROJECT"
fi

# ========== STEP 2: npm install ==========
if (( SKIP_BUILD )); then
  skip "Step 2/4: npm install (skipped, --no-build)"
else
  say "Step 2/4: npm dependencies"
  # node_modules/.package-lock.json is npm's own marker of "install matches lockfile"
  marker="$EXT_DIR/node_modules/.package-lock.json"
  lockfile="$EXT_DIR/package-lock.json"
  if [[ -f "$marker" && "$marker" -nt "$lockfile" ]]; then
    skip "node_modules up to date with package-lock.json"
  else
    ( cd "$EXT_DIR" && npm install )
    ok "npm install complete"
  fi
fi

# ========== STEP 3: build dist/ ==========
if (( SKIP_BUILD )); then
  skip "Step 3/4: build (skipped, --no-build)"
  if [[ ! -f "$EXT_DIR/dist/extension.js" ]]; then
    err "dist/extension.js missing and --no-build set. Either drop --no-build or commit dist/."
    exit 1
  fi
else
  say "Step 3/4: build extension"
  dist="$EXT_DIR/dist/extension.js"
  needs_build=1
  if [[ -f "$dist" ]]; then
    # Check if any source file is newer than the built artifact.
    newer="$(find "$EXT_DIR/src" -type f \( -name '*.ts' -o -name '*.mjs' -o -name '*.html' -o -name '*.css' \) -newer "$dist" -print -quit 2>/dev/null)"
    if [[ -z "$newer" && "$EXT_DIR/package.json" -ot "$dist" && "$EXT_DIR/esbuild.mjs" -ot "$dist" ]]; then
      skip "dist/extension.js up to date with sources"
      needs_build=0
    fi
  fi
  if (( needs_build )); then
    ( cd "$EXT_DIR" && npm run package )
    ok "Built $dist"
  fi
fi

# ========== STEP 4: symlink into each detected editor ==========
say "Step 4/4: editor symlinks"

installed_count=0
for entry in "${EDITORS[@]}"; do
  name="${entry%%|*}"
  rest="${entry#*|}"
  ext_dir="${rest%%|*}"
  cli="${rest##*|}"

  # Detect: either the extensions dir already exists, OR the CLI is on PATH.
  if [[ ! -d "$ext_dir" ]] && ! command -v "$cli" >/dev/null 2>&1; then
    continue   # editor not installed; silent skip
  fi

  link_path="${ext_dir}/${EXT_NAME}"
  mkdir -p "$ext_dir"

  # Case A: link already correct.
  if [[ -L "$link_path" ]]; then
    current_target="$(readlink "$link_path")"
    if [[ "${current_target:A}" == "${EXT_DIR:A}" ]]; then
      skip "$name: symlink already points here"
      installed_count=$((installed_count+1))
      continue
    fi
    # Case B: stale symlink (points elsewhere). Symlinks are safe to replace.
    warn "$name: existing symlink points to $current_target"
    if confirm "  Replace with link to $EXT_DIR?"; then
      rm "$link_path"
      ln -s "$EXT_DIR" "$link_path"
      ok "$name: symlinked"
      installed_count=$((installed_count+1))
    else
      skip "$name: left as-is"
    fi
    continue
  fi

  # Case C: a real directory exists at the target — could contain user state.
  if [[ -d "$link_path" ]]; then
    warn "$name: $link_path exists as a real directory (not a symlink)"
    if confirm "  Move it aside to ${link_path}.backup and create symlink?"; then
      mv "$link_path" "${link_path}.backup.$(date +%s)"
      ln -s "$EXT_DIR" "$link_path"
      ok "$name: symlinked (old folder moved aside)"
      installed_count=$((installed_count+1))
    else
      skip "$name: left as-is"
    fi
    continue
  fi

  # Case D: nothing there — ask before creating (per-editor prompt).
  if confirm "$name detected. Install extension symlink to $link_path?"; then
    ln -s "$EXT_DIR" "$link_path"
    ok "$name: symlinked"
    installed_count=$((installed_count+1))
  else
    skip "$name: declined"
  fi
done

if (( installed_count == 0 )); then
  warn "No editor symlinks created. Re-run with an editor installed, or use --yes to accept defaults."
fi

# ========== SMOKE TEST ==========
say "Verifying installation"

# 1. ig-tool reachable
if ig-tool --help >/dev/null 2>&1; then
  ok "ig-tool --help: OK"
else
  err "ig-tool --help failed"
  exit 1
fi

# 2. package.json parses and main file exists
main_field="$(node -e "console.log(require('$EXT_DIR/package.json').main)" 2>/dev/null || true)"
if [[ -z "$main_field" ]]; then
  err "Could not read 'main' from package.json"
  exit 1
fi
main_path="$EXT_DIR/${main_field#./}"
if [[ ! -f "$main_path" ]]; then
  err "Built extension not found at $main_path"
  exit 1
fi
ok "Extension entry point readable: $main_field"

# 3. Each symlink resolves to a readable target
for entry in "${EDITORS[@]}"; do
  name="${entry%%|*}"
  rest="${entry#*|}"
  ext_dir="${rest%%|*}"
  link_path="${ext_dir}/${EXT_NAME}"
  if [[ -L "$link_path" ]]; then
    if [[ -r "${link_path:A}/package.json" ]]; then
      ok "$name: symlink resolves to readable extension"
    else
      err "$name: symlink at $link_path is broken"
      exit 1
    fi
  fi
done

print
ok "Done. Reload your editor window(s) to pick up changes."
print "       (Cmd+Shift+P → 'Developer: Reload Window')"
