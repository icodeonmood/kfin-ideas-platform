#!/usr/bin/env bash
# One-time setup of a Mac (Apple silicon) to run the full stack and every test gate.
#
#   scripts/setup-mac.sh --check   report what is missing; change nothing
#   scripts/setup-mac.sh           install what is missing (Homebrew packages), size and start Colima,
#                                  install project dependencies (make setup)
# Then:  make verify
#
# Never touches an existing Colima VM: if one exists, it is reported (and started if stopped), not resized.
set -euo pipefail

CHECK_ONLY=0
[[ "${1:-}" == "--check" ]] && CHECK_ONLY=1

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BREW_PACKAGES=(colima docker docker-compose docker-buildx uv node gh)
PORTS=(3000 5432 8000 8025 1025 8090 9000 3310)
problems=0

say()  { printf '%s\n' "$*"; }
ok()   { printf '  ok    %s\n' "$*"; }
todo() { printf '  todo  %s\n' "$*"; problems=$((problems + 1)); }
warn() { printf '  warn  %s\n' "$*"; }

say "== This Mac"
[[ "$(uname -s)" == "Darwin" ]] || { say "This script is for macOS."; exit 1; }
ram_gb=$(( $(sysctl -n hw.memsize) / 1024 / 1024 / 1024 ))
cpus=$(sysctl -n hw.ncpu)
ok "$(sysctl -n machdep.cpu.brand_string), ${cpus} cores, ${ram_gb} GB RAM, $(uname -m)"
[[ "$(uname -m)" == "arm64" ]] || warn "not Apple silicon; images are multi-arch, but only arm64 has been tested"
free_gb=$(df -g "$HOME" | awk 'NR==2 {print $4}')
(( free_gb >= 30 )) && ok "${free_gb} GB free disk" || warn "only ${free_gb} GB free disk; 30 GB or more recommended"

say "== Homebrew packages"
if ! command -v brew >/dev/null 2>&1; then
  todo "Homebrew is not installed: see https://brew.sh, then re-run this script"
  exit 1
fi
missing=()
for pkg in "${BREW_PACKAGES[@]}"; do
  if brew list --versions "$pkg" >/dev/null 2>&1; then ok "$pkg $(brew list --versions "$pkg" | awk '{print $2}')"; else missing+=("$pkg"); todo "$pkg not installed"; fi
done
if (( ${#missing[@]} )) && (( ! CHECK_ONLY )); then
  say "   installing: ${missing[*]}"
  brew install "${missing[@]}"
fi

say "== Docker CLI plugins (compose, buildx)"
plugin_dir="$(brew --prefix)/lib/docker/cli-plugins"
config="$HOME/.docker/config.json"
if [[ -f "$config" ]] && grep -q "$plugin_dir" "$config"; then
  ok "$config lists $plugin_dir"
else
  todo "$config does not list $plugin_dir"
  if (( ! CHECK_ONLY )); then
    mkdir -p "$HOME/.docker"
    node -e '
      const fs = require("fs"); const [file, dir] = process.argv.slice(1);
      const cfg = fs.existsSync(file) ? JSON.parse(fs.readFileSync(file, "utf8")) : {};
      cfg.cliPluginsExtraDirs = [...new Set([...(cfg.cliPluginsExtraDirs || []), dir])];
      fs.writeFileSync(file, JSON.stringify(cfg, null, 2) + "\n");
    ' "$config" "$plugin_dir"
    ok "added $plugin_dir to $config"
  fi
fi

say "== Colima (the Docker VM)"
# Half the RAM, at most 12 GB; leave two cores for macOS, at most 8.
vm_mem=$(( ram_gb / 2 )); (( vm_mem > 12 )) && vm_mem=12; (( vm_mem < 4 )) && vm_mem=4
vm_cpu=$(( cpus - 2 )); (( vm_cpu > 8 )) && vm_cpu=8; (( vm_cpu < 2 )) && vm_cpu=2
if command -v colima >/dev/null 2>&1 && colima list 2>/dev/null | awk 'NR>1 && $1=="default"' | grep -q .; then
  row=$(colima list 2>/dev/null | awk 'NR>1 && $1=="default" {print $2, $4, $5}')
  ok "existing Colima VM (status, CPUs, memory): ${row}; not resized"
  if [[ "$row" == Stopped* ]] && (( ! CHECK_ONLY )); then colima start; fi
else
  todo "no Colima VM yet; would create one with ${vm_cpu} CPUs and ${vm_mem} GB"
  (( CHECK_ONLY )) || colima start --cpu "$vm_cpu" --memory "$vm_mem" --disk 60
fi

say "== Ports the stack needs"
for port in "${PORTS[@]}"; do
  if lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
    warn "port $port is in use by $(lsof -nP -iTCP:"$port" -sTCP:LISTEN | awk 'NR==2 {print $1}')"
  else
    ok "port $port free"
  fi
done

say "== Project dependencies"
if (( CHECK_ONLY )); then
  [[ -d "$ROOT/services/worker/.venv" ]] && ok "Python environment present" || todo "Python environment (make setup)"
  [[ -d "$ROOT/apps/web/node_modules" ]] && ok "Node modules present" || todo "Node modules (make setup)"
else
  (cd "$ROOT" && make setup)
fi

say ""
if (( CHECK_ONLY )); then
  say "Check finished: ${problems} item(s) to set up. Run without --check to set them up."
else
  say "Setup finished. Next: make verify   (starts the stack and runs lint, tests, e2e and eval)"
fi
