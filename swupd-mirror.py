import urllib.request
from bs4 import BeautifulSoup
import os
from pathlib import Path

upstream_server_url = 'https://cdn.download.clearlinux.org'


def get_content(url: str) -> bytes:
    response = urllib.request.urlopen(url)
    if response.status != 200:
        raise Exception('HTTP status code {}'.format(response.status))
    return response.read()


def get_utf8_str(url: str) -> str:
    content = get_content(url)
    return content.decode('utf-8')


def get_int(url: str) -> int:
    content = get_utf8_str(url)
    return int(content)


def download_file(url: str, target_dir: str, filename: str) -> None:
    assert Path(target_dir).exists()
    assert Path(target_dir).is_dir()
    # todo use a pool to manage download
    urllib.request.urlretrieve(url, os.path.join(target_dir, filename))


def download_files_recursive(url: str, target_dir: str) -> None:
    if Path(target_dir).exists():
        if Path(target_dir).is_dir():
            pass
        else:
            raise Exception(target_dir + ' is supposed to be a directory, not something else')
    else:
        os.makedirs(target_dir)

    content = get_utf8_str(url)
    soup = BeautifulSoup(content)
    links = soup.find_all('a')

    for tag in links:
        link = tag.get('href', None)

        if link is not None:
            if str(link).startswith(url):
                # is a folder or a file?
                link_tail = str(link).removeprefix(url)

                if link_tail.count('/') == 0:
                    # file
                    download_file(link, target_dir, link_tail)
                elif link_tail.endswith('/') and link_tail.count('/') == 1:
                    # folder
                    download_files_recursive(link, os.path.join(target_dir, link_tail.removesuffix('/')))
                else:
                    print("Warning: unrecognized url", link)


def download_version(version: str) -> None:
    # note: `version` can be either a int or the literal string 'version'

    content = get_utf8_str(upstream_server_url + '/update/' + version + '/')
    soup = BeautifulSoup(content)
    links = soup.find_all('a')

    for tag in links:
        link = tag.get('href', None)
        if link is not None:
            print(link)
    pass


if __name__ == '__main__':

    latest_version = get_int(upstream_server_url + '/latest')
    print("latest version:", latest_version)

    manifest = get_utf8_str(upstream_server_url + '/update/' + str(latest_version) + '/Manifest.MoM')
    min_version = 0
    for line in manifest.split('\n'):
        if line.startswith('version:'):
            version = int(line.removeprefix('version:'))
            if version != latest_version:
                raise Exception('Unexpected manifest "version" field')
        elif line.startswith('minversion:'):
            min_version = int(line.removeprefix('minversion:'))
            if min_version > latest_version or min_version < 0:
                raise Exception('Unexpected manifest "minversion" field')

    download_version(str(0))
    download_version('version')
    for version in range(min_version, latest_version + 1):
        download_version(str(version))
