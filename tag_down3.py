import httpx
import asyncio
import re
import os
import csv
import time
import json
import hashlib
from datetime import datetime
from urllib.parse import quote
from url_utils import quote_url
from tqdm.asyncio import tqdm

# 辅助函数
def del_special_char(string):
    """移除字符串中的特殊字符，只保留中文、字母、数字、#和日文字符"""
    string = re.sub(r'[^#\u4e00-\u9fa5\u0030-\u0039\u0041-\u005a\u0061-\u007a\u3040-\u31FF\.]', '', string)
    return string

def stamp2time(msecs_stamp: int) -> str:
    """将时间戳转换为格式化的日期时间字符串"""
    timeArray = time.localtime(msecs_stamp / 1000)
    return time.strftime("%Y-%m-%d %H-%M", timeArray)

def hash_save_token(media_url):
    """根据媒体 URL 生成短哈希值，用于文件名"""
    m = hashlib.md5()
    m.update(f'{media_url}'.encode('utf-8'))
    return m.hexdigest()[:4]

def get_heighest_video_quality(variants) -> str:
    """从视频变体中选择最高质量的 URL"""
    if len(variants) == 1:  # GIF 适配
        return variants[0]['url']
    max_bitrate = 0
    heighest_url = None
    for i in variants:
        if 'bitrate' in i and int(i['bitrate']) > max_bitrate:
            max_bitrate = int(i['bitrate'])
            heighest_url = i['url']
    return heighest_url

# CSV 生成类
class csv_gen:
    def __init__(self, save_path: str, text_down: bool) -> None:
        self.f = open(f'{save_path}/{datetime.now().strftime("%Y-%m-%d %H-%M-%S")}-mode.csv', 'w', encoding='utf-8-sig', newline='')
        self.writer = csv.writer(self.f)
        self.writer.writerow(['Run Time : ' + datetime.now().strftime('%Y-%m-%d %H-%M-%S')])
        if text_down:
            main_par = ['Tweet Date', 'Display Name', 'User Name', 'Tweet URL', 'Tweet Content', 
                        'Favorite Count', 'Retweet Count', 'Reply Count']
        else:
            main_par = ['Tweet Date', 'Display Name', 'User Name', 'Tweet URL', 'Media Type', 
                        'Media URL', 'Saved Path', 'Tweet Content', 'Favorite Count', 
                        'Retweet Count', 'Reply Count']
        self.writer.writerow(main_par)

    def csv_close(self):
        """关闭 CSV 文件"""
        self.f.close()

    def stamp2time(self, msecs_stamp: int) -> str:
        """将时间戳转换为格式化的日期时间字符串"""
        timeArray = time.localtime(msecs_stamp / 1000)
        return time.strftime("%Y-%m-%d %H:%M", timeArray)

    def data_input(self, main_par_info: list) -> None:
        """向 CSV 文件写入一行数据"""
        main_par_info[0] = self.stamp2time(main_par_info[0])
        self.writer.writerow(main_par_info)

# 异步下载控制函数
async def download_control(media_lst, csv_instance, max_concurrent_requests):
    """控制并发下载媒体文件"""
    semaphore = asyncio.Semaphore(max_concurrent_requests)

    async def down_save(url, _csv_info, is_image):
        """下载单个媒体文件并保存"""
        if is_image:
            url += '?format=png&name=4096x4096'
        count = 0
        while True:
            try:
                async with semaphore:
                    async with httpx.AsyncClient() as client:
                        response = await client.get(quote_url(url), timeout=(3.05, 16))
                with open(_csv_info[6], 'wb') as f:
                    f.write(response.content)
                break
            except Exception as e:
                count += 1
                print(f'{_csv_info[6]}=====>第{count}次下载失败,正在重试')

        csv_instance.data_input(_csv_info)

    tasks = [down_save(url, info, is_image) for url, info, is_image in media_lst]
    for coro in tqdm(asyncio.as_completed(tasks), total=len(tasks), desc="下载进度"):
        await coro

# 异步搜索函数
async def search_media(url, headers, cursor, folder_path):
    """搜索媒体（图片/视频）并提取信息"""
    media_lst = []
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)
    raw_data = json.loads(response.text)
    if not cursor:
        raw_data = raw_data['data']['search_by_raw_query']['search_timeline']['timeline']['instructions'][-1]['entries']
        if len(raw_data) == 2:
            return None, media_lst
        cursor = raw_data[-1]['content']['value']
        raw_data_lst = raw_data[0]['content']['items']
    else:
        raw_data = raw_data['data']['search_by_raw_query']['search_timeline']['timeline']['instructions']
        cursor = raw_data[-1]['entry']['content']['value']
        if 'moduleItems' in raw_data[0]:
            raw_data_lst = raw_data[0]['moduleItems']
        else:
            return None, media_lst

    for tweet in raw_data_lst:
        tweet = tweet['item']['itemContent']['tweet_results']['result']
        try:
            display_name = tweet['core']['user_results']['result']['legacy']['name']
            screen_name = '@' + tweet['core']['user_results']['result']['legacy']['screen_name']
            time_stamp = int(tweet['edit_control']['editable_until_msecs']) - 3600000
            Favorite_Count = tweet['legacy']['favorite_count']
            Retweet_Count = tweet['legacy']['retweet_count']
            Reply_Count = tweet['legacy']['reply_count']
            _status_id = tweet['legacy']['conversation_id_str']
            tweet_url = f'https://twitter.com/{screen_name}/status/{_status_id}'
            tweet_content = tweet['legacy']['full_text'].split('https://t.co/')[0]
        except Exception:
            continue

        try:
            raw_media_lst = tweet['legacy']['extended_entities']['media']
            for _media in raw_media_lst:
                if 'video_info' in _media:
                    media_url = get_heighest_video_quality(_media['video_info']['variants'])
                    media_type = 'Video'
                    is_image = False
                    _file_name = f'{folder_path}{stamp2time(time_stamp)}_{screen_name}_{hash_save_token(media_url)}.mp4'
                else:
                    media_url = _media['media_url_https']
                    media_type = 'Image'
                    is_image = True
                    _file_name = f'{folder_path}{stamp2time(time_stamp)}_{screen_name}_{hash_save_token(media_url)}.png'
                media_csv_info = [time_stamp, display_name, screen_name, tweet_url, media_type, media_url, _file_name, 
                                  tweet_content, Favorite_Count, Retweet_Count, Reply_Count]
                media_lst.append([media_url, media_csv_info, is_image])
        except Exception:
            continue
    return cursor, media_lst

async def search_media_latest(url, headers, cursor, folder_path):
    """搜索最新的媒体内容"""
    media_lst = []
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)
    raw_data = json.loads(response.text)
    if not cursor:
        raw_data = raw_data['data']['search_by_raw_query']['search_timeline']['timeline']['instructions'][-1]['entries']
        if len(raw_data) == 2:
            return None, media_lst
        cursor = raw_data[-1]['content']['value']
        raw_data_lst = raw_data[:-2]
    else:
        raw_data = raw_data['data']['search_by_raw_query']['search_timeline']['timeline']['instructions']
        cursor = raw_data[-1]['entry']['content']['value']
        if 'entries' in raw_data[0]:
            raw_data_lst = raw_data[0]['entries']
        else:
            return None, media_lst

    for tweet in raw_data_lst:
        if 'promoted' in tweet['entryId']:
            continue
        tweet = tweet['content']['itemContent']['tweet_results']['result']
        try:
            display_name = tweet['core']['user_results']['result']['legacy']['name']
            screen_name = '@' + tweet['core']['user_results']['result']['legacy']['screen_name']
            time_stamp = int(tweet['edit_control']['editable_until_msecs']) - 3600000
            Favorite_Count = tweet['legacy']['favorite_count']
            Retweet_Count = tweet['legacy']['retweet_count']
            Reply_Count = tweet['legacy']['reply_count']
            _status_id = tweet['legacy']['conversation_id_str']
            tweet_url = f'https://twitter.com/{screen_name}/status/{_status_id}'
            tweet_content = tweet['legacy']['full_text'].split('https://t.co/')[0]
        except Exception:
            continue

        try:
            raw_media_lst = tweet['legacy']['extended_entities']['media']
            for _media in raw_media_lst:
                if 'video_info' in _media:
                    media_url = get_heighest_video_quality(_media['video_info']['variants'])
                    media_type = 'Video'
                    is_image = False
                    _file_name = f'{folder_path}{stamp2time(time_stamp)}_{screen_name}_{hash_save_token(media_url)}.mp4'
                else:
                    media_url = _media['media_url_https']
                    media_type = 'Image'
                    is_image = True
                    _file_name = f'{folder_path}{stamp2time(time_stamp)}_{screen_name}_{hash_save_token(media_url)}.png'
                media_csv_info = [time_stamp, display_name, screen_name, tweet_url, media_type, media_url, _file_name, 
                                  tweet_content, Favorite_Count, Retweet_Count, Reply_Count]
                media_lst.append([media_url, media_csv_info, is_image])
        except Exception:
            continue
    return cursor, media_lst

async def search_save_text(url, headers, csv_instance, cursor):
    """搜索并保存文本内容到 CSV"""
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)
    raw_data = json.loads(response.text)
    if not cursor:
        raw_data = raw_data['data']['search_by_raw_query']['search_timeline']['timeline']['instructions'][-1]['entries']
        if len(raw_data) == 2:
            return None
        cursor = raw_data[-1]['content']['value']
        raw_data_lst = raw_data[:-2]
    else:
        raw_data = raw_data['data']['search_by_raw_query']['search_timeline']['timeline']['instructions']
        cursor = raw_data[-1]['entry']['content']['value']
        if len(raw_data) == 2:
            return None
        raw_data_lst = raw_data[0]['entries']

    for tweet in raw_data_lst:
        if 'promoted' in tweet['entryId']:
            continue
        tweet = tweet['content']['itemContent']['tweet_results']['result']
        if 'tweet' in tweet and 'edit_control' in tweet['tweet']:
            tweet = tweet['tweet']
        try:
            time_stamp = int(tweet['edit_control']['editable_until_msecs']) - 3600000
            display_name = tweet['core']['user_results']['result']['legacy']['name']
            screen_name = '@' + tweet['core']['user_results']['result']['legacy']['screen_name']
            Favorite_Count = tweet['legacy']['favorite_count']
            Retweet_Count = tweet['legacy']['retweet_count']
            Reply_Count = tweet['legacy']['reply_count']
            _status_id = tweet['legacy']['conversation_id_str']
            tweet_url = f'https://twitter.com/{screen_name}/status/{_status_id}'
            tweet_content = tweet['legacy']['full_text'].split('https://t.co/')[0]
            csv_instance.data_input([time_stamp, display_name, screen_name, tweet_url, tweet_content, Favorite_Count, 
                                     Retweet_Count, Reply_Count])
        except Exception:
            continue
    return cursor

# 主函数
async def run_tag_down(cookie, tag, _filter, down_count, media_latest, text_down, max_concurrent_requests=8):
    """
    运行标签下载任务
    
    参数:
        cookie: Twitter 的 Cookie
        tag: 搜索标签
        _filter: 搜索过滤器
        down_count: 下载条目数
        media_latest: 是否搜索最新媒体
        text_down: 是否仅下载文本
        max_concurrent_requests: 最大并发请求数
    
    返回:
        dict: 包含保存路径和 CSV 文件路径
    """
    if text_down:
        entries_count = 20
        product = 'Latest'
        mode = 'text'
    else:
        entries_count = 50
        product = 'Media'
        mode = 'media'
        if media_latest:
            entries_count = 20
            product = 'Latest'
            mode = 'media_latest'
    _filter = ' ' + _filter

    # 定义保存路径，只定义一次
    folder_path = os.getcwd() + os.sep + (del_special_char(tag) if tag else del_special_char(_filter)) + os.sep
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)

    # 实例化 csv_gen，确保传递 text_down 参数
    csv_instance = csv_gen(folder_path, text_down)

    headers = {
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36',
        'authorization': 'Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA',
        'cookie': cookie,
        'x-csrf-token': re.findall(r'ct0=(.*?);', cookie)[0],
        'referer': f'https://twitter.com/search?q={quote(tag + _filter)}&src=typed_query&f=media'
    }

    cursor = ''
    for i in range(down_count // entries_count):
        url = f'https://twitter.com/i/api/graphql/tUJgNbJvuiieOXvq7OmHwA/SearchTimeline?variables={{"rawQuery":"{quote(tag + _filter)}","count":{entries_count},"cursor":"{cursor}","querySource":"typed_query","product":"{product}"}}&features={{"rweb_tipjar_consumption_enabled":true,"responsive_web_graphql_exclude_directive_enabled":true,"verified_phone_label_enabled":false,"creator_subscriptions_tweet_preview_api_enabled":true,"responsive_web_graphql_timeline_navigation_enabled":true,"responsive_web_graphql_skip_user_profile_image_extensions_enabled":false,"communities_web_enable_tweet_community_results_fetch":true,"c9s_tweet_anatomy_moderator_badge_enabled":true,"articles_preview_enabled":true,"tweetypie_unmention_optimization_enabled":true,"responsive_web_edit_tweet_api_enabled":true,"graphql_is_translatable_rweb_tweet_is_translatable_enabled":true,"view_counts_everywhere_api_enabled":true,"longform_notetweets_consumption_enabled":true,"responsive_web_twitter_article_tweet_consumption_enabled":true,"tweet_awards_web_tipping_enabled":false,"creator_subscriptions_quote_tweet_preview_enabled":false,"freedom_of_speech_not_reach_fetch_enabled":true,"standardized_nudges_misinfo":true,"tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled":true,"tweet_with_visibility_results_prefer_gql_media_interstitial_enabled":true,"rweb_video_timestamps_enabled":true,"longform_notetweets_rich_text_read_enabled":true,"longform_notetweets_inline_media_enabled":true,"responsive_web_enhance_cards_enabled":false}}'
        url = quote_url(url)

        if text_down:
            cursor = await search_save_text(url, headers, csv_instance, cursor)
            if not cursor:
                break
        else:
            cursor, media_lst = await (search_media_latest(url, headers, cursor, folder_path) if media_latest else search_media(url, headers, cursor, folder_path))
            if not media_lst:
                break
            await download_control(media_lst, csv_instance, max_concurrent_requests)

    csv_path = csv_instance.f.name
    csv_instance.csv_close()

    return {"folder_path": folder_path, "csv_path": csv_path}