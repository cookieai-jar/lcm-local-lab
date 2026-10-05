#!/bin/sh
# Idempotent host bootstrap for lcm-local-lab: Homebrew, Colima, docker, docker-compose,
# the oaa-runner-internal submodule. Run via `make install`, safe to re-run.
set -e

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "==> git submodules"
git -C "$REPO_ROOT" submodule update --init --recursive

if command -v brew >/dev/null 2>&1; then
    echo "==> Homebrew already installed ($(command -v brew))"
else
    echo "==> Homebrew not found, installing"
    if sudo -n true 2>/dev/null; then
        # Passwordless sudo available: use the official installer (/opt/homebrew).
        NONINTERACTIVE=1 /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    else
        # No sudo (common on locked-down corporate laptops): install into a
        # user-owned prefix instead. This is Homebrew's official sudo-free method.
        echo "    no passwordless sudo; installing into \$HOME/homebrew instead of /opt/homebrew"
        mkdir -p "$HOME/homebrew"
        curl -fsSL https://github.com/Homebrew/brew/tarball/main | tar xz --strip-components 1 -C "$HOME/homebrew"
        echo ""
        echo "    IMPORTANT: add this to your shell profile (~/.zshrc), then open a new shell:"
        echo "        export PATH=\"\$HOME/homebrew/bin:\$PATH\""
        echo ""
    fi
fi

# Make sure this script's own `brew`/`colima`/`docker` calls below can find a
# user-prefix install even in a shell that hasn't sourced the profile change yet.
export PATH="$HOME/homebrew/bin:$PATH"

brew_install_if_missing() {
    if command -v "$1" >/dev/null 2>&1; then
        echo "==> $1 already installed"
    else
        echo "==> installing $1"
        brew install "$1"
    fi
}

brew_install_if_missing colima
brew_install_if_missing docker
brew_install_if_missing docker-compose

echo "==> wiring docker-compose as a docker CLI plugin"
mkdir -p "$HOME/.docker/cli-plugins"
ln -sf "$(brew --prefix)/bin/docker-compose" "$HOME/.docker/cli-plugins/docker-compose"

if colima status >/dev/null 2>&1; then
    echo "==> colima already running"
else
    echo "==> starting colima"
    ARCH="$(uname -m)"
    if [ "$ARCH" = "arm64" ]; then
        # osixia images are amd64-only; vz+rosetta lets Colima run them on Apple Silicon.
        colima start --cpu 4 --memory 8 --disk 60 --vm-type vz --vz-rosetta
    else
        colima start --cpu 4 --memory 8 --disk 60
    fi
fi

echo "==> done. docker context:"
docker context ls
