from dataclasses import dataclass
from typing import Optional
from os.path import isdir
from os import path
import re
import shutil
from langcodes import Language
from langcodes import standardize_tag
import langcodes
import py3langid as langid
from pyarr import SonarrAPI
from ass_parser import read_ass
from ass_tag_parser import ass_to_plaintext
import json
import os
import subprocess
import configus

SONARR_HOST_URL = configus.CONF_SONARR_HOST_URL
SONARR_API = configus.CONF_SONARR_API
TEMP_FOLDER = configus.CONF_TEMP_FOLDER
DEFAULT_LANG = configus.CONF_DEFAULT_LANG
SUBTITLE_PATH = configus.CONF_SUBTITLE_PATH
LANGUAGE_TAGS = configus.COMMON_LANGUAGE_TAGS


@dataclass
class TrackInfo:
    trackId: Optional[str] = None
    basedir: Optional[str] = None
    filename: Optional[str] = None
    filepath: Optional[str] = None
    is_default: Optional[bool] = False
    is_forced: Optional[bool] = False
    season: Optional[str] = None
    episode: Optional[str] = None
    trackname: Optional[str] = None
    release: Optional[str] = 'Anonymous'
    subtype: Optional[str] = None
    language_ietf: Optional[str] = None
    to_remux: Optional[bool] = None
    is_sdh: Optional[bool] = None

    @property
    def sdh(self) -> Optional[str]:
        if self.is_sdh:
            return 'sdh.'
        else:
            return ''

    @property
    def forced(self) -> Optional[str]:
        if self.is_forced:
            return 'forced.'
        else:
            return ''

    @property
    def default(self) -> Optional[str]:
        if self.is_default:
            return 'default.'
        else:
            return ''

    @property
    def trackname_combined(self) -> Optional[str]:
        re_p = r'\[.+\]-\[.+\]'
        if re.search(re_p, str(self.trackname)) is not None:
            return self.trackname
        else:
            return f'[{self.release}]-[{self.trackname}]'


def check_forced(track_name: str) -> bool:
    keywords = ["signs", "songs", "forc"]
    track_name_lower = track_name.lower()
    forced = (
        "forced." if any(
            keyword in track_name_lower for keyword in keywords) else ""
    )
    return True if forced == 'forced.' else False


def extension(sub_type) -> str:
    sub_extension = ""
    if "PGS" in sub_type:
        sub_extension = "sup"
    elif "ASS" in sub_type:
        sub_extension = "ass"
    elif "SSA" in sub_type:
        sub_extension = "ssa"
    elif "UTF8" in sub_type or "ASCII" in sub_type:
        sub_extension = "srt"
    elif "VOBSUB" in sub_type:
        sub_extension = "sub"
    elif "USF" in sub_type:
        sub_extension = "usf"
    elif "WEBVTT" in sub_type:
        sub_extension = "vtt"
    return sub_extension


def list_ext_tracks(ep_path: str) -> list:
    track_keywords = ['ass', 'srt', 'ssa', 'sub', 'sup']
    basedir = os.path.dirname(ep_path)
    filename = os.path.basename(ep_path)
    filename = os.path.splitext(filename)[0]
    all_files = os.listdir(basedir)
    matching = [track for track in all_files
                if track.startswith(filename)
                and track.endswith(tuple(track_keywords))]
    return matching


def parse_subtitle_filename(file_path: str) -> TrackInfo:
    s = TrackInfo()
    base_dir = path.dirname(file_path)
    file_name = path.basename(file_path)
    is_default = False
    is_forced = False
    rpattern = r'S(\d{2,3})\.E(\d{2,3})\.\[(.+)\]-\[(.+)\]\.(.+)\.(\w{3}$)'
    # 'S01.E20.[Retr0]-[Signs#Songs [Commie]].default.eng.forced.ass'
    re_match = re.search(string=file_name, pattern=rpattern)
    season = re_match.group(1)  # pyright: ignore
    episode = re_match.group(2)  # pyright: ignore
    rel_group = re_match.group(3)  # pyright: ignore
    trackname = re_match.group(4)  # pyright: ignore
    flags = re_match.group(5)  # pyright: ignore
    sub_extention = re_match.group(6)  # pyright: ignore
    if 'default' in flags:
        is_default = True
        flags = flags.replace('default.', '')
    if 'forced' in flags:
        is_forced = True
        flags = flags.replace('forced', '')
    flags = flags.replace('.', '')
    lang_ = standardize_tag(flags)
    s.basedir = base_dir
    s.filename = file_name
    s.is_default = is_default
    s.is_forced = is_forced
    s.season = season
    s.episode = episode
    s.trackname = f'[{rel_group}]-[{trackname}]'
    s.subtype = sub_extention
    s.language_ietf = lang_
    s.filepath = file_path
    return s


def parse_external_trackname(ep_path: str, sub_path: str) -> dict:
    results = {}
    filename = os.path.basename(ep_path)
    filename = os.path.splitext(filename)[0]
    sub_path_copy = sub_path
    sub_path = os.path.splitext(sub_path)[0]
    flags = sub_path.replace(filename + '.', '').split('.')
    flags_copy = flags.copy()
    for flag in flags_copy:
        if 'default' == flag:
            results['default'] = True
            flags.remove(flag)
        if 'forced' == flag:
            results['forced'] = True
            flags.remove(flag)
        if 'hi' == flag:
            results['cc'] = True
            flags.remove(flag)
        if 'cc' == flag:
            results['cc'] = True
            flags.remove(flag)
        if 'sdh' == flag:
            results['cc'] = True
            flags.remove(flag)
    if len(flags) == 2:
        results['trackname'] = flags[0]
        results['tracklang'] = langcodes.standardize_tag(flags[1])
    if len(flags) == 1:
        results['tracklang'] = langcodes.standardize_tag(flags[0])
    results['filename'] = sub_path_copy
    return results


def option_selector(k_list: list[str], v_list: list[str], txt: str) -> str:
    result = ''
    print('Choose between the following options')
    for i, k in enumerate(k_list):
        print(f'{i}. {k}: {v_list[i]}')
    while True:
        choice = int(input('Option N°: '))
        if 0 <= choice <= len(k_list):
            if choice == 0:
                result = input(txt)
                break
            else:
                result = v_list[choice]
                break
    return result


def language_selector() -> str:
    v_list = ['If you choose this option, you can input your own text']
    k_list = ['Write your own']
    # Key and Value are reversed on purpose
    for value, key in LANGUAGE_TAGS.items():
        k_list.append(key)
        v_list.append(value)
    txt = 'BCP 47 tags are required: '
    lang = option_selector(k_list, v_list, txt)
    lang = standardize_tag(lang)
    return lang


def ask_user_input(header: dict, parsed_name: dict) -> TrackInfo:
    key_list = ['Write your own']
    val_list = ['If you choose this option, you can input your own text']
    if not len(header) == 0:
        for key, value in header.items():
            key_list.append(key)
            val_list.append(value)
    for key, value in parsed_name.items():
        key_list.append(key)
        val_list.append(value)
    t = TrackInfo()
    print(parsed_name.get('filename'))
    t.is_forced = parsed_name.get('forced', False)
    print(f'Is "Forced track" correct ? Forced is {t.is_forced}')
    choice = input(r'[Y/n] : ')
    if choice.lower().startswith('n'):
        t.is_forced = not t.is_forced
        print(f'Forced track is now {t.is_forced}')
    t.is_default = parsed_name.get('default', False)
    print(f'Is "Default track" correct ? Default is {t.is_default}')
    choice = input(r'[Y/n] : ')
    if choice.lower().startswith('n'):
        t.is_default = not t.is_default
        print(f'Default track is now {t.is_default}')
    t.is_sdh = parsed_name.get('cc', False)
    print(f'Is "Hearing impaired track" correct ? CC is {t.is_sdh}')
    choice = input(r'[Y/n] : ')
    if choice.lower().startswith('n'):
        t.is_sdh = not t.is_sdh
        print(f'Hearing impaired track is now {t.is_sdh}')
    t.trackname = parsed_name.get('trackname', header.get('title', 'und'))
    print(f'Is Track Name correct ? Track Name is {t.trackname}')
    choice = input(r'[Y/n] : ')
    if choice.lower().startswith('n'):
        txt = 'Write your own Track Name : '
        t.trackname = option_selector(key_list, val_list, txt)
        print(f'Track Name is now : {t.trackname}')
    t.language_ietf = parsed_name.get('tracklang')
    print(f'Is Track Language correct ? : Language is {t.language_ietf}')
    print(f'Identified language in subtitle file is : '
          f'{parsed_name.get("identified_lang", "undefiend")}')
    choice = input(r'[Y/n] : ')
    if choice.lower().startswith('n'):
        t.language_ietf = language_selector()
        print(f'Track Lang is now : {t.language_ietf}')
    return t


def build_subtitle_tags(ep_path: str, sub_list: list[str]) -> list[TrackInfo]:
    sub_list_ok = []
    basedir = os.path.dirname(ep_path)
    for sub in sub_list:
        fullpath = os.path.join(basedir, sub)
        if sub.endswith('ass'):
            header = get_subtitle_header(fullpath, True)
            title_parsed = parse_external_trackname(ep_path, sub)
            title_parsed['identified_lang'] = identify_lang_in_dialog(fullpath)
            approuved_track = ask_user_input(header, title_parsed)
            approuved_track.filepath = os.path.join(basedir, sub)
            sub_list_ok.append(approuved_track)
        if sub.endswith('srt') or sub.endswith('ssa'):
            title_parsed = parse_external_trackname(ep_path, sub)
            title_parsed['identified_lang'] = identify_lang_in_dialog(fullpath)
            approuved_track = ask_user_input({}, title_parsed)
            approuved_track.filepath = os.path.join(basedir, sub)
            sub_list_ok.append(approuved_track)
    return sub_list_ok


def clean_header(sub: dict) -> dict:
    keys_to_clean = ['ScriptType',
                     'WrapStyle',
                     'PlayResX',
                     'PlayResY',
                     'ScaledBorderAndShadow',
                     'YCbCr Matrix',
                     'Last Style Storage',
                     'Video Aspect Ratio',
                     'Video Zoom',
                     'Video Position',
                     'Collisions',
                     'Video File',
                     'Aegisub Video Aspect Ratio',
                     # 'Original Translation',
                     # 'Original Editing',
                     # 'Original Timing',
                     'Synch Point',
                     # 'Script Updated By',
                     'Update Details',
                     'Timer']
    for k in keys_to_clean:
        if k in sub:
            del sub[k]
    return sub


def get_subtitle_header(sub_path: str, cleaning=False) -> dict:
    content = get_subtitle_file_content(sub_path)
    sub = read_ass(content)
    sub = dict(sub.script_info)
    if cleaning:
        sub = clean_header(sub)
    return sub


def get_subtitle_file_content(sub_path: str) -> str:
    return read_sub_file(sub_path)


def identify_lang_in_dialog(sub_path: str) -> str:
    content = get_subtitle_file_content(sub_path)
    ext = str(os.path.splitext(sub_path)[1])
    dialogs = ''
    identify = ''
    if ext.endswith('ass') or ext.endswith('ssa'):
        dialogs = read_ass_dialogs(content)
        identify = langid.classify(dialogs)[0]
    elif ext.endswith('srt'):
        dialogs = read_srt_dialogs(content)
        identify = langid.classify(dialogs)[0]
    else:
        identify = 'undefiend'
    return str(identify)


def read_ass_dialogs(ass_events) -> str:
    all_events = read_ass(ass_events).events
    dialog_list = []
    limit_line = 150
    current_line = 0
    for dialog_line in all_events:
        dialog_list.append(dialog_line.text)
        current_line += 1
        if current_line >= limit_line:
            break
    cleaned_list = []
    for raw_dialog in dialog_list:
        cleaning = ass_to_plaintext(raw_dialog)
        cleaned_list.append(cleaning.replace('\n', ' ').strip())
    result = ' '.join(cleaned_list)
    return result


def read_srt_dialogs(content: str) -> str:
    timecode = r'\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}'
    cleaned = re.sub(timecode, '', content)
    cleaned = '\n'.join(line.strip()
                        for line in cleaned.splitlines() if line.strip())
    return cleaned.replace('\n', ' ')


def read_sub_file(sub_path: str) -> str:
    with open(sub_path, 'r') as file:
        file_content = file.read()
        return file_content


class Episode():
    def __init__(self):
        self._serie_id = ""
        self._ep_id = ""
        self._ep_file_exist = False
        self._external_tracks: list[TrackInfo] = []
        self._number = ""
        self._season = ""
        self._video_path = ""
        self._serie_path = ""
        self._sonarr_var = None
        self.release = ""
        self.tvdbid = ""
        self._copy_temp_path = ""
        self._temp_folder = TEMP_FOLDER

    @property
    def serie_id(self):
        return self._serie_id

    @serie_id.setter
    def serie_id(self, s_id: int | str):
        self._serie_id = str(s_id)

    @property
    def ep_id(self):
        return self._ep_id

    @ep_id.setter
    def ep_id(self, id: int | str):
        self._ep_id = str(id)

    @property
    def temp_path(self) -> str:
        return self._copy_temp_path

    @property
    def serie_path(self) -> str:
        return self._serie_path

    @serie_path.setter
    def serie_path(self, s_path: str):
        self._serie_path = s_path

    @property
    def video_path(self) -> str:
        return self._video_path

    @video_path.setter
    def video_path(self, new_path: str) -> None:
        self._video_path = new_path
        self._ep_file_exist = True

    @property
    def file_exist(self) -> bool:
        return self._ep_file_exist

    @property
    def ext_tracks(self) -> list[TrackInfo]:
        return self._external_tracks

    @ext_tracks.setter
    def ext_tracks(self, tracks: list[TrackInfo]):
        self._external_tracks = tracks

    @property
    def number(self) -> str:
        return self._number

    @number.setter
    def number(self, value: str | int) -> None:
        try:
            number = int(value)
            formated_number = f"{number:02d}"
            self._number = formated_number
        except ValueError:
            print("Episode number is not a valid format")

    @property
    def season(self) -> str:
        return self._season

    @season.setter
    def season(self, value: str | int) -> None:
        try:
            season = int(value)
            formated_season = f"{season:02d}"
            self._season = formated_season
        except ValueError:
            print("Season number is not a valid format")

    @property
    def sonarr_var(self):
        return self._sonarr_var

    @sonarr_var.setter
    def sonarr_var(self, value):
        self._sonarr_var = value
        self._video_path = value.get("sonarr_episodefile_path")
        self.tvdbid = value.get("sonarr_series_tvdbid")
        self.number = value.get("sonarr_episodefile_episodenumbers")
        self.season = value.get("sonarr_episodefile_seasonnumber")
        self.serie_path = value.get("sonarr_series_path")
        self.release = value.get("sonarr_episodefile_releasegroup")
        self._serie_id = value.get("sonarr_series_id")
        self._ep_id = value.get("sonarr_episodefile_episodeids")

    def copy_temp(self) -> str:
        path = shutil.copy(self._video_path, self._temp_folder)
        self._copy_temp_path = path
        return path

    def delete_temp(self) -> None:
        temp_folder = self._temp_folder
        if os.path.exists(temp_folder) and os.path.isdir(temp_folder):
            files = os.listdir(temp_folder)
            if files:
                for file in files:
                    file_path = os.path.join(temp_folder, file)
                    if os.path.isfile(file_path):
                        os.remove(file_path)


class MkvAnalyzer():
    def __init__(self):
        self._audio = []
        self.__subs = []
        self._tracks = {}
        self._video_path = ""

    @property
    def subs(self) -> list[TrackInfo]:
        return self.__subs

    @property
    def too_big(self) -> bool:
        size_in_bytes = os.path.getsize(self._video_path)
        size_in_mb = int(size_in_bytes / (1024 * 1024))
        track_number = len(self.__subs)
        return size_in_mb > 400 or track_number > 2

    def analyze(self, json_data: dict = {}, video_path: str = "") -> None:
        self.__subs = []
        if not json_data:
            json_data = self._tracks
        if video_path == "":
            video_path = self._video_path
        if (json_data.get("tracks") is not None):
            for track in json_data["tracks"]:
                if track["type"] == "subtitles":
                    self._analyze_sub_track(track, video_path)

    def _analyze_sub_track(self, track: dict, video_path: str) -> None:
        s = TrackInfo()
        track_props = track["properties"]
        sub_type = track_props.get("codec_id")
        sub_type_extention = extension(sub_type)
        track_id = track["id"]
        track_name = track_props.get("track_name", "und")
        track_name = track_name.replace(r"/", "#")
        is_forced = track_props.get("forced_track", False)
        if track_name != "und" and not is_forced:
            is_forced = check_forced(track_name)
        track_lang_ietf = track_props.get("language_ietf", "und")
        if track_lang_ietf != "und":
            track_lang = track_lang_ietf
        else:
            track_lang = track_props.get("language", "und")
        if track_lang == "und":
            track_lang = self.guess_lang(track_name)
        if track_lang == "und" or not track_lang:
            track_lang = self.guess_lang_harder(video_path,
                                                track_id,
                                                sub_type_extention)
        if track_lang != "und" and track_name == "und":
            track_name = (f"{Language.get(track_lang).display_name()} # "
                          f"{Language.get(track_lang).display_name(track_lang)}")
        if track_lang != "und":
            if DEFAULT_LANG in track_lang:
                s.is_default = True
        track_lang = standardize_tag(track_lang)
        s.trackId = track_id
        s.subtype = sub_type_extention
        s.trackname = track_name
        s.is_forced = is_forced
        s.language_ietf = track_lang
        self.__subs.append(s)

    def identify(self, video_file: str) -> bool:
        json_data = ""
        cmd = [f"mkvmerge -i -J \"{video_file}\""]
        print(cmd)
        proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
        json_data, err = proc.communicate()
        json_data = json_data.decode("utf-8")
        json_data = json.loads(json_data)
        self._video_path = video_file
        self._tracks = json_data
        return not json_data["errors"]

    def normalize_lang(self, track: dict, trackname="") -> dict:
        do_something = track
        return do_something

    def guess_lang(self, track_name):
        try:
            track_lang = Language.find(track_name)
            return track_lang
        except LookupError:
            print("Unable to determine language for subtitle track")
            return False

    def guess_lang_harder(self, video_file, track_id, sub_extention):
        text_subs = ['ass', 'ssa', 'srt']
        result = ""
        if sub_extention in text_subs:
            sub_path = self.export(video_file, track_id,
                                   "./caca" + sub_extention)
        return result

    def export(self, video_file: str, track_id: str | int, path: str) -> str:
        cmd = [
            f"mkvextract tracks \"{video_file}\" {str(track_id)}:\"{path}\""]
        print(cmd)
        subprocess.run(cmd, shell=True, check=True)
        return path


class Sonarr():
    def __init__(self, export_external_tracks=False) -> None:
        self._sonarr = SonarrAPI(SONARR_HOST_URL, SONARR_API)
        self._series = []
        self._episode_list = []
        self._episode = {}
        self._episode_path = []
        self._bool_export_ext_tracks = export_external_tracks
        self._external_tracks = []
        self._serie_id = ''

    # tvdbid, seasonnumber, episodenumber, releasegroup

    @property
    def series(self) -> list:
        series = self._sonarr.get_series()
        self._series = series
        return self._series

    def episode_list(self, serie_id: int | str) -> list:
        self._serie_id = serie_id
        ep_list = self._sonarr.get_episode(serie_id, series=True)
        self._episode_list = ep_list
        return self._episode_list

    def episode(self, ep_id: int | str) -> Episode:
        ep = Episode()
        sonarr_ep = self._sonarr.get_episode(ep_id, series=False)
        ep.ep_id = ep_id
        ep.serie_id = self._serie_id
        if 'episodeFile' in sonarr_ep:
            ep.tvdbid = sonarr_ep['series'].get('tvdbId')
            ep.season = sonarr_ep.get('seasonNumber')
            ep.number = sonarr_ep.get('episodeNumber')
            ep.video_path = sonarr_ep['episodeFile'].get('path')
            ep.serie_path = sonarr_ep['series'].get('path')
            ep.release = sonarr_ep['episodeFile'].get('releaseGroup')
            if self._bool_export_ext_tracks:
                self._list_ext_tracks(ep.video_path)
                ep.ext_tracks = self._external_tracks
        return ep

    def is_monitored(self, ep_id: int | str) -> bool:
        ep_id = int(ep_id)
        ep = self._sonarr.get_episode(ep_id, series=False)
        return ep.get("monitored", True)

    def _list_ext_tracks(self, ep_path: str) -> None:
        track_list = list_ext_tracks(ep_path)
        if len(track_list) > 0:
            print(f'External subtitles found alongside the episode: '
                  f'{len(track_list)} track(s) present in folder')
            subs = build_subtitle_tags(ep_path, track_list)
            self._external_tracks = subs


class Subtitles():
    def __init__(self) -> None:
        self.__subs_list = []

    @property
    def subs_list(self) -> list[TrackInfo]:
        return self.__subs_list

    def compare_with_mkv(self, mkv_tracks: list[TrackInfo]) -> list[TrackInfo]:
        sub_tracks = self.subs_list
        if len(sub_tracks) > 0:
            for sub_track in sub_tracks:
                lang = str(sub_track.language_ietf)[:2]
                for mkv_track in mkv_tracks:
                    mkv_lang = str(mkv_track.language_ietf)[:2]
                    if lang in mkv_lang:
                        sub_track.to_remux = False
                        break
                    else:
                        sub_track.to_remux = True
        self.__subs_list = sub_tracks
        return sub_tracks

    def analyze_folder(self, folder_path: str) -> list[TrackInfo]:
        if isdir(folder_path):
            all_subs = os.listdir(folder_path)
            if len(all_subs) > 0:
                for subtitle in all_subs:
                    f_path = path.join(folder_path, subtitle)
                    subtitle_track = parse_subtitle_filename(f_path)
                    self.__subs_list.append(subtitle_track)
        return self.subs_list
