#!/usr/env/bin bash
set -e

target_dir="$PWD/mirror"
upstream_server_url="https://cdn.download.clearlinux.org"
latest_version=$(( "(curl -- "$upstream_server_url"/latest)" ))
manifest="$(curl -- "$upstream_server_url"/update/"$latest_version"/Manifest.MoM)"
version=$(( "$(echo "$manifest" | grep "^version:" | head -n 1 | awk -F ':' '{print $2}')" ))
minversion=$(( "$(echo "$manifest" | grep "^minversion:" | head -n 1 | awk -F ':' '{print $2}')" ))

unset manifest

cd -- "$target_dir"

names=(0 version "$version" "$minversion")

for name in "${names[@]}"
do
    wget --no-verbose --no-parent --recursive --no-host-directories -erobots=off --reject "index.html" "$upstream_server_url"/update/"$name"/
done
