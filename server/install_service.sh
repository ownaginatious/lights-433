#!/bin/bash -
#title           :install_service.sh
#description     :This script installs the Lights-433 server onto a Linux
#                 machine (preferably a Raspberry Pi) running the systemd
#                 init system.
#author          :Dillon Dixon
#date            :20160428
#version         :0.1
#===============================================================================

set -e -u

# Check if the script is being run as root.
if [ "$EUID" -ne 0 ]; then
    >&2 echo "Please run this script as root or with the sudo command."
    exit 1
fi

if [[ "$(uname)" != "Linux" ]]; then
    echo "This installation script is only designed for Linux machines."
    exit 1
fi

if [ -z "$(which python2 2> /dev/null)" ]; then
    echo "No Python 2 installation found. Ensure Python 2 is installed (python2)."
    exit 1
fi

if [ -z "$(which systemctl 2> /dev/null)" ]; then
    echo "This script only works with systems running systemd."
    exit 1
fi

echo " >> Stopping any running lights-433 services..."
# Stop and disable any running services, if they exist.
systemctl disable "lights-433" &> /dev/null || true
systemctl stop "lights-433" &> /dev/null || true

install_dir="/opt/lights-433"
if [[ "${1:-}" == "purge" ]]; then
    echo " >> Deleting old installations (${install_dir})... "
    rm -rf "${install_dir}"
fi

config_dir="/etc/lights-433"
echo " >> Creating config directory (${config_dir})..."
mkdir -p "${config_dir}"

config_file="${config_dir}/switches.conf"
echo " >> Creating config file (${config_file})..."
touch "${config_file}"

sentry_config_file="${config_dir}/sentry.conf"
echo " >> Creating sentry config file (${sentry_config_file})..."
touch "${sentry_config_file}"

echo " >> Creating virtualenv... (${install_dir}/venv)"
if [ -z "$(which virtualenv 2> /dev/null)" ]; then
    echo "Virtualenv is missing! Please install from pip or package manager."
    exit 1
fi

if [[ ! -d "${install_dir}/venv" ]]; then
    virtualenv "${install_dir}/venv" --python "$(which python2)"
fi
set +u
. "${install_dir}/venv/bin/activate"
set -u

# Change to the script's directory.
cd "$(dirname "$0")"
echo " >> Uninstalling older versions of lights-433..."
pip uninstall --yes lights-433 || true
echo " >> Installing lights-433..."
python2 "./setup.py" install

tmp_file="$(mktemp -t lights-433.XXXXXXXXXX)"

echo " >> Generating systemd unit file..."
# Create the systemd unit file
{
    echo "[Unit]"
    echo "Description=Lights 433MHz Control Server"
    echo "After=network.target"

    echo "[Service]"
    echo "WorkingDirectory=${install_dir}"
    echo "ExecStart=${install_dir}/venv/bin/lights433 rpi --adapter-args reset_pin=4 --host 0.0.0.0 --port 5000"
    echo "Type=simple"
    echo "Restart=always"
    echo "RestartSec=10"

    echo "[Install]"
    echo "WantedBy=multi-user.target"

} >> "${tmp_file}"

echo " >> Installing systemd unit file..."
cp "${tmp_file}" "/usr/lib/systemd/system/lights-433.service"
systemctl enable "lights-433"
systemctl start "lights-433"
rm -f "${tmp_file}"

echo ""
echo "  Light-433 service installed and started!"
echo "  Please re-run this script to make any changes."
echo ""
echo "  Configure via: ${config_file}"
echo ""
