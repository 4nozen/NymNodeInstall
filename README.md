# Nym Node Installer

This script provides an automated way to install, configure, and manage a [Nym Mixnode](https://nymtech.net/docs/operators/nodes/nym-node/). It is designed for Debian-based Linux distributions (like Ubuntu) and automates most of the setup process.

## Features

- **Automated System Setup**: Updates the system and installs necessary dependencies (`curl`, `wget`, `ufw`).
- **Latest Binary Download**: Fetches the latest stable release of the `nym-node` binary directly from the official Nym GitHub repository.
- **Node Initialization**: Guides the user through the initial node configuration.
- **Firewall Configuration**: Automatically configures `ufw` to open the required ports (8080, 1789, 1790, 9000).
- **Systemd Service**: Creates and enables a `systemd` service to ensure the node runs automatically on system boot.
- **Bonding Helper**: Simplifies the process of signing the contract message required for bonding the node with the Nym Wallet.

## Prerequisites

- A server running a Debian-based Linux distribution (e.g., Ubuntu 20.04 or later).
- `sudo` or `root` privileges.
- At least 100 NYM tokens in your Nym Wallet for bonding the node.

## Usage

1.  **Clone the repository or download the script:**

    ```bash
    wget https://https://github.com/4nozen/NymNodeInstall/blob/main/install.py
    ```

2.  **Run the installer:**

    The script requires `sudo` privileges for system-wide changes.

    **Standard Installation (with system update):**

    ```bash
    python3 install.py
    ```

    **Installation without system update:**
    If you want to skip the initial system update and upgrade steps, use the `--no-update` flag:

    ```bash
    python3 install.py --no-update
    ```

## Installation Process

The script will guide you through the following steps:

1.  **System Update (Optional)**: Updates your system's package lists and upgrades installed packages.
2.  **Dependency Installation**: Installs required tools.
3.  **Nym Binary Download**: Downloads and installs the `nym-node` binary.
4.  **Firewall Setup**: Configures `ufw`.
5.  **Node Initialization**: You will be prompted to enter a unique **Node ID**.
6.  **Mnemonic Phrase**: The script will display your node's mnemonic phrase. **Save this phrase in a secure location!** You will need it to restore your wallet.
7.  **Bonding**: The script will provide you with an **Identity Key** and **Host IP**. You will need to use these in the Nym Wallet to generate a payload.
8.  **Signing**: Paste the payload from the wallet back into the terminal to complete the signing process.
9.  **Service Start**: The `nym-node` service will be started and enabled on boot.

---

**You can delegate to my nodes:**

- F618gw6jZaLR1VdMTeaH11MhHQJY5rdpYEDLrMKEHcjk
- E3BayLcp2RiQ66ZxzkPkZuREYCYrsHB1o7vFULQ6u6Np
- G2adZrt5ByjSZKrR6G139FYfd4ScxHbinQjpP28h4APm

  [bumpmeup nodes](https://nymesis.vercel.app/?q=bump)

_Node monitoring tool:_
[Nymesis](https://nymesis.vercel.app/) https://nymesis.vercel.app/

---

> **⚠️ Security Warning**
>
> Always review scripts that require `sudo` privileges before running them on your system. This script performs system-wide actions, including installing packages, modifying the firewall, and creating system services.
