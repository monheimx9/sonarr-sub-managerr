from os.path import isdir
from os import path
import re
import shutil
from langcodes import Language
from langcodes import standardize_tag
from pyarr import SonarrAPI
import json
import os
import subprocess
import configus

SONARR_HOST_URL = configus.CONF_SONARR_HOST_URL
SONARR_API = configus.CONF_SONARR_API
TEMP_FOLDER = configus.CONF_TEMP_FOLDER
DEFAULT_LANG = configus.CONF_DEFAULT_LANG


class Episode():
    def __init__(self):
        self._number = ""
        self._season = ""
        self._video_path = ""
        self.serie_path = ""
        self._sonarr_var = None
        self.release = ""
        self.tvdbid = ""
        self._copy_temp_path = ""
        self._temp_folder = TEMP_FOLDER

    @property
    def temp_path(self) -> str:
        return self._copy_temp_path

    @property
    def video_path(self) -> str:
        return self._video_path

    @video_path.setter
    def video_path(self, new_path: str) -> None:
        self._video_path = new_path

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


class Tracks():
    def __init__(self):
        self._audio = []
        self.__subs = []
        self._tracks = {}
        self._video_path = ""

    @property
    def subs(self) -> list:
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
        default = ""
        track_props = track["properties"]
        sub_type = track_props.get("codec_id")
        sub_type_extention = self.extension(sub_type)
        track_id = track["id"]
        is_forced = track_props.get("forced_track", False)
        if is_forced:
            forced_flag_txt = "forced."
        else:
            forced_flag_txt = ""
        track_name = track_props.get("track_name", "und")
        track_name = track_name.replace(r"/", "#")
        if track_name != "und" and not is_forced:
            if "signs" in track_name.lower():
                is_forced = True
                forced_flag_txt = "forced."
            elif "songs" in track_name.lower():
                is_forced = True
                forced_flag_txt = "forced."
            elif "forc" in track_name.lower():
                is_forced = True
                forced_flag_txt = "forced."
        track_lang_ietf = track_props.get("language_ietf", "und")
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
                default = "default."
        if track_lang_ietf != 'und':
            track_lang = track_lang_ietf
        else:
            track_lang = standardize_tag(track_lang)
        track_info = {"track_id": track_id,
                      "sub_type_extention": sub_type_extention,
                      "track_name": track_name,
                      "forced_flag_txt": forced_flag_txt,
                      "track_lang": track_lang,
                      "default": default}
        self.__subs.append(track_info)

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

    def extension(self, sub_type) -> str:
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

    def guess_lang(self, track_name):
        try:
            track_lang = Language.find(track_name)
            return track_lang
        except LookupError:
            print("Unable to determine language for subtitle track")
            return False

    def guess_lang_harder(self, video_file, track_id, sub_extention):
        result = ""
        if sub_extention:
            sub_path = self.export(video_file, track_id,
                                   "./caca" + sub_extention)
        return result

    def read_ass_sub(self):
        pass

    def read_ssa_sub(self):
        pass

    def read_srt_sub(self):
        pass

    def export(self, video_file: str, track_id: str | int, path: str) -> str:
        cmd = [
            f"mkvextract tracks \"{video_file}\" {str(track_id)}:\"{path}\""]
        print(cmd)
        subprocess.run(cmd, shell=True, check=True)
        return path


class Sonarr():
    def __init__(self) -> None:
        self._sonarr = SonarrAPI(SONARR_HOST_URL, SONARR_API)
        self._series = []
        self._episode_list = []
        self._episode_path = []

    # tvdbid, seasonnumber, episodenumber, releasegroup

    @property
    def series(self):
        series = self._sonarr.get_series()
        self._series = series
        return self._series

    def episode_list(self, serie_id):
        ep_list = self._sonarr.get_episode_file(serie_id, series=True)
        self._episode_list = ep_list
        return self._episode_list


class Subtitles(Tracks):
    def __init__(self) -> None:
        self.__subs_list = []

    @property
    def subs_list(self):
        return self.__subs_list

    def analyze_folder(self, folder_path: str) -> list:
        if isdir(folder_path):
            all_subs = os.listdir(folder_path)
            if len(all_subs) > 0:
                for subtitle in all_subs:
                    full_path = path.join(folder_path, subtitle)
                    subtitle_track = self.subtitle_info_from_file(full_path)
                    self.__subs_list.append(subtitle_track)
        return self.__subs_list

    def subtitle_info_from_file(self, file_path: str) -> dict:
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
        sub = {'base_dir': base_dir,
               'file_name': file_name,
               'default_flag': is_default,
               'forced_flag': is_forced,
               'season': season,
               'episode': episode,
               'trackname': f'[{rel_group}]-[{trackname}]',
               'subtype': sub_extention,
               'language_ietf': lang_}
        return sub
