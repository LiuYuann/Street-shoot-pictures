"""大概用时23.986048221588135,18.475126266479492"""

import requests
import os
from urllib.parse import urlencode
from pyquery import PyQuery as pq
from pymongo import MongoClient
from multiprocessing import Pool
from time import time
from hashlib import md5
import re
import json

base_url = 'https://www.toutiao.com/search_content/?'
headers = {
    'Referer': 'https://www.toutiao.com/search/?keyword=%E8%A1%97%E6%8B%8D',
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36',
}
client = MongoClient()
db = client['jiepai']
collection = db['jiepai']

max_page = 7


def get_page(offset):
    params = {
        'offset': offset,
        'format': 'json',
        'autoload': 'true',
        'count': '20',
        'cur_tab': 1,
        'form': 'search_tab',
        'keyword': '街拍'
    }
    url = base_url + urlencode(params)
    try:
        response = requests.get(url=url)
        if response.status_code == 200:
            return response.json()
    except requests.ConnectionError as e:
        print('Error', e.args)


def parse_page(json):
    if json:
        items = json.get('data')
        for item in items:
            if item.get('has_image'):
                if re.search(r'(toutiao)', str(item.get('article_url'))):
                    jiepai = {}
                    jiepai['article_url'] = item.get('article_url')
                    jiepai['has_gallery'] = item.get('has_gallery')
                    jiepai['has_video'] = item.get('has_video')
                    jiepai['id'] = item.get('id')
                    yield jiepai


def parse_gallerypage(result, id):
    try:
        response = requests.get(url=result, headers=headers)
        if response.status_code == 200:
            html = response.text

            d = re.search(r'gallery: JSON.parse\("(\{.*?\})"\)', html).group(1)
            m1 = re.sub('(\\\\)', '', d)
            m2 = re.sub(',"sub_abstracts.*?]', '', m1)
            m3 = re.sub(',"sub_titles.*?]', '', m2)
            dd = json.loads(m3)
            data = {}
            img_url = []
            for i in dd.get('sub_images'):
                img_url.append(i['url'])
            doc = pq(html)
            data['title'] = doc.find('title').text()
            data['img_url'] = img_url
            data['_id'] = id
            return data
    except requests.ConnectionError as e:
        print('Error', e.args)


def parse_nogallerypage(result, id):
    try:
        response = requests.get(url=result, headers=headers)
        data = {}
        if response.status_code == 200:
            html = response.text
            doc = pq(html)
            d = re.findall("content: '(.*?)',", html)[0]
            img_url = re.findall("quot;(http.*?)&quot", d)
            data['_id'] = id
            data['title'] = doc.find('title').text()
            data['img_url'] = img_url
            return data
    except requests.ConnectionError as e:
        print('Error', e.args)


def save_to_mongo(result):
    try:
        if collection.insert(result):
            print('Saved to Mongo')
    except pymongo.errors.DuplicateKeyError as e:
        print('Error', e.args)

def download_image(item):
    if not os.path.exists(item.get('title')):
        os.mkdir(item.get('title'))
    try:
        for url in item.get('img_url'):
            response=requests.get(url)
            if response.status_code==200:
                file_path='{0}/{1}.{2}'.format(item.get('title'),md5(response.content).hexdigest(),'jpg')
                if not os.path.exists(file_path):
                    with open(file_path,'wb')as f:
                        f.write(response.content)
                else:
                    print('Already downloaded!!!')
    except requests.ConnectionError:
        print("Downloading failed!!!")

def main(offset):
    print(offset)
    p = get_page(offset)
    results = parse_page(p)
    data={}
    for result in results:
        if result.get('has_gallery'):
            data = parse_gallerypage(result['article_url'], result['id'])
        elif not result.get('has_video'):
            data = parse_nogallerypage(result['article_url'], result['id'])
        if data:
            print(result['article_url'])
            # save_to_mongo(data)#存入数据库
            download_image(data)
            # print(data)
            data = None


if __name__ == '__main__':
    ago=time()
    if not os.path.exists('img'):
        os.mkdir('img')
    os.chdir('./img')
    pool = Pool()
    groups = ([x*20 for x in range(0, max_page)])
    pool.map(main, groups)
    pool.close()
    pool.join()
    print("用时",time()-ago)
    # cursor = collection.find()
    # for item in cursor:
    #     print(item)
    # collection.remove({'title':{'$exists':True}})
    # print(cursor.count())  # 获取文档个数
