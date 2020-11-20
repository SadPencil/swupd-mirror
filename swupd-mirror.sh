#!/usr/env/bin bash
set -e

target_dir="$PWD/mirror"
upstream_server_url="https://cdn.download.clearlinux.org"

_version=v0.1
echo "swupd-mirror $_version"
echo "get the metadata from the upstream server..."

latest_version=$(( "$(curl -- "$upstream_server_url"/latest)" ))
echo "latest version: $latest_version"

manifest="$(curl -- "$upstream_server_url"/update/"$latest_version"/Manifest.MoM)"
version=$(( "$(echo "$manifest" | grep "^version:" | head -n 1 | awk -F ':' '{print $2}')" ))
minversion=$(( "$(echo "$manifest" | grep "^minversion:" | head -n 1 | awk -F ':' '{print $2}')" ))

[ "$version" = "$latest_version" ] || ( echo "version mismatch. " 1>&2 ; exit 1 ) || exit 1
echo "min version: $minversion"
unset manifest
unset version

echo "download files..."

cd -- "$target_dir"

names=(0 version "$latest_version" "$minversion")

for name in "${names[@]}"
do
    wget --no-verbose --no-parent --recursive --no-host-directories -erobots=off --reject "index.html" "$upstream_server_url"/update/"$name"/
done
