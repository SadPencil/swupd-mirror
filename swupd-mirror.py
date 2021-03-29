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
            logging.warning('Warning: unrecognized url:' + link)

    return files_list


def download_version(version: str, target_dir: str) -> list:
    # note: `version` can be either a int or the literal string 'version'
    return get_files_list_recursive(upstream_server_url + '/update/' + version + '/', target_dir)


def download_with_wget(target_link: list,download_count: int):
    for i in range(2):
        # 
        if(os.system("wget -q --no-cache --limit-rate=2m -t 3 -N --directory-prefix "+str(target_link[1])+" "+str(target_link[0]))==0):
            break
    print(download_count)

def download_with_wget2(target_link: list,download_count: int):
    for i in range(2):
        # 
        if(os.system("wget2 -q --no-cache --limit-rate=2m -t 3 -N --directory-prefix "+str(target_link[1])+" "+str(target_link[0]))==0):
            break
    print(download_count)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', '-o', action='store',
                    dest='download_dir',
                    help=('directory you want download to. default:\'./\''),
                    default='./',
                    type=pathlib.Path)
    parser.add_argument('--use-wget2', action='store_true',
                    dest='use_wget2',
                    help=('use wget2 to download.'),
                    default=False)
    args=parser.parse_args()

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

    logging.info("min verion:" + str(min_version))

    files_list = []
    files_list.extend(
        download_version(str(0), str(args.download_dir)+'/update/'+str(0)+'/')
    )
    files_list.extend(
        download_version('version', str(args.download_dir)+'/update/version/')
    )
    files_list.extend(
        download_version(str(min_version), str(args.download_dir)+'/update/'+str(min_version)+'/')
    )
    files_list.extend(
        download_version(str(latest_version), str(args.download_dir)+'/update/'+str(latest_version)+'/')
    )

    logging.info(str(len(files_list)) + ' files to be downloaded.')
    time.sleep(3)

    #for link in files_list:
    #    print(link)
    
    download_count=0
    with ThreadPoolExecutor(24) as executor: # the number here is the threads count
        if(args.use_wget2):
            for link in files_list:
                download_count+=1
                executor.submit(download_with_wget2,link,download_count)
        else:
            for link in files_list:
                download_count+=1
                executor.submit(download_with_wget,link,download_count)

     

