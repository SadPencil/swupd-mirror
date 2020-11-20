#!/usr/bin/env bash
set -e

target_dir="$PWD/mirror"
upstream_server_url="https://cdn.download.clearlinux.org"

_version=v0.1
echo "swupd-mirror $_version"
echo "get the metadata from the upstream server..."

latest_version=$( curl -- "$upstream_server_url"/latest | sed -e 's/^[[:space:]]*//g' -e 's/[[:space:]]*$//g' )
[[ "$latest_version" == ?(-)+([0-9]) ]] || ( echo "unexpected content: latest_version is not a number." 1>&2 ; exit 1 ) || exit 1
echo "latest version: $latest_version"

manifest="$( curl -- "$upstream_server_url"/update/"$latest_version"/Manifest.MoM )"
version=$( echo "$manifest" | grep "^version:" | head -n 1 | awk -F ':' '{print $2}' | sed -e 's/^[[:space:]]*//g' -e 's/[[:space:]]*$//g' )
minversion=$( echo "$manifest" | grep "^minversion:" | head -n 1 | awk -F ':' '{print $2}' | sed -e 's/^[[:space:]]*//g' -e 's/[[:space:]]*$//g' )

[[ "$version" == ?(-)+([0-9]) ]] || ( echo "unexpected manifest: version is not a number." 1>&2 ; exit 1 ) || exit 1
[[ "$minversion" == ?(-)+([0-9]) ]] || ( echo "unexpected manifest: minversion is not a number." 1>&2 ; exit 1 ) || exit 1

[ "$version" = "$latest_version" ] || ( echo "unexpected manifest: version mismatch." 1>&2 ; exit 1 ) || exit 1

unset manifest
unset version

echo "min version: $minversion"

echo "download files..."

cd -- "$target_dir"

names=(0 version "$latest_version" "$minversion")

for name in "${names[@]}"; do
  wget --no-verbose \
    --no-parent \
    --recursive \
    --no-host-directories \
    -e robots=off \
    --reject "index.html" \
    --report-speed=bits \
    --continue \
    --progress=bar \
    --timestamping \
    --timeout=30 \
    --retry-connrefused \
    --unlink \
    "$upstream_server_url"/update/"$name"/
done
