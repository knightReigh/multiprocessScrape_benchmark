#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import codecs
import re
import sys
import os
import shutil
import itertools

import requests
from bs4 import BeautifulSoup
from datetime import datetime

import gevent.pool as pool
import gevent.monkey
gevent.monkey.patch_all()

Greenlet_size = 100
Headers = {'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/53.0.2785.143 Safari/537.36'}

def get_pageList(mid, headers):
    ''' input: (bilibili) mid
        output: A list containing page urls for all submitted videos
    '''
    pageSize = 30
    API= ('https://space.bilibili.com/ajax/member/getSubmitVideos?mid=%s' % str(mid)
            + '&pagesize=%s' % str(pageSize) + '&tid=0&page=%s&keyword=&order=pubdate' )
    pageNum = 0
    itemNum = 0

    # get pageNum
    try:
        r = requests.get((API % '1'), headers=headers)
        if r.status_code == 200:
            json_content = r.json()
            tlist = json_content['data']['tlist']
            itemNum = sum([int(tlist[tab]['count']) for tab in tlist])
            pageNum = int(itemNum/pageSize) + (itemNum % pageSize > 0)
    except Exception as e:
        print(e)
        sys.exit

    # get page list
    API_list = [(API % str(page)) for page in range(1, pageNum + 1)]
    return [API_list, itemNum]

def get_singlePage_session(params):

    page_url, session = params

    try:
        r = session.get(page_url)
        json_content = r.json()
        vlist = json_content['data']['vlist']
        records = []
        for video in vlist:
            title = video['title']
            aid = video['aid']
            url = "https://www.bilibili.com/video/av" + str(aid)
            records.append({'title':title, 'aid': aid, 'url': url})
    except Exception as e:
        print(e)
        sys.exit

    return records

def parse_gevent_session(API_list, numProcess, headers):
    p = pool.Pool(numProcess)
    s = requests.session()
    s.headers.update(headers)
    result = p.map(get_singlePage_session, zip(API_list, [ s ] * len(API_list)))
    p.join()
    s.close()
    return result


def crawlRawData(mid, numProcess=Greenlet_size):
    [API_list, itemNum] = get_pageList(mid, Headers)
    result = parse_gevent_session(API_list, numProcess, Headers)

    result = list(itertools.chain(*result))
    return [result, itemNum]

def get_TeamXStream():
    mid = 37694382
    [crawlData, itemNum] = crawlRawData(mid)
    print("Raw Crawl finished.")

    extra_id = []
    extra_urls = []
    streamData = []

    count = 0
    for i in range(len(crawlData)):
        title = crawlData[i]['title']
        url = crawlData[i]['url']

        if "口袋48" in title and "直播" in title:
            title = remove_nbws(title.strip())
            date = date_extractor(title)
            title = (title.replace('【SNH48】', '').replace('TeamX', '').strip()
                     + ' (' + date + ')')
            streamData.append({'title': title, 'url': url, 'date': date})
            if not date:
                extra_id.append(count)
                extra_urls.append(url)

            count += 1

    print('%s more urls to crawl.' % len(extra_urls))
    s = requests.Session()
    s.headers.update(Headers)
    p = pool.Pool(Greenlet_size)

    extra_records = p.map(s.get, extra_urls)
    p.join()
    s.close()

    for i in range(len(extra_records)):
        r = extra_records[i]
        if r.status_code == 200:
            soup = BeautifulSoup(r.content, 'lxml')
            date = soup.find('meta', {'itemprop':'uploadDate'})['content'][:10]
            streamData[extra_id[i]]['date'] = date
        else:
            streamData[extra_id[i]]['date'] = datetime.now().strftime('%Y-%m-%d')

        streamData[extra_id[i]]['title'] = streamData[extra_id[i]]['title'] + ' (' + streamData[extra_id[i]]['date'] + ')'


    print_md(streamData)
    print_txt(streamData)

def print_md(streamData):
    with codecs.open('直播.md', 'w', encoding='utf-8') as f:
        f.write(codecs.BOM_UTF8.decode('utf-8'))
        for video in streamData:
            line = '[' + str(video['title']) + '](' + str(video['url']) + ')'
            f.write(line + os.linesep)

def print_txt(streamData):
    with codecs.open('直播.txt', 'w', encoding='utf-8') as f:
        f.write(codecs.BOM_UTF8.decode('utf-8'))
        f.write('直播' + os.linesep + os.linesep)
        for video in streamData:
            line = str(video['title']) + os.linesep + str(video['url']) + os.linesep + os.linesep
            f.write(line)

def date_extractor(arbString):
    if  re.search(r'\d*年\d*月\d*日',arbString):
        date = re.search(r'\d*年\d*月\d*日',arbString).group(0)
        Y = re.search(r'\d*年',date).group(0)[:-1]
        m = re.search(r'年\d*月',date).group(0)[1:-1]
        d =  re.search(r'月\d*日',date).group(0)[1:-1]
        if len(Y) == 2:
            Y = '20' + Y
        if len(m) == 1:
            m = '0' + m
        if len(d) == 1:
            d = '0' + d
        date = Y + '-' + m + '-' + d
    elif re.search(r'\d{6}',arbString):
        date = re.search(r'\d{6}',arbString).group(0)
        date = '20' + date[:2] + '-' + date[2:4] + '-' + date[4:6]
    else:
        date = "" # last resolve

    return date

def remove_nbws(text):
    """ remove unwanted unicode punctuation: zwsp, nbws, \t, \r, \r.
    """

    # ZWSP: Zero width space
    text = text.replace(u'\u200B', '')
    # NBWS: Non-breaking space
    text = text.replace(u'\xa0', ' ')
    # HalfWidth fullstop
    text = text.replace(u'\uff61', '')
    # Bullet
    text = text.replace(u'\u2022', '')
    # White space
    text = text.replace(u'\t', ' ').replace(u'\r', ' ')

    #text = text.replace(u'\u7B60','菌')

    # General Punctuation
    gpc_pattern = re.compile(r'[\u2000-\u206F]')
    text = gpc_pattern.sub('', text)

    # Mathematical Operator
    mop_pattern = re.compile(r'[\u2200-\u22FF]')
    text = mop_pattern.sub('', text)

    # Combining Diacritical Marks
    dcm_pattern = re.compile(r'[\u0300-\u036F]')
    text = dcm_pattern.sub('', text)

    lsp_pattern = re.compile(r'[\x80-\xFF]')
    text = lsp_pattern.sub('', text)

    text = re.sub(r'\s+', ' ', text)

    return text