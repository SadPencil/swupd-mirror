import argparse
import logging
from urllib.parse import urljoin
from bs4 import BeautifulSoup
import os
import pathlib
import urllib3
import time
from typing import List, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

# TODO make these variables as command line arguments with default values
upstream_server_url = 'https://cdn.download.clearlinux.org'
upstream_server_host = 'cdn.download.clearlinux.org'
upstream_server_port = 443

# TODO make these variables as command line arguments with default values
chunk_size = 1048576
max_thread = 24
retry_count = 3
http_timeout = 10

http = urllib3.HTTPSConnectionPool(
    host=upstream_server_host,
    port=upstream_server_port,
    timeout=http_timeout,
    maxsize=max_thread,
    retries=urllib3.util.Retry(total=retry_count),
    block=True,
)


def remove_suffix(s: str, suffix: str) -> str:
    if not s.endswith(suffix):
        return s
    return s[:-len(suffix)]


def remove_prefix(s: str, prefix: str) -> str:
    if not s.startswith(prefix):
        return s
    return s[len(prefix):]


def http_get_content(url: str) -> bytes:
    response = http.request(method='GET', url=url)
    if response.status != 200:
        raise Exception('HTTP status code {}'.format(response.status_code))
    return response.data


def http_get_text(url: str) -> str:
    data = http_get_content(url)
    return data.decode(encoding='utf-8', errors='strict')


def http_get_int(url: str) -> int:
    text = http_get_text(url)
    return int(text)


def get_file_list(url: str, target_dir: str, filename: str) -> Tuple[str, str, str]:
    return url, target_dir, filename


def get_files_list_recursive(
        url: str,
        target_dir: str,
        executor: ThreadPoolExecutor = None) -> List[Tuple[str, str, str]]:
    files_list = []
    folders_and_destinations_list = []

    logging.info('Retrieving file list from folder: ' + url)

    content = http_get_text(url)
    soup = BeautifulSoup(content, features="html.parser")
    links = soup.find_all('a')

    # TODO: (less important) parsing large HTML consumes lots of CPU time

    for tag in links:
        link = tag.get('href', None)
        if link is None:
            continue

        # possible relative url -> absolute url
        link = urljoin(url, link)

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
            folders_and_destinations_list.append(
                (link, os.path.join(target_dir, remove_suffix(link_tail, '/')))
            )
        else:
            logging.warning('Warning: ignored unrecognized url: ' + link)

    if executor is None:
        for (folder_url, destination_dir) in folders_and_destinations_list:
            files_list_sub = get_files_list_recursive(folder_url, destination_dir)
            files_list.extend(files_list_sub)
    else:
        futures = [
            executor.submit(get_files_list_recursive, folder_url, destination_dir, executor=executor)
            for (folder_url, destination_dir) in folders_and_destinations_list]

        for future in as_completed(futures):
            result = future.result()
            files_list.extend(result)

    return files_list


def get_files_list_of_version(
        version: str,
        target_root_dir: str,
        executor: ThreadPoolExecutor = None) -> List[Tuple[str, str, str]]:
    # note: `version` can be either an integer string or the literal string 'version'
    return get_files_list_recursive(
        upstream_server_url + '/update/' + version + '/',
        target_root_dir + '/update/' + version + '/',
        executor=executor)


def download_file(target_link: Tuple[str, str, str], skip_on_exists: bool = True, display_message: str = '') -> None:
    url, target_dir, filename = target_link

    if len(display_message) != 0:
        logging.info(display_message)

    if pathlib.Path(target_dir).exists():
        if pathlib.Path(target_dir).is_dir():
            pass
        else:
            raise Exception(target_dir + ' is supposed to be a directory, not something else.')
    else:
        os.makedirs(target_dir)

    file_path = os.path.join(target_dir, filename)
    file_path_downloading = file_path + '.downloading'

    if pathlib.Path(file_path).exists():
        if skip_on_exists:
            return

    with open(file_path_downloading, 'wb') as file:
        with http.request('GET', url, preload_content=False) as request:
            for chunk in request.stream(chunk_size):
                file.write(chunk)
            request.release_conn()
    os.replace(src=file_path_downloading, dst=file_path)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--out', '-o',
        action='store',
        dest='download_dir',
        help='the destination directory',
        required=True,
        type=pathlib.Path,
    )

    parser.add_argument(
        '--verbose', '-v',
        action='store_false',
        dest='no_verbose',
        help='verbose mode',
    )

    # TODO add other parameters

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO if args.no_verbose else logging.DEBUG,
        format="%(levelname)s: %(message)s",
    )

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

    with ThreadPoolExecutor(max_workers=max_thread) as executor:
        files_list.extend(
            get_files_list_of_version(
                str(0),
                str(args.download_dir),
                executor=executor)
        )
        files_list.extend(
            get_files_list_of_version(
                'version',
                str(args.download_dir),
                executor=executor)
        )
        files_list.extend(
            get_files_list_of_version(
                str(min_version),
                str(args.download_dir),
                executor=executor)
        )
        files_list.extend(
            get_files_list_of_version(
                str(latest_version),
                str(args.download_dir),
                executor=executor)
        )

    files_count = len(files_list)
    logging.info(str(files_count) + ' files to be downloaded.')

    time.sleep(3)

    # TODO feature: extract, other than download a file if the corresponding .gz file exists

    with ThreadPoolExecutor(max_workers=max_thread) as executor:
        for i in range(files_count):
            future = executor.submit(
                download_file,
                files_list[i],
                display_message='Downloading, {} of {}'.format(i, files_count)
            )

    # TODO handle SIGINT and SIGTERM
