from dataclasses import dataclass
from typing import Optional
from os.path import isdir
from os import path
import re
import shutil
from langcodes import Language
from langcodes import standardize_tag
from langcodes import closest_match
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
LOG = configus.CONF_LOGGER


@dataclass
class TrackInfo:
    trackId: str = ''
    basedir: str = ''
    filename: str = ''
    filepath: str = ''
    is_default: Optional[bool] = False
    is_forced: Optional[bool] = False
    season: str = ''
    episode: str = ''
    trackname: str = ''
    release: str = 'Anonymous'
    subtype: str = ''
    language_ietf: str = ''
    to_remux: Optional[bool] = False
    is_sdh: Optional[bool] = False
    delay_ms: int = 0

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
            return f'{self.trackname}'
        else:
            return f'[{self.release}]-[{self.trackname}]'


@dataclass
class AudioTrackInfo(TrackInfo):
    codec: str = ''


def check_forced(track_name: str) -> bool:
    keywords = ["signs", "songs", "forc", "s&s"]
    track_name_lower = track_name.lower()
    forced = (
        "forced." if any(
            keyword in track_name_lower for keyword in keywords) else ""
    )
    return True if forced == 'forced.' else False


def extension(sub_type) -> str:
    """Returns the file extension for the given subtitle type.

    Args:
        sub_type: The subtitle type.
    """
    sub_extension = ""
    sub_type = sub_type.upper()
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
    elif "TIMED TEXT" in sub_type:
        sub_extension = "ttml"
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


def subtitle_export_name(t: TrackInfo) -> str:
    """Returns the file name for the subtitle without the parents dir
    In exemple:
        S01.E20.[Retr0]-[Signs#Songs [Commie]].default.eng.forced.ass
    """
    sub_name = (f"S{t.season}.E{t.episode}."
                f"{t.trackname_combined}."
                f"{t.default}"
                f"{t.language_ietf}."
                f"{t.forced}{t.sdh}"
                f"{t.subtype}")
    LOG.debug(sub_name)
    return sub_name


def parse_external_trackname(ep_path: str, sub_path: str) -> dict:
    results = {}
    results['subtype'] = os.path.splitext(sub_path)[1].replace('.', '')
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
        choice = input('Option N°: ')
        if choice.isnumeric():
            choice = int(choice)
            if 0 <= choice <= len(k_list):
                if choice == 0:
                    result = input(txt)
                    break
                else:
                    result = v_list[choice]
                    break
        else:
            print('Only numeric values')
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


def ask_user_input(header: dict, parsed_name: dict,
                   guess: bool = False) -> TrackInfo:
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
    if not guess:
        while True:
            t.subtype = parsed_name.get('subtype', '')
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
            t.trackname = parsed_name.get(
                'trackname', header.get('title', 'und'))
            print(f'Is Track Name correct ? Track Name is {t.trackname}')
            choice = input(r'[Y/n] : ')
            if choice.lower().startswith('n'):
                txt = 'Write your own Track Name : '
                t.trackname = option_selector(key_list, val_list, txt)
                print(f'Track Name is now : {t.trackname}')
            t.language_ietf = parsed_name.get('tracklang', '')
            print(
                f'Is Track Language correct ? : Language is {t.language_ietf}')
            print(f'Identified language in subtitle file is : '
                  f'{parsed_name.get("identified_lang", "undefiend")}')
            choice = input(r'[Y/n] : ')
            if choice.lower().startswith('n'):
                t.language_ietf = language_selector()
                print(f'Track Lang is now : {t.language_ietf}')
            choice = input('Is everything correct ? [Y/n]')
            if not choice.lower().startswith('n'):
                break
    else:
        t.subtype = parsed_name.get('subtype', '')
        t.is_forced = parsed_name.get('forced', False)
        t.is_default = parsed_name.get('default', False)
        t.is_sdh = parsed_name.get('cc', False)
        t.trackname = parsed_name.get('trackname', header.get('title', 'und'))
        t.language_ietf = parsed_name.get('tracklang', '')
    LOG.debug(subtitle_export_name(t))
    return t


def build_subtitle_tags(ep_path: str, sub_list: list[str],
                        guess: bool = False) -> list[TrackInfo]:
    sub_list_ok = []
    basedir = os.path.dirname(ep_path)
    for sub in sub_list:
        fullpath = os.path.join(basedir, sub)
        if sub.endswith('ass'):
            header = get_subtitle_header(fullpath, True)
            title_parsed = parse_external_trackname(ep_path, sub)
            title_parsed['identified_lang'] = identify_lang_in_dialog(fullpath)
            approuved_track = ask_user_input(header, title_parsed, guess)
            approuved_track.filepath = os.path.join(basedir, sub)
            sub_list_ok.append(approuved_track)
        if sub.endswith('srt') or sub.endswith('ssa'):
            title_parsed = parse_external_trackname(ep_path, sub)
            title_parsed['identified_lang'] = identify_lang_in_dialog(fullpath)
            approuved_track = ask_user_input({}, title_parsed, guess)
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
    try:
        content = get_subtitle_file_content(sub_path)
        sub = read_ass(content)
        sub = dict(sub.script_info)
        if cleaning:
            sub = clean_header(sub)
        return sub
    except Exception as e:
        LOG.error(f'Could not read subtitle header {e} on:')
        LOG.error(sub_path)
        return {}


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
    try:
        all_events = read_ass(ass_events).events
        dialog_list = []
        limit_line = 400
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
    except Exception as e:
        LOG.error(f'Could not read dialog lines (event) {e}')
        return ''


def read_srt_dialogs(content: str) -> str:
    timecode = r'\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}'
    cleaned = re.sub(timecode, '', content)
    cleaned = '\n'.join(line.strip()
                        for line in cleaned.splitlines() if line.strip())
    return cleaned.replace('\n', ' ')


def read_sub_file(sub_path: str) -> str:
    try:
        num_lines: int = 400
        with open(sub_path, 'r') as file:
            file_content = ""
            lines_read = 0
            for line in file:
                file_content += line
                lines_read += 1
                if num_lines is not None and lines_read >= num_lines:
                    break
            return file_content
    except Exception as e:
        LOG.error(e)
        return ''


def build_track_flags(track: TrackInfo) -> str:
    i = '0'
    tn = f'--track-name {i}:\"{track.trackname_combined}\"'
    td = f'--default-track-flag {i}:{str(track.is_default).lower()}'
    te = f'--track-enabled-flag {i}:true'
    tf = f'--forced-display-flag {i}:{str(track.is_forced).lower()}'
    hi = f'--hearing-impaired-flag {i}:{str(track.is_sdh).lower()}'
    tl = f'--language {i}:\"{track.language_ietf}\"'
    file = f'\"{str(track.filepath)}\"'
    fullstring = f'{td} {te} {tf} {hi} {tn} {tl} {file}'
    return fullstring


def sync_subtitles(ref: str, unsync: str,
                   cwdir: str = '') -> str:
    bname = os.path.basename(unsync)
    refbname = os.path.basename(ref)
    sync_path = f'{TEMP_FOLDER}subs/synced.{bname}'
    if cwdir == '':
        cwdir = f'{TEMP_FOLDER}subs/'
    if not os.path.exists(cwdir):
        os.makedirs(cwdir)
    ext = os.path.splitext(unsync)[1]
    cmd = f'ffsubsync {refbname} -i \"{bname}\" -o s{ext}'
    LOG.debug(cmd)
    out = subprocess.run(cmd, shell=True, check=True,
                         cwd=cwdir, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, text=True)
    out_txt = f'{out.stdout}{out.stderr}'
    LOG.info(out_txt)
    if check_sync_offset(out_txt):
        shutil.move(f'{cwdir}s{ext}', sync_path)
        return sync_path
    else:
        return unsync


def check_sync_offset(out: str) -> bool:
    pattern = r'offset seconds: (-?\d+\.\d+)'
    matchre = re.search(pattern, out)
    offset: float = 0.0
    if matchre:
        offset: float = float(matchre.group(1))
        if offset < -2.0 or offset > 2.0:
            LOG.warning('Subtitles won\' be syncronized due too big offset'
                        ' it might be a mistake')
            return False
        else:
            return True
    else:
        return False


def export(video_file: str, track_id: str | int, path: str) -> str:
    cmd = [
        f"mkvextract tracks \"{video_file}\" {str(track_id)}:\"{path}\""]
    LOG.debug(cmd)
    subprocess.run(cmd, shell=True, check=True)
    return path


class SubSync():
    def __init__(self, refmkv: list[TrackInfo],
                 unsync: list[TrackInfo],
                 vpath: str):
        self._ref: list[TrackInfo] = refmkv
        self._un: list[TrackInfo] = unsync
        reflang: list[str] = []
        refpath = f'{TEMP_FOLDER}subs/ref'
        for r in refmkv:
            reflang.append(str(r.language_ietf))
        for t in unsync:
            if t.to_remux:
                t.filepath = shutil.copy(
                    str(t.filepath), f'{TEMP_FOLDER}subs/')
                lngstr = str(t.language_ietf)
                lng_match = closest_match(lngstr, reflang, 100)
                lngdiplay = Language.make(lng_match[0]).display_name()
                LOG.debug(f'Closest matching language: \'{lngdiplay}\' '
                          f'with distance {lng_match[1]}/100')
                for r in refmkv:
                    if r.language_ietf in lng_match or 'und' in lng_match:
                        if r.is_forced == t.is_forced:
                            if 'sup' not in str(r.subtype):
                                ref = export(vpath, str(r.trackId),
                                             f'{refpath}.{str(r.subtype)}')
                                try:
                                    t.filepath = sync_subtitles(
                                        ref, str(t.filepath))
                                    break
                                except Exception as e:
                                    LOG.error(e)
                                    break

    @property
    def syncronized(self) -> list[TrackInfo]:
        return self._un

    def del_temp(self) -> None:
        temp_folder = f'{TEMP_FOLDER}subs/'
        if os.path.exists(temp_folder) and os.path.isdir(temp_folder):
            files = os.listdir(temp_folder)
            if files:
                for file in files:
                    file_path = os.path.join(temp_folder, file)
                    if os.path.isfile(file_path):
                        os.remove(file_path)


class Episode():
    def __init__(self):
        self._serie_id = ""
        self._serie_title = ""
        self._ep_id = ""
        self._ep_file_exist = False
        self._external_tracks: list[TrackInfo] = []
        self._number = ""
        self._season = ""
        self._video_path = ""
        self._serie_path = ""
        self._sonarr_var = None
        self._release = ""
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
    def serie_title(self) -> str:
        return self._serie_title

    @serie_title.setter
    def serie_title(self, name: str):
        self._serie_title = name

    @property
    def ep_id(self):
        return self._ep_id

    @ep_id.setter
    def ep_id(self, id: int | str):
        self._ep_id = str(id)

    @property
    def release(self) -> str:
        if self._release == 'None' or self._release == '':
            return 'Anonymous'
        else:
            return self._release

    @release.setter
    def release(self, rel: str):
        self._release = rel

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
        self._serie_title = value.get("sonarr_series_title")

    def copy_temp(self) -> str:
        LOG.debug(f'Make temp copy of {self._video_path}')
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
        self._temp_folder = TEMP_FOLDER

    @property
    def subs(self) -> list[TrackInfo]:
        return self.__subs

    @property
    def too_big(self) -> bool:
        size_in_bytes = os.path.getsize(self._video_path)
        size_in_mb = int(size_in_bytes / (1024 * 1024))
        track_number = len(self.__subs)
        return size_in_mb > 200 or track_number > 1

    def analyze(self, json_data: dict = {}, video_path: str = "") -> bool:
        self.__subs = []
        subfounds = False
        if not json_data:
            json_data = self._tracks
        if video_path == "":
            video_path = self._video_path
        if (json_data.get("tracks") is not None):
            for track in json_data["tracks"]:
                if track["type"] == "subtitles":
                    subfounds = True
                    self._analyze_sub_track(track, video_path)
        if subfounds:
            LOG.debug(f'Subtitles found for {video_path}')
        else:
            LOG.debug(f'No subtitle tracks for {video_path}')
        return subfounds

    def _analyze_sub_track(self, track: dict, video_path: str) -> None:
        try:
            s = TrackInfo()
            s.filepath = video_path
            track_props = track["properties"]
            sub_type = track_props.get("codec_id", track.get('codec'))
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
        except Exception as e:
            LOG.error(f'Can\'t dertermine subtitle {e}')

    def identify(self, video_file: str) -> bool:
        json_data = ""
        cmd = [f"mkvmerge -i -J \"{video_file}\""]
        LOG.debug(cmd)
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
        result = "und"
        tempy = f'{TEMP_FOLDER}subid.{sub_extention}'
        if sub_extention in text_subs:
            sub_path = self.export(video_file, track_id, tempy)
            result = identify_lang_in_dialog(sub_path)
        return result

    def export(self, video_file: str, track_id: str | int, path: str) -> str:
        try:
            cmd = [
                f"mkvextract tracks \"{video_file}\" {str(track_id)}:\"{path}\""]
            LOG.debug(cmd)
            subprocess.run(cmd, shell=True, check=True)
            return path
        except Exception as e:
            LOG.error(f'Could not export track: {e}')
            return path

    def import_tracks(self, track_list: list[TrackInfo], vpath: str):
        mkv_path: str = vpath
        mkv_name: str = os.path.basename(mkv_path)
        temp_dir: str = os.path.join(self._temp_folder, 'import/', mkv_name)
        i: int = 0
        cmd: str = f'mkvmerge -o \"{temp_dir}\" \"{mkv_path}\"'
        for t in track_list:
            if t.to_remux:
                cmd = f'{cmd} {build_track_flags(t)}'
                i += 1
        if i > 0:
            LOG.debug(f'Muxing new track(s) into {self._video_path}')
            LOG.debug(cmd)
            subprocess.run(cmd, shell=True, check=True)
            shutil.copy(temp_dir, os.path.dirname(self._video_path))
            os.remove(temp_dir)


class Sonarr():
    def __init__(self, export_external_tracks=False) -> None:
        LOG.debug('init Sonarr()')
        self._sonarr = SonarrAPI(SONARR_HOST_URL, SONARR_API)
        self._series = []
        self._episode_list = []
        self._bool_export_ext_tracks = export_external_tracks
        self._guess_ext_tracks = False
        self._external_tracks: list[TrackInfo] = []
        self._ep: Episode
        self._serie_id = ''

    # tvdbid, seasonnumber, episodenumber, releasegroup

    def external_tracks_guess_method(self, folder: str = ''):
        if self._bool_export_ext_tracks:
            if self._test_external_tracks(folder):
                print('You can let the program guess every flags for the'
                      'external tracks, are you sure of the file organisation?')
                print(f'Check folder: {folder}')
                method = input('[y/N]: ')
                if method.lower().startswith('y'):
                    self._guess_ext_tracks = True

    def _test_external_tracks(self, directory: str) -> bool:
        root_directory = directory
        valid_extensions = ['ass', 'ssa', 'srt', 'sub', 'sup']
        f_list = []
        for root, dirs, files in os.walk(root_directory):
            for file in files:
                file_name, file_extension = os.path.splitext(file)
                if file_extension.lstrip('.').lower() in valid_extensions:
                    f_list.append(file)
        return True if len(f_list) > 0 else False

    @property
    def series(self) -> list:
        series = self._sonarr.get_series()
        self._series = series
        LOG.debug(f'Get serie list from sonarr - Lenght: {len(series)}')
        return self._series

    def episode_list(self, serie_id: int | str) -> list:
        self._serie_id = serie_id
        ep_list = self._sonarr.get_episode(serie_id, series=True)
        self._episode_list = ep_list
        LOG.debug(
            f'Get ep list for serie: {serie_id} - Lenght: {len(ep_list)} eps')
        return self._episode_list

    def episode(self, ep_id: int | str) -> Episode:
        ep = Episode()
        sonarr_ep = self._sonarr.get_episode(ep_id, series=False)
        ep.ep_id = ep_id
        ep.serie_id = self._serie_id
        ep.serie_title = sonarr_ep['series'].get('title')
        if 'episodeFile' not in sonarr_ep:
            LOG.warning(f'No file for episodeID: {ep.ep_id} '
                        f'S{sonarr_ep.get("seasonNumber")}'
                        f'E{sonarr_ep.get("episodeNumber")}')
        if 'episodeFile' in sonarr_ep:
            ep.tvdbid = sonarr_ep['series'].get('tvdbId')
            ep.season = sonarr_ep.get('seasonNumber')
            ep.number = sonarr_ep.get('episodeNumber')
            ep.video_path = sonarr_ep['episodeFile'].get('path')
            ep.serie_path = sonarr_ep['series'].get('path')
            ep.release = sonarr_ep['episodeFile'].get('releaseGroup')
            if self._bool_export_ext_tracks:
                self._ep = ep
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
            guess = self._guess_ext_tracks
            LOG.info(f'External subtitles found alongside the episode: '
                     f'{len(track_list)} track(s) present in folder')
            self._external_tracks = build_subtitle_tags(
                ep_path, track_list, guess)
            self._move_ext_tracks()

    def _move_ext_tracks(self) -> None:
        ep = self._ep
        tracks = self._external_tracks
        sub_dir = f'{SUBTITLE_PATH}{ep.tvdbid}/S{ep.season}/E{ep.number}/'
        LOG.debug('Moving external tracks')
        for t in tracks:
            t.episode = ep.number
            t.season = ep.season
            dst = (f'{sub_dir}{subtitle_export_name(t)}')
            if not os.path.exists(sub_dir):
                LOG.debug(f'{sub_dir} doesn\'t exist, creating parents dir')
                os.makedirs(sub_dir)
            LOG.debug(dst)
            shutil.move(str(t.filepath), dst)


class Subtitles():
    def __init__(self) -> None:
        self.__subs_list: list[TrackInfo] = []

    @ property
    def subs_list(self) -> list[TrackInfo]:
        return self.__subs_list

    def compare_with_mkv(self, mkv_tracks: list[TrackInfo]) -> list[TrackInfo]:
        LOG.debug('Comparing external tracks with MKV')
        sub_tracks = self.subs_list
        if len(sub_tracks) > 0:
            for sub_track in sub_tracks:
                lang = str(sub_track.language_ietf)[:2]
                n = str(sub_track.trackname_combined)
                e = str(sub_track.subtype)
                for mkv_track in mkv_tracks:
                    mkv_lang = str(mkv_track.language_ietf)[:2]
                    mkv_n = str(mkv_track.trackname_combined)
                    mkv_e = str(mkv_track.subtype)
                    if lang in mkv_lang and n in mkv_n and e in mkv_e:
                        sub_track.to_remux = False
                        LOG.debug(f'Track already exists: {mkv_n}')
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
