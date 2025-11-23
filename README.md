# Nym Node Installer

Automated installation script for Nym Network nodes with interactive setup.

[![Python 3.6+](https://img.shields.io/badge/python-3.6%2B-blue.svg)](https://www.python.org/downloads/)
[![Linux](https://img.shields.io/badge/platform-Linux-lightgrey.svg)](https://www.linux.org/)

## Features

- Automated system setup and configuration
- Support for Mixnodes and Exit Gateways
- Automatic firewall configuration
- Color-coded interactive interface
- Systemd service with auto-restart
- Balance verification
- Interactive contract signing

## Requirements

- Linux (Debian/Ubuntu)
- Python 3.6+
- sudo privileges
- Public IP address
- 101+ NYM tokens

## Quick Start

```bash
# Download
wget wget https://raw.githubusercontent.com/4nozen/NymNodeInstall/main/nym_installer.py

# Run
python3 nym_installer.py
```

## Usage

```bash
# Full installation
python3 nym_installer.py

# Skip system update
python3 nym_installer.py --no-update
```

The installer will guide you through:
1. System setup and dependencies
2. Node mode selection (Mixnode/Exit Gateway)
3. Firewall configuration
4. Node initialization
5. Wallet setup and funding
6. Contract signing

## Service Management

```bash
# Check status
sudo systemctl status nym-node

# View logs
sudo journalctl -u nym-node -f

# Restart
sudo systemctl restart nym-node
```

## Configuration

- Binary: `/usr/local/bin/nym-node`
- Config: `~/.nym/nym-nodes/YOUR_NODE_ID/`
- Service: `/etc/systemd/system/nym-node.service`

## Ports

- `8080` - HTTP API
- `1789` - Mixnet traffic
- `1790` - Verloc protocol
- `9000` - WireGuard (Exit Gateway)

## Security

⚠️ **Important**: Save your 24-word mnemonic phrase securely. It's the only way to recover your wallet.

# nym-node Updater

Simple Python script to check and update nym-node binary from GitHub releases.

## Features

- Checks current nym-node version
- Fetches latest release from GitHub
- Downloads and compares versions
- Interactive or automatic update
- Optional service restart
- Comprehensive logging

## Requirements

```bash
pip install requests
```

## Usage

### Interactive mode
```bash
./nym_updater.py
```

Script will ask for confirmation before updating and restarting service.

### Automatic mode
```bash
./nym_updater.py -y
```

Automatically answers "yes" to all prompts (update + service restart).

## What it does

1. Finds your current nym-node installation
2. Gets current Build Version
3. Checks GitHub for latest release
4. Downloads new binary to `/tmp/nym-update/`
5. Compares versions
6. If update available:
   - Creates backup of current binary
   - Replaces binary using `sudo`
   - Optionally restarts `nym-node.service`

## Example output

```
📦 Current Build Version: 2025-01-15T10:30:00Z
🌐 Latest Release: nym-binaries-v2025.20-leerdammer
📥 Downloaded Build Version: 2025-01-20T14:45:00Z

✅ Update available! (2025-01-20T14:45:00Z > 2025-01-15T10:30:00Z)

Do you want to update? [y/N]: y
✅ Update successful!

Restart nym-node.service? [y/N]: y
✅ Service restarted successfully
```

## Notes

- Requires `sudo` access for updating binary and restarting service
- Creates backup with `.backup` suffix before updating
- Binary locations checked:
  - System PATH
  - `~/.nym/bin/nym-node`

## Support

- [Nym Discord](https://discord.gg/nym)
- [Documentation](https://nymtech.net/docs)

## Support the Developer

Delegate to:
```
8jFCkcCJus7cHg8LVQiTwbEuKqzmMm6EwYezNx2cKArB
EmUjBBYcvNzEovM7AhxrYXeTJJ4Kg2g2w7sP6V1GDa13
CRzMQu3Fbf3eGCscPog323gofAGWzT37gXuvWEFHm9NG
G2adZrt5ByjSZKrR6G139FYfd4ScxHbinQjpP28h4APm
E3BayLcp2RiQ66ZxzkPkZuREYCYrsHB1o7vFULQ6u6Np
F618gw6jZaLR1VdMTeaH11MhHQJY5rdpYEDLrMKEHcjk
```

Donate: `n18lc3qmx4jqzr55gvh5qmg6z3q4874x4xmmhhqd`

## License

MIT License - see [LICENSE](LICENSE) file
