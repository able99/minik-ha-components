#! usr/bin/python
#coding=utf-8
import os
import sys
import voluptuous as vol
import logging
import threading
import homeassistant.helpers.config_validation as cv
from homeassistant.util import sanitize_filename
_LOGGER = logging.getLogger(__name__)


REQUIREMENTS = []


from homeassistant.const import (ATTR_ENTITY_ID)


DOMAIN = 'mbox'
CONF_PLAYLIST_DIR = 'playlist_dir'
CONF_MEDIA_DIR = 'media_dir'
CONF_MEDIA_PLAYER = 'media_player'
CONF_TTS_PLAYER = 'tts_player'
CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_PLAYLIST_DIR): cv.string,
        vol.Required(CONF_MEDIA_DIR): cv.string,
        vol.Optional(CONF_MEDIA_PLAYER): cv.entity_ids,
        vol.Optional(CONF_TTS_PLAYER): cv.entity_ids,
    }),
}, extra=vol.ALLOW_EXTRA)

SERVICE_MUSICBOX_PLAY = 'play'
ATTR_FILENAME = 'filename'
ATTR_NAME = 'name'
ATTR_TYPE = 'type'
ATTR_TYPE_SONG = 'song'
ATTR_TYPE_ARTIST = 'artist'
ATTR_TYPE_PLAYLIST = 'playlist'
ATTR_TYPE_ALBUM = 'album'
ATTR_TYPE_LOCAL = 'local'
ATTR_REPLACE = 'replace'
SERVICE_MUSICBOX_PLAY_SCHEMA = vol.Schema({
    vol.Optional(ATTR_NAME): cv.string,
    vol.Optional(ATTR_TYPE): vol.In([ATTR_TYPE_SONG, ATTR_TYPE_ARTIST, ATTR_TYPE_PLAYLIST, ATTR_TYPE_ALBUM, ATTR_TYPE_LOCAL]),
    vol.Optional(ATTR_FILENAME): cv.string,
    vol.Optional(ATTR_REPLACE): cv.boolean,
})

MEDIA_PLAYER_DOMAIN = 'media_player'
MEDIA_PLAYER_SERVICE_PLAY_MEDIA = 'play_media'
MEDIA_PLAYER_SERVICE_SELECT_SOURCE = 'select_source'
MEDIA_PLAYER_SERVICE_CLEAR_PLAYLIST = 'clear_playlist'
MEDIA_PLAYER_ATTR_INPUT_SOURCE = 'source'
MEDIA_PLAYER_ATTR_MEDIA_PLAYLIST = 'media_playlist'


def setup(hass, config):
    media_path = config[DOMAIN][CONF_MEDIA_DIR]
    playlist_path = config[DOMAIN][CONF_PLAYLIST_DIR]
    try:
        media_player = config[DOMAIN][CONF_MEDIA_PLAYER]
    except:
        pass
    try:
        tts_player = config[DOMAIN][CONF_TTS_PLAYER] or media_player
    except:
        pass

    crawler = Crawler()
    if not os.path.isabs(playlist_path):
        playlist_path = hass.config.path(playlist_path)
    if not os.path.isdir(playlist_path):
        _LOGGER.error( "invalid playlist_path %s.", playlist_path)
        return False
    if not os.path.isabs(media_path):
        media_path = hass.config.path(media_path)
    if not os.path.isdir(media_path):
        _LOGGER.error( "invalid media_path %s.", media_path)
        return False

    def send_tts(message):
        data = {'message': message}
        if media_player:
            data[ATTR_ENTITY_ID] = media_player
        hass.services.call('tts', 'baidu_say', data)
        #hass.block_till_done()

    def play(service):
        def work():
            try:
                name = service.data[ATTR_NAME]
            except:
                name = ''
            try:
                type = service.data[ATTR_TYPE]
            except:
                type = ATTR_TYPE_SONG
            try:
                replace = service.data[ATTR_REPLACE]
            except:
                replace = False
            try:
                filename = service.data[ATTR_FILENAME]
            except:
                pass
            if filename == None or filename == '':
                filename = 'default'
            filename = filename + '.m3u8'
            playlist_file_path = os.path.normpath(os.path.join(playlist_path,filename))

            _LOGGER.warn('name=%s type=%s replace=%i filename=%s '%(name, type,replace,filename))
            if not os.path.isfile(playlist_file_path):
                f=open(playlist_file_path,'w', encoding='utf8')
                seq = ["#EXTM3U\n", "\n"]
                f.writelines(seq)
                f.close()
            if not replace and os.path.isfile(playlist_file_path):
                f = open(playlist_file_path,'r', encoding='utf8')
                flist=f.readlines()
                f.close()
            else:
                flist = []
            track_list = []

            if type == ATTR_TYPE_SONG:
                if not name:
                    _LOGGER.error('need name attr')
                    return False
                song = crawler.search_song(name)
                _id = song.song_id
                name = song.song_name
                name = name.replace('/', '')
                name = name.replace('.', '')
                url = crawler.get_song_url(_id)
                musicpath = crawler.get_song_by_url(url, name, media_path, None)
                track_list.append('#EXTINF:310, %s \n' % (name))
                track_list.append('file://'+os.path.normpath(musicpath)+'\n')
            elif type == ATTR_TYPE_ARTIST:
                if not name:
                    _LOGGER.error('need name attr')
                    return False
                artist = crawler.search_artist(name)
                songs = crawler.get_artists_hot_songs(artist.artist_id)
                folder = artist.artist_name
                for song in songs:
                    _id = song.song_id
                    name = song.song_name
                    name = name.replace('/', '')
                    name = name.replace('.', '')
                    url = crawler.get_song_url(_id)
                    musicpath = crawler.get_song_by_url(url, name, os.path.join(media_path, folder), None)
                    track_list.append('#EXTINF:310, %s - %s \n' % (folder,name))
                    track_list.append('file://'+os.path.normpath(musicpath)+'\n')
            elif type == ATTR_TYPE_ALBUM:
                if not name:
                    _LOGGER.error('need name attr')
                    return False
                if name[0] == '#':
                    album = crawler.search_album(name)
                    songs = crawler.get_album_songs(album.album_id)
                    folder = album.album_name
                else:
                    songs = crawler.get_album_songs(name[1:])
                    folder = 'playlist'+name
                for song in songs:
                    _id = song.song_id
                    name = song.song_name
                    name = name.replace('/', '')
                    name = name.replace('.', '')
                    url = crawler.get_song_url(_id)
                    musicpath = crawler.get_song_by_url(url, name, os.path.join(media_path, folder), None)
                    track_list.append('#EXTINF:310, %s \n' % (name))
                    track_list.append('file://'+os.path.normpath(musicpath)+'\n')
            elif type == ATTR_TYPE_LOCAL:
                names = name.split(';') if name else None
                for (root, dirs, files) in os.walk(media_path):  
                    for dirc in dirs:
                        if not names or dirc in names:  
                            for (root1, dirs1, files1) in os.walk(root+dirc):  
                                for filename in files1:
                                    musicpath = os.path.join(root1,filename)
                                    track_list.append('#EXTINF:310, %s \n' % (os.path.basename(musicpath)))
                                    track_list.append('file://'+os.path.normpath(musicpath)+'\n')

            flist.insert(2,track_list)
            f=open(playlist_file_path,'w', encoding='utf8')
            for i in range(len(flist)):
                f.writelines(flist[i])
            f.close()

            data = {
              'entity_id': 'media_player.mpd',
              'source': 'default',
            }
            hass.services.call('media_player', 'select_source', data)

        threading.Thread(target=work).start()

    hass.services.register(DOMAIN, SERVICE_MUSICBOX_PLAY, play, schema=SERVICE_MUSICBOX_PLAY_SCHEMA)
    return True



# netease music
# =================

import base64
import json
import binascii
from Cryptodome.Cipher import AES
import requests
from requests.exceptions import RequestException, Timeout, ProxyError
from requests.exceptions import ConnectionError as ConnectionException

# .config
# -----------------

headers = {
    # 'Cookie': 'appver=1.5.2',
    'Accept': '*/*',
    'Accept-Encoding': 'gzip,deflate,sdch',
    'Accept-Language': 'zh-CN,zh;q=0.8,gl;q=0.6,zh-TW;q=0.4',
    'Connection': 'keep-alive',
    'Content-Type': 'application/x-www-form-urlencoded',
    'Host': 'music.163.com',
    'Referer': 'http://music.163.com/search/',
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Ubuntu Chromium/56.0.2924.76 Chrome/56.0.2924.76 Safari/537.36'
}

modulus = '00e0b509f6259df8642dbc35662901477df22677ec152b5ff68ace615bb7b725152b3ab17a876aea8a5aa76d2e417629ec4ee341f56135fccf695280104e0312ecbda92557c93870114af6c9d05c4f7f0c3685b7a46bee255932575cce10b424d813cfe4875d3e82047b97ddef52741d546b8e289dc6935b3ece0462db0a22b8e7'
nonce = '0CoJUm6Qyw8W8jud'
pub_key = '010001'

# .encrypt
# ---------------

def encrypted_request(text):
    text = json.dumps(text)
    sec_key = create_secret_key(16)
    enc_text = aes_encrypt(aes_encrypt(text, nonce), sec_key.decode('utf-8'))
    enc_sec_key = rsa_encrpt(sec_key, pub_key, modulus)
    data = {'params': enc_text, 'encSecKey': enc_sec_key}
    return data


def aes_encrypt(text, secKey):
    pad = 16 - len(text) % 16
    text = text + chr(pad) * pad
    encryptor = AES.new(secKey.encode('utf-8'), AES.MODE_CBC, b'0102030405060708')
    ciphertext = encryptor.encrypt(text.encode('utf-8'))
    ciphertext = base64.b64encode(ciphertext).decode('utf-8')
    return ciphertext


def rsa_encrpt(text, pubKey, modulus):
    text = text[::-1]
    rs = pow(int(binascii.hexlify(text), 16), int(pubKey, 16), int(modulus, 16))
    return format(rs, 'x').zfill(256)


def create_secret_key(size):
    return binascii.hexlify(os.urandom(size))[:16]

# .modulus
# -------------------
class Song(object):

    def __init__(self, song_id, song_name, artist_id=None, album_id=None,
                hot_comments=None, comment_count=None, song_lyric=None,
                song_url=None):
        self.song_id = song_id
        self.song_name = song_name
        self.artist_id = artist_id
        self.album_id = album_id
        self.hot_comments = [] if hot_comments is None else hot_comments
        self.comment_count = 0 if comment_count is None else comment_count
        self.song_lyric = u'' if song_lyric is None else song_lyric
        self.song_url = '' if song_url is None else song_url


class Comment(object):

    def __init__(self, comment_id, content, like_count, created_time,
                user_id=None):
        self.comment_id = comment_id
        self.content = content
        self.like_count = like_count
        self.created_time = created_time
        self.user_id = user_id


class Album(object):

    def __init__(self, album_id, album_name, artist_id=None,
                songs=None, hot_comments=None):
        self.album_id = album_id
        self.album_name = album_name
        self.artist_id = artist_id
        self.songs = [] if songs is None else songs
        self.hot_comments = [] if hot_comments is None else hot_comments

    def add_song(self, song):
        self.songs.append(song)


class Artist(object):

    def __init__(self, artist_id, artist_name, hot_songs=None):
        self.artist_id = artist_id
        self.artist_name = artist_name
        self.hot_songs = [] if hot_songs is None else hot_songs

    def add_song(self, song):
        self.hot_songs.append(song)


class Playlist(object):

    def __init__(self, playlist_id, playlist_name, user_id=None,
                songs=None, hot_comments=None):
        self.playlist_id = playlist_id
        self.playlist_name = playlist_name
        self.user_id = user_id
        self.songs = [] if songs is None else songs
        self.hot_comments = [] if hot_comments is None else hot_comments

    def add_song(self, song):
        self.songs.append(song)


class User(object):

    def __init__(self, user_id, user_name, songs=None, hot_comments=None):
        self.user_id = user_id
        self.user_name = user_name
        self.songs = [] if songs is None else songs
        self.hot_comments = [] if hot_comments is None else hot_comments

    def add_song(self, song):
        self.songs.append(song)

# .exceptions
# --------------
class SearchNotFound(RequestException):
    """Search api return None."""


class SongNotAvailable(RequestException):
    """Some songs are not available, for example Taylor Swift's songs."""


class GetRequestIllegal(RequestException):
    """Status code is not 200."""


class PostRequestIllegal(RequestException):
    """Status code is not 200."""

# .weapi
# -------------
def exception_handle(method):
    """Handle exception raised by requests library."""

    def wrapper(*args, **kwargs):
        try:
            result = method(*args, **kwargs)
            return result
        except ProxyError:
            _LOGGER.exception('ProxyError when try to get %s.', args)
            raise ProxyError('A proxy error occurred.')
        except ConnectionException:
            _LOGGER.exception('ConnectionError when try to get %s.', args)
            raise ConnectionException('DNS failure, refused connection, etc.')
        except Timeout:
            _LOGGER.exception('Timeout when try to get %s', args)
            raise Timeout('The request timed out.')
        except RequestException:
            _LOGGER.exception('RequestException when try to get %s.', args)
            raise RequestException('Please check out your network.')

    return wrapper

class Crawler(object):
    """NetEase Music API."""

    def __init__(self, timeout=60, proxy=None):
        self.session = requests.Session()
        self.session.headers.update(headers)
        self.download_session = requests.Session()
        self.timeout = timeout
        self.proxies = {'http': proxy, 'https': proxy}

    @exception_handle
    def get_request(self, url):
        """Send a get request.
        warning: old api.
        :return: a dict or raise Exception.
        """

        resp = self.session.get(url, timeout=self.timeout, proxies=self.proxies)
        result = resp.json()
        if result['code'] != 200:
            LOG.error('Return %s when try to get %s', result, url)
            raise GetRequestIllegal(result)
        else:
            return result

    @exception_handle
    def post_request(self, url, params):
        """Send a post request.
        :return: a dict or raise Exception.
        """

        data = encrypted_request(params)
        resp = self.session.post(url, data=data, timeout=self.timeout,
                                proxies=self.proxies)
        result = resp.json()
        if result['code'] != 200:
            _LOGGER.error('Return %s when try to post %s => %s', result, url, params)
            raise PostRequestIllegal(result)
        else:
            return result

    def search(self, search_content, search_type, limit=9):
        """Search entrance.
        :params search_content: search content.
        :params search_type: search type.
        :params limit: result count returned by weapi.
        :return: a dict.
        """

        url = 'http://music.163.com/weapi/cloudsearch/get/web?csrf_token='
        params = {'s': search_content, 'type': search_type, 'offset': 0,
                'sub': 'false', 'limit': limit}
        result = self.post_request(url, params)
        return result

    def search_song(self, song_name, quiet=False, limit=9):
        """Search song by song name.
        :params song_name: song name.
        :params quiet: automatically select the best one.
        :params limit: song count returned by weapi.
        :return: a Song object.
        """

        result = self.search(song_name, search_type=1, limit=limit)
        if result['result']['songCount'] <= 0:
            _LOGGER.warning('Song %s not existed!', song_name)
            raise SearchNotFound('Song {} not existed.'.format(song_name))
        else:
            songs = result['result']['songs']
            song_id, song_name = songs[0]['id'], songs[0]['name']
            song = Song(song_id, song_name)
            return song

    def search_album(self, album_name, quiet=False, limit=9):
        """Search album by album name.
        :params album_name: album name.
        :params quiet: automatically select the best one.
        :params limit: album count returned by weapi.
        :return: a Album object.
        """

        result = self.search(album_name, search_type=10, limit=limit)

        if result['result']['albumCount'] <= 0:
            _LOGGER.warning('Album %s not existed!', album_name) 
            raise SearchNotFound('Album {} not existed'.format(album_name))
        else:
            albums = result['result']['albums']
            album_id, album_name = albums[0]['id'], albums[0]['name']
            album = Album(album_id, album_name)
            return album

    def search_artist(self, artist_name, quiet=False, limit=9):
        """Search artist by artist name.
        :params artist_name: artist name.
        :params quiet: automatically select the best one.
        :params limit: artist count returned by weapi.
        :return: a Artist object.
        """

        result = self.search(artist_name, search_type=100, limit=limit)

        if result['result']['artistCount'] <= 0:
            _LOGGER.warning('Artist %s not existed!', artist_name) 
            raise SearchNotFound('Artist {} not existed.'.format(artist_name))
        else:
            artists = result['result']['artists']
            artist_id, artist_name = artists[0]['id'], artists[0]['name']
            artist = Artist(artist_id, artist_name)
            return artist

    def search_playlist(self, playlist_name, quiet=False, limit=9):
        """Search playlist by playlist name.
        :params playlist_name: playlist name.
        :params quiet: automatically select the best one.
        :params limit: playlist count returned by weapi.
        :return: a Playlist object.
        """

        result = self.search(playlist_name, search_type=1000, limit=limit)

        if result['result']['playlistCount'] <= 0:
            _LOGGER.warning('Playlist %s not existed!', playlist_name) 
            raise SearchNotFound('playlist {} not existed'.format(playlist_name))
        else:
            playlists = result['result']['playlists']
            playlist_id, playlist_name = playlists[0]['id'], playlists[0]['name']
            playlist = Playlist(playlist_id, playlist_name)
            return playlist

    def search_user(self, user_name, quiet=False, limit=9):
        """Search user by user name.
        :params user_name: user name.
        :params quiet: automatically select the best one.
        :params limit: user count returned by weapi.
        :return: a User object.
        """

        result = self.search(user_name, search_type=1002, limit=limit)

        if result['result']['userprofileCount'] <= 0:
            _LOGGER.warning('User %s not existed!', user_name) 
            raise SearchNotFound('user {} not existed'.format(user_name))
        else:
            users = result['result']['userprofiles']
            user_id, user_name = users[0]['userId'], users[0]['nickname']
            user = User(user_id, user_name)
            return user

    def get_user_playlists(self, user_id, limit=1000):
        """Get a user's all playlists.
        warning: login is required for private playlist.
        :params user_id: user id.
        :params limit: playlist count returned by weapi.
        :return: a Playlist Object.
        """

        url = 'http://music.163.com/weapi/user/playlist?csrf_token='
        csrf = ''
        params = {'offset': 0, 'uid': user_id, 'limit': limit, 'csrf_token': csrf}
        result = self.post_request(url, params)
        playlists = result['playlist']
        return self.display.select_one_playlist(playlists)

    def get_playlist_songs(self, playlist_id, limit=1000):
        """Get a playlists's all songs.
        :params playlist_id: playlist id.
        :params limit: length of result returned by weapi.
        :return: a list of Song object.
        """

        url = 'http://music.163.com/weapi/v3/playlist/detail?csrf_token='
        csrf = ''
        params = {'id': playlist_id, 'offset': 0, 'total': True, 'limit': limit, 'n': 1000, 'csrf_token': csrf}
        result = self.post_request(url, params)

        songs = result['playlist']['tracks']
        songs = [Song(song['id'], song['name']) for song in songs]
        return songs

    def get_album_songs(self, album_id):
        """Get a album's all songs.
        warning: use old api.
        :params album_id: album id.
        :return: a list of Song object.
        """

        url = 'http://music.163.com/api/album/{}/'.format(album_id)
        result = self.get_request(url)

        songs = result['album']['songs']
        songs = [Song(song['id'], song['name']) for song in songs]
        return songs

    def get_artists_hot_songs(self, artist_id):
        """Get a artist's top50 songs.
        warning: use old api.
        :params artist_id: artist id.
        :return: a list of Song object.
        """
        url = 'http://music.163.com/api/artist/{}'.format(artist_id)
        result = self.get_request(url)

        hot_songs = result['hotSongs']
        songs = [Song(song['id'], song['name']) for song in hot_songs]
        return songs

    def get_song_url(self, song_id, bit_rate=320000):
        """Get a song's download address.
        :params song_id: song id<int>.
        :params bit_rate: {'MD 128k': 128000, 'HD 320k': 320000}
        :return: a song's download address.
        """

        url = 'http://music.163.com/weapi/song/enhance/player/url?csrf_token='
        csrf = ''
        params = {'ids': [song_id], 'br': bit_rate, 'csrf_token': csrf}
        result = self.post_request(url, params)
        song_url = result['data'][0]['url']  # download address

        if song_url is None:  # Taylor Swift's song is not available
            _LOGGER.warning( 'Song %s is not available due to copyright issue. => %s', song_id, result)
            raise SongNotAvailable( 'Song {} is not available due to copyright issue.'.format(song_id))
        else:
            return song_url

    def get_song_lyric(self, song_id):
        """Get a song's lyric.
        warning: use old api.
        :params song_id: song id.
        :return: a song's lyric.
        """

        url = 'http://music.163.com/api/song/lyric?os=osx&id={}&lv=-1&kv=-1&tv=-1'.format(song_id)
        result = self.get_request(url)
        if 'lrc' in result and result['lrc']['lyric'] is not None:
            lyric_info = result['lrc']['lyric']
        else:
            lyric_info = 'Lyric not found.'
        return lyric_info

    @exception_handle
    def get_song_by_url(self, song_url, song_name, folder, lyric_info):
        """Download a song and save it to disk.
        :params song_url: download address.
        :params song_name: song name.
        :params folder: storage path.
        :params lyric: lyric info.
        """

        if not os.path.exists(folder):
            os.makedirs(folder)
        fpath = os.path.join(folder, song_name+'.mp3')
        if sys.platform == 'win32' or sys.platform == 'cygwin':
            valid_name = re.sub(r'[<>:"/\\|?*]', '', song_name)
            if valid_name != song_name:
                fpath = os.path.join(folder, valid_name + '.mp3')

        if not os.path.exists(fpath):
            resp = self.download_session.get( song_url, timeout=self.timeout, stream=True)
            #length = int(resp.headers.get('content-length'))
            #label = 'Downloading {} {}kb'.format(song_name, int(length/1024))

            with open(fpath, 'wb') as song_file:
                for chunk in resp.iter_content(chunk_size=1024):
                    if chunk:  
                        song_file.write(chunk)

        if lyric_info:
            folder = os.path.join(folder, 'lyric')
            if not os.path.exists(folder): os.makedirs(folder)
            fpath = os.path.join(folder, song_name+'.lrc')
            with open(fpath, 'w') as lyric_file:
                lyric_file.write(lyric_info)

        return fpath

