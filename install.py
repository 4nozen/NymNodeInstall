#!/usr/bin/env python3
"""
Nym Node Installer - Automated installation and configuration of a Nym Node
"""

import os
import sys
import json
import time
import argparse
import subprocess
import requests
from pathlib import Path
from typing import List, Optional, Dict, Any
from dataclasses import dataclass

@dataclass
class NodeConfig:
    """Node Configuration"""
    node_id: str = ""
    public_ip: str = ""
    binary_path: str = ""
    cosmos_mnemonic: str = ""
    nyx_address: str = ""
    rpc_endpoint: str = "https://nym-rpc.polkachu.com/"

class Colors:
    """ANSI colors for output"""
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    PURPLE = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    END = '\033[0m'

class Logger:
    """Logging utilities"""

    @staticmethod
    def success(message: str) -> None:
        print(f"{Colors.GREEN}✅ {message}{Colors.END}")

    @staticmethod
    def error(message: str) -> None:
        print(f"{Colors.RED}❌ {message}{Colors.END}")

    @staticmethod
    def warning(message: str) -> None:
        print(f"{Colors.YELLOW}⚠️  {message}{Colors.END}")

    @staticmethod
    def info(message: str) -> None:
        print(f"{Colors.BLUE}ℹ️  {message}{Colors.END}")

    @staticmethod
    def section(title: str) -> None:
        print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*50}")
        print(f"{title}")
        print(f"{'='*50}{Colors.END}")

class CommandRunner:
    """Command execution utilities"""

    @staticmethod
    def require_root() -> None:
        """Check for root privileges"""
        if os.geteuid() != 0:
            Logger.error("This script requires sudo privileges! Please run as root.")
            sys.exit(1)

    @staticmethod
    def run(cmd: List[str], sudo: bool = False, capture_output: bool = False,
            text: bool = True, check: bool = False) -> subprocess.CompletedProcess:
        """Execute a command"""
        if sudo:
            cmd = ['sudo'] + cmd
        return subprocess.run(cmd, capture_output=capture_output, text=text, check=check)

    @staticmethod
    def run_with_output(cmd: List[str], sudo: bool = False) -> int:
        """Execute a command with real-time output"""
        if sudo:
            cmd = ['sudo'] + cmd
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for line in process.stdout:
            print(line, end='')
            # sys.stdout.write('\r' + line.strip())
            # sys.stdout.flush()
        process.wait()
        if process.returncode != 0:
            raise subprocess.CalledProcessError(process.returncode, cmd)
        return process.returncode

class SystemManager:
    """System Management"""

    @staticmethod
    def update_system() -> bool:
        """Update the system"""
        CommandRunner.require_root()
        Logger.section("Updating the system")

        try:
            steps = [['apt-get', 'update'], ['apt-get', 'upgrade', '-y']]
            for idx, cmd in enumerate(steps, start=1):
                Logger.info(f"[{idx}/{len(steps)}] Executing: {' '.join(cmd)}")
                CommandRunner.run_with_output(cmd, sudo=True)

            Logger.success("System updated successfully!")
            return True
        except subprocess.CalledProcessError as e:
            Logger.error(f"Error: command '{e.cmd}' returned non-zero exit code {e.returncode}")
            return False

    @staticmethod
    def install_packages(packages: List[str]) -> bool:
        """Install packages"""
        CommandRunner.require_root()
        Logger.section(f"Checking and installing packages: {', '.join(packages)}")

        try:
            result = CommandRunner.run(['dpkg-query', '-W', '-f=${Package}\n'],
                                     capture_output=True, check=True)
            installed = set(result.stdout.splitlines())
        except subprocess.CalledProcessError:
            installed = set()

        to_install = set(packages) - installed
        if not to_install:
            Logger.success(f"Packages {', '.join(packages)} are already installed.")
            return True

        Logger.info(f"Installing: {', '.join(to_install)}")
        try:
            CommandRunner.run_with_output(['apt-get', 'install', '-y'] + list(to_install), sudo=True)
            Logger.success(f"Installed: {', '.join(to_install)}")
            return True
        except subprocess.CalledProcessError as e:
            Logger.error(f"Installation error: {e}")
            return False

class NetworkManager:
    """Network Management"""

    @staticmethod
    def get_public_ip() -> Optional[str]:
        """Get public IP address"""
        try:
            result = CommandRunner.run(['curl', '-4', '-s', 'https://ifconfig.me'],
                                     capture_output=True, check=True)
            ip = result.stdout.strip()
            Logger.info(f"Public IP: {ip}")
            return ip
        except subprocess.CalledProcessError:
            Logger.error("Failed to get public IP!")
            return None

    @staticmethod
    def open_ports(ports: List[int]) -> bool:
        """Open ports via ufw"""
        CommandRunner.require_root()
        Logger.section(f"Opening ports: {', '.join(map(str, ports))}")

        try:
            CommandRunner.run(['ufw', 'status'], sudo=True, capture_output=True, check=True)
        except subprocess.CalledProcessError:
            Logger.info("ufw is not installed. Installing...")
            try:
                CommandRunner.run_with_output(['apt-get', 'install', '-y', 'ufw'], sudo=True)
            except subprocess.CalledProcessError as e:
                Logger.error(f"Error installing ufw: {e}")
                return False

        try:
            status = CommandRunner.run(['ufw', 'status'], sudo=True, capture_output=True, check=True).stdout
            if "inactive" in status:
                Logger.info("Enabling ufw...")
                CommandRunner.run_with_output(['ufw', 'enable'], sudo=True)

            for port in ports:
                Logger.info(f"Opening port {port}...")
                CommandRunner.run_with_output(['ufw', 'allow', str(port)], sudo=True)

            Logger.success("Ports opened successfully via ufw.")
            return True

        except subprocess.CalledProcessError as e:
            Logger.error(f"Error configuring ufw: {e}")
            return False

class NymNodeManager:
    """Nym Node Management"""

    def __init__(self):
        self.config = NodeConfig()
        self.dest_dir = Path.home() / "nym"
        self.dest_dir.mkdir(exist_ok=True)

    def check_if_node_installed(self) -> bool:
        """Check if node is already installed"""
        nym_dir = Path.home() / ".nym"
        return nym_dir.exists()

    def download_latest_binary(self) -> str:
        """Download the latest binary and move it to /usr/local/bin"""
        Logger.section("Downloading the latest version of nym-node")

        api_url = "https://api.github.com/repos/nymtech/nym/releases/latest"
        try:
            result = CommandRunner.run(['curl', '-sL', api_url], capture_output=True, check=True)
            data = json.loads(result.stdout)
        except Exception as e:
            Logger.error(f"Error getting release information: {e}")
            sys.exit(1)

        download_url = None
        for asset in data.get("assets", []):
            if asset.get("name", "").startswith("nym-node"):
                download_url = asset.get("browser_download_url")
                break

        if not download_url:
            Logger.error("Could not find nym-node binary in the latest release.")
            sys.exit(1)

        tmp_path = "/tmp/nym-node"
        binary_dest_path = "/usr/local/bin/nym-node"
        
        Logger.info(f"Downloading {download_url} → {tmp_path}")

        try:
            CommandRunner.run(['wget', '-O', tmp_path, download_url], check=True)
            
            Logger.info(f"Moving binary to {binary_dest_path}")
            CommandRunner.run(['mv', tmp_path, binary_dest_path], sudo=True, check=True)
            CommandRunner.run(['chmod', '+x', binary_dest_path], sudo=True, check=True)
            
            Logger.success(f"Binary saved and made executable: {binary_dest_path}")

            self.config.binary_path = binary_dest_path
            return binary_dest_path
        except subprocess.CalledProcessError as e:
            Logger.error(f"Error during binary download/move: {e}")
            sys.exit(1)

    def initialize_node(self) -> bool:
        """Initialize the node"""
        Logger.section("Initializing the node")

        self.config.node_id = input("Enter your node ID: ").strip()
        if not self.config.node_id:
            Logger.error("ID cannot be empty!")
            return False

        self.config.public_ip = NetworkManager.get_public_ip()
        if not self.config.public_ip:
            return False

        Logger.info("Running initialization...")
        try:
            CommandRunner.run([
                self.config.binary_path,
                "run",
                "--mode", "mixnode",
                "--id", self.config.node_id,
                "--init-only",
                "--public-ips", self.config.public_ip,
                "--accept-operator-terms-and-conditions"
            ], check=True)
            Logger.success("Node initialized successfully!")
            return True
        except subprocess.CalledProcessError as e:
            Logger.error(f"Initialization error: {e}")
            return False

    def create_description_toml(self) -> str:
        """Create description.toml file"""
        Logger.section("Creating node description")

        base_dir = Path.home() / ".nym" / "nym-nodes" / self.config.node_id / "data"
        base_dir.mkdir(parents=True, exist_ok=True)
        file_path = base_dir / "description.toml"

        Logger.info("Please fill in the details for description.toml (you can leave them blank):")
        website = input("Website: ").strip()
        security_contact = input("Security Contact: ").strip()
        details = input("Details: ").strip()

        content = f'''moniker = "{self.config.node_id}"
website = "{website}"
security_contact = "{security_contact}"
details = "{details}"
'''

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

        Logger.success(f"description.toml file created: {file_path}")
        return str(file_path)

    def create_systemd_service(self) -> bool:
        """Create systemd service"""
        CommandRunner.require_root()
        Logger.section("Creating systemd service")

        if not self.config.node_id:
            Logger.error("node_id is not set!")
            return False

        service_name = "nym-node.service"
        service_path = f"/etc/systemd/system/{service_name}"

        service_content = f"""
[Unit]
Description=Nym Node
After=network.target

[Service]
User={os.getenv("USER", "root")}
ExecStart={self.config.binary_path} run --mode mixnode --id {self.config.node_id} --accept-operator-terms-and-conditions
Restart=on-failure
LimitNOFILE=65535

[Install]
WantedBy=multi-user.target
"""

        try:
            tmp_service = "/tmp/nym-node.service"
            with open(tmp_service, "w") as f:
                f.write(service_content)

            CommandRunner.run(['mv', tmp_service, service_path], sudo=True, check=True)
            CommandRunner.run(['chmod', '644', service_path], sudo=True, check=True)

            Logger.success(f"systemd unit created: {service_path}")

            CommandRunner.run(['systemctl', 'daemon-reload'], sudo=True, check=True)
            CommandRunner.run(['systemctl', 'enable', service_name], sudo=True, check=True)
            CommandRunner.run(['systemctl', 'start', service_name], sudo=True, check=True)

            Logger.success(f"Service {service_name} started and enabled on boot.")
            return True
        except subprocess.CalledProcessError as e:
            Logger.error(f"Error creating systemd service: {e}")
            return False

    def get_bonding_information(self) -> Dict[str, str]:
        """Get bonding information"""
        try:
            result = CommandRunner.run([
                self.config.binary_path,
                "bonding-information",
                "--id", self.config.node_id
            ], capture_output=True, check=True, text=True)

            output = result.stdout
            bonding_info = {}

            lines = output.strip().split('\n')
            for line in lines:
                if "Identity Key:" in line:
                    bonding_info["identity_key"] = line.split(":", 1)[1].strip()
                elif "Host:" in line:
                    bonding_info["host"] = line.split(":", 1)[1].strip()
            
            if not bonding_info.get("host"):
                 bonding_info["host"] = self.config.public_ip

            return bonding_info

        except subprocess.CalledProcessError as e:
            Logger.error(f"Error getting bonding information: {e}")
            return {}

    def get_cosmos_mnemonic(self) -> str:
        """Get cosmos mnemonic for the client account"""
        mnemonic_path = Path.home() / ".nym" / "nym-nodes" / self.config.node_id / "data" / "cosmos_mnemonic"

        if not mnemonic_path.exists():
            Logger.error("cosmos_mnemonic file not found. Make sure the node is initialized.")
            return ""

        try:
            with open(mnemonic_path, 'r') as f:
                mnemonic = f.read().strip()

            self.config.cosmos_mnemonic = mnemonic
            return mnemonic
        except Exception as e:
            Logger.error(f"Error reading cosmos_mnemonic: {e}")
            return ""

    def check_balance(self, address: str) -> None:
        """Check NYX account balance"""
        Logger.info(f"Checking account balance: {address}")
        
        try:
            api_url = f"https://validator.nymtech.net/api/v1/unstable/account/{address}"
            response = requests.get(api_url, timeout=10)
            response.raise_for_status()
            data = response.json()

            balance_unym = 0
            for coin in data.get('balances', []):
                if coin.get('denom') == 'unym':
                    balance_unym = int(coin.get('amount', 0))
                    break
            
            balance_nym = balance_unym / 1_000_000
            Logger.info(f"Current balance: {balance_nym:.6f} NYM")

        except requests.exceptions.RequestException as e:
            Logger.error(f"Error checking balance: {e}")
        except (json.JSONDecodeError, KeyError) as e:
            Logger.error(f"Error parsing response from API: {e}")
        except Exception as e:
            Logger.error(f"Unexpected error while checking balance: {e}")

    def sign_contract_message(self) -> None:
        """Sign the contract message"""
        Logger.section("Signing the contract message")

        bonding_info = self.get_bonding_information()
        if not bonding_info or not bonding_info.get("identity_key"):
            Logger.error("Failed to get bonding information. Cannot continue.")
            return

        Logger.info("Use the following details in the Nym Wallet:")
        print(f"  {Colors.YELLOW}Identity Key:{Colors.END} {bonding_info['identity_key']}")
        print(f"  {Colors.YELLOW}Host:{Colors.END} {bonding_info['host']}")
        
        Logger.info("\nPlease follow the instructions at: https://nym.com/docs/operators/nodes/nym-node/bonding#bond-via-the-desktop-wallet-recommended")
        
        while True:
            payload = input("\nPaste the <PAYLOAD_GENERATED_BY_THE_WALLET>: ").strip()
            if payload:
                break
            Logger.error("Payload cannot be empty! Please paste the payload to continue.")

        try:
            cmd = [self.config.binary_path, "sign", "--id", self.config.node_id, "--contract-msg", payload]
            Logger.info(f"Executing: ")
            CommandRunner.run_with_output(cmd)

        except subprocess.CalledProcessError as e:
            Logger.error(f"Error signing message: {e}")


class NymNodeInstaller:
    """Main installer class"""

    def __init__(self):
        self.node_manager = NymNodeManager()

    def run(self, no_update: bool = False):
        """Run the installer"""
        try:
            Logger.info("Welcome to the Nym Node Installer!")

            if not self.install_node(no_update=no_update):
                sys.exit(1)

            self.show_mnemonic()

            Logger.section("Next Steps")
            Logger.info("1. Download the Nym Wallet: https://nym.com/wallet")
            Logger.info("2. Restore your account using the Mnemonic phrase you saved.")
            Logger.info("3. You wallet acount must have a balance of at least 100 NYM.")
            input("Press Enter when you are ready to continue...")
            
            self.node_manager.sign_contract_message()

            Logger.success("All done! The node has been installed and configured.")

        except KeyboardInterrupt:
            Logger.warning("Installation interrupted by user.")
            sys.exit(1)
        except Exception as e:
            Logger.error(f"An unexpected error occurred: {e}")
            sys.exit(1)


    def install_node(self, no_update: bool = False) -> bool:
        """Full node installation"""
        Logger.section("Nym Node Installer - Starting installation")

        if not no_update:
            if not SystemManager.update_system():
                return False
        else:
            Logger.info("Skipping system update as requested.")

        if self.node_manager.check_if_node_installed():
            reinstall = input("Nym node is already installed. Do you want to reinstall? (y/N): ").lower().strip()
            if reinstall != 'y':
                Logger.info("Installation cancelled.")
                return False

        if not SystemManager.install_packages(['curl', 'wget']):
            return False

        self.node_manager.download_latest_binary()

        if not NetworkManager.open_ports([8080, 1789, 1790, 9000]):
            return False

        if not self.node_manager.initialize_node():
            return False

        self.node_manager.create_description_toml()

        if not self.node_manager.create_systemd_service():
            return False

        Logger.success("Node installation complete!")
        return True

    def show_mnemonic(self):
        """Display the mnemonic phrase"""
        Logger.section("Save your Mnemonic phrase")
        mnemonic = self.node_manager.get_cosmos_mnemonic()
        if not mnemonic:
            Logger.error("Could not get mnemonic phrase.")
            return

        Logger.warning("IMPORTANT: Save this phrase in a secure place! It is required to access your wallet.")
        print(f"\n{Colors.YELLOW}{mnemonic}{Colors.END}\n")
        input("Press Enter after you have saved the phrase...")

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="Nym Node Installer")
    parser.add_argument("--no-update", action="store_true", help="Skip system update")
    args = parser.parse_args()

    installer = NymNodeInstaller()
    installer.run(no_update=args.no_update)

if __name__ == "__main__":
    main()
