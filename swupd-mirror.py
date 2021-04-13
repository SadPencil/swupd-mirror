import argparse
import logging
import requests
import urllib.request
from bs4 import BeautifulSoup
import os
import pathlib
import urllib
import sys
import time
from typing import List, Tuple

from concurrent.futures import ThreadPoolExecutor

upstream_server_url = 'https://cdn.download.clearlinux.org'

_session = requests.Session()


def remove_suffix(s: str, suffix: str) -> str:
    if not s.endswith(suffix):
        return s
    return s[:-len(suffix)]


def remove_prefix(s: str, prefix: str) -> str:
    if not s.startswith(prefix):
        return s
    return s[len(prefix):]


def http_get_content(url: str) -> bytes:
    response = _session.get(url)
    if response.status_code != 200:
        raise Exception('HTTP status code {}'.format(response.status_code))
    return response.content


def http_get_text(url: str) -> str:
    response = _session.get(url)
    if response.status_code != 200:
        raise Exception('HTTP status code {}'.format(response.status_code))
    return response.text


def http_get_int(url: str) -> int:
    content = http_get_text(url)
    return int(content)


def get_file_list(url: str, target_dir: str, filename: str) -> Tuple[str, str, str]:
    return url, target_dir, filename


def get_files_list_recursive(url: str, target_dir: str) -> List[Tuple[str, str, str]]:
    files_list = []

    logging.info('Retrieving file list from folder: ' + url)

    content = http_get_text(url)
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
        link_tail = remove_prefix(str(link), url)
        if len(link_tail) == 0:
            continue
        if link_tail.count('/') == 0:
            # file
            files_list_item = get_file_list(link, target_dir, link_tail)
            files_list.append(files_list_item)
        elif link_tail.endswith('/') and link_tail.count('/') == 1:
            # folder
            files_list_sub = get_files_list_recursive(link, os.path.join(target_dir, remove_suffix(link_tail, '/')))
            files_list.extend(files_list_sub)
        else:
            logging.warning('Warning: ignored unrecognized url: ' + link)

    return files_list


def get_files_list_of_version(version: str, target_dir: str) -> List[Tuple[str, str, str]]:
    # note: `version` can be either an integer string or the literal string 'version'
    return get_files_list_recursive(upstream_server_url + '/update/' + version + '/', target_dir)


def download_with_wget(target_link: Tuple[str, str, str], retry_count: int = 3, display_message: str = '') -> bool:
    if len(display_message) != 0:
        logging.info(display_message)

    for _ in range(retry_count):
        # TODO escape the url and the folder path
        exit_code = os.system(
            "wget -q --no-cache --limit-rate=2m -t 3 -N --directory-prefix " + str(target_link[1]) + " " + str(
                target_link[0]))
        if exit_code == 0:
            return True
        else:
            logging.warning("Warning: failed to download file at: " + target_link[1] + ", retrying...")
    raise Exception("Failed to download file at: " + target_link[1])


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', '-o', action='store',
                        dest='download_dir',
                        help='the destination directory',
                        required=True,
                        type=pathlib.Path)

    # TODO add number of thread count
    # TODO add retry times
    # TODO add arg upstream server

    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG, format="%(levelname)s: %(message)s")

    latest_version = http_get_int(upstream_server_url + '/latest')
    logging.info("latest version:" + str(latest_version))

    manifest = http_get_text(upstream_server_url + '/update/' + str(latest_version) + '/Manifest.MoM')
    min_version = 0
    for line in manifest.split('\n'):
        if line.startswith('version:'):
            version = int(remove_prefix(line, 'version:'))
            if version != latest_version:
                raise Exception('Unexpected manifest "version" field')
        elif line.startswith('minversion:'):
            min_version = int(remove_prefix(line, 'minversion:'))
            if min_version > latest_version or min_version < 0:
                raise Exception('Unexpected manifest "minversion" field')

    logging.info("min version:" + str(min_version))

    time.sleep(3)

    files_list = []
    files_list.extend(
        get_files_list_of_version(str(0), str(args.download_dir) + '/update/' + str(0) + '/')
    )
    files_list.extend(
        get_files_list_of_version('version', str(args.download_dir) + '/update/version/')
    )
    files_list.extend(
        get_files_list_of_version(str(min_version), str(args.download_dir) + '/update/' + str(min_version) + '/')
    )
    files_list.extend(
        get_files_list_of_version(str(latest_version), str(args.download_dir) + '/update/' + str(latest_version) + '/')
    )

    files_count = len(files_list)
    logging.info(str(files_count) + ' files to be downloaded.')

    time.sleep(3)

    retry_count = 3
    worker_count = 42

    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        for i in range(files_count):
            future = executor.submit(
                download_with_wget,
                files_list[i],
                retry_count=retry_count,
                display_message='Downloading, {} of {}'.format(i, files_count)
            )

    # TODO handle SIGINT and SIGTERM
