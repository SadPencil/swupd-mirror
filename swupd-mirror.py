import logging
import requests
import urllib.request
from bs4 import BeautifulSoup
import os
import pathlib
import urllib

upstream_server_url = 'https://cdn.download.clearlinux.org'

_session = requests.Session()


def get_content(url: str) -> bytes:
    response = _session.get(url)
    if response.status_code != 200:
        raise Exception('HTTP status code {}'.format(response.status_code))
    return response.content


def get_utf8_str(url: str) -> str:
    content = get_content(url)
    return content.decode('utf-8')


def get_int(url: str) -> int:
    content = get_utf8_str(url)
    return int(content)


def get_file_list(url: str, target_dir: str, filename: str) -> tuple:
    return url, target_dir, filename

    # assert pathlib.Path(target_dir).exists()
    # assert pathlib.Path(target_dir).is_dir()
    # # todo use a pool to manage download
    # print('URL=', url, 'FILE=', os.path.join(target_dir, filename))
    # # urllib.request.urlretrieve(url, os.path.join(target_dir, filename))


def get_files_list_recursive(url: str, target_dir: str) -> list:
    files_list = []

    logging.info('Download folder from:' + url)

    # if pathlib.Path(target_dir).exists():
    #     if pathlib.Path(target_dir).is_dir():
    #         pass
    #     else:
    #         raise Exception(target_dir + ' is supposed to be a directory, not something else')
    # else:
    #     os.makedirs(target_dir)

    content = get_utf8_str(url)
    soup = BeautifulSoup(content, features="html.parser")
    links = soup.find_all('a')

    for tag in links:
        link = tag.get('href', None)
        if link is None:
            continue

        # possible relative url -> absolute url
        link = urllib.parse.urljoin(url, link)

        # no parent
        if not str(link).startswith(url):
            continue

        # is a folder or a file?
        link_tail = str(link).removeprefix(url)
        if len(link_tail) == 0:
            continue
        if link_tail.count('/') == 0:
            # file
            files_list_item = get_file_list(link, target_dir, link_tail)
            files_list.append(files_list_item)
        elif link_tail.endswith('/') and link_tail.count('/') == 1:
            # folder
            files_list_sub = get_files_list_recursive(link, os.path.join(target_dir, link_tail.removesuffix('/')))
            files_list.extend(files_list_sub)
        else:
            logging.warning('Warning: unrecognized url:' + link)

    return files_list


def download_version(version: str, target_dir: str) -> list:
    # note: `version` can be either a int or the literal string 'version'
    return get_files_list_recursive(upstream_server_url + '/update/' + version + '/', target_dir)


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, format="%(levelname)s: %(message)s")

    latest_version = get_int(upstream_server_url + '/latest')
    logging.info("latest version:" + str(latest_version))

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

    files_list = []
    files_list.extend(
        download_version(str(0), './test/')
    )
    files_list.extend(
        download_version('version', './test/')
    )
    files_list.extend(
        download_version(str(min_version), './test/')
    )
    files_list.extend(
        download_version(str(latest_version), './test/')
    )

    logging.info(str(len(files_list)) + ' files to be downloaded.')
