import os
import argparse
# import sys
# import subprocess
# import py3langid as langid
# from iso639 import Lang
# from langcodes import Language
# from langcodes import standardize_tag
# from pysubparser import parser
# import ass
# from ass_tag_parser import parse_ass
from episodus import Episode
from episodus import Tracks
from episodus import Sonarr
from episodus import Subtitles
import configus

GRABING_FOLDER = configus.CONF_GRABING_FOLDER
SUBTITLE_PATH = configus.CONF_SUBTITLE_PATH
PROGRESS_FOLDER = configus.CONF_PROGRESS_FOLDER

to_remux = False
export_external_tracks = False


def export_all_from_sonarr():
    global export_external_tracks
    sonarr = Sonarr(export_external_tracks)
    all_series = sonarr.series
    for serie in all_series:
        serie_id = serie.get("id")
        serie_tvid = serie.get("tvdbId")
        ep_list = sonarr.episode_list(serie_id)
        already_done = read_progress_sonarr()
        if str(serie_id) not in already_done:
            for episode in ep_list:
                monitored = episode.get("monitored")
                if monitored:
                    ep_id = episode.get("id")
                    episodeInfo = sonarr.episode(ep_id)
                    if 'episodeFile' in episodeInfo:
                        epFile = episodeInfo["episodeFile"]
                        ep_path = epFile.get("path")
                        season_num = f"{episodeInfo.get('seasonNumber'):02d}"
                        release = epFile.get('releaseGroup')
                        ep_num = f"{episodeInfo.get('episodeNumber'):02d}"
                        export_ep(ep_path, serie_tvid,
                                  ep_num, season_num, release)
        save_progress_sonarr(serie_id)


def export_ep(ep_path: str,
              tvid: str,
              ep_num: str,
              season: str,
              rel_group: str) -> None:
    global to_remux
    tracks = Tracks()
    subs = Subtitles()
    ep = Episode()
    subs_folder = f"{SUBTITLE_PATH}{tvid}/S{season}/E{ep_num}/"
    subs.analyze_folder(subs_folder)
    ep.video_path = ep_path
    if tracks.identify(ep_path):
        tracks.analyze()
        if tracks.too_big:
            video_path = ep.copy_temp()
        else:
            video_path = ep.video_path
        for t in tracks.subs:
            sub_path_full = (f"{subs_folder}"
                             f"S{season}.E{ep_num}."
                             f"[{rel_group}]-[{t.trackname}]."
                             f"{t.default}"
                             f"{t.language_ietf}."
                             f"{t.forced}"
                             f"{t.subtype}")
            tracks.export(video_path, str(t.trackId), sub_path_full)
            # if not args.all or args.reset, only on standard queue
            # eport temp subtitle track for syncronization with ffsubsync
            # remux prev external subs with new video and try to sync new subs
        ep.delete_temp()
        if to_remux:
            subs.compare_with_mkv(tracks.subs)
            test = subs.subs_list
            print('Remuxing old sub tracks with new video file')


def get_sonarr_var(data_file_path):
    data_from_file = {}
    with open(data_file_path, "r") as file:
        for line in file:
            line = line.strip()
            if line.startswith("#"):
                continue  # Skip comments
            key, value = line.split("=", 1)
            data_from_file[key] = value
    return data_from_file


def treat_queue_from_sonarr(source_folder) -> None:
    # Get a list of all files in the source folder
    ep = Episode()
    sonarr = Sonarr()
    files = os.listdir(source_folder)
    for file in files:
        file_path_full = os.path.join(source_folder, file)
        ep.sonarr_var = get_sonarr_var(file_path_full)
        monitored = sonarr.is_monitored(ep.ep_id)
        if monitored:
            export_ep(ep.video_path, ep.tvdbid,
                      ep.number, ep.season, ep.release)
        os.remove(file_path_full)


def save_progress_sonarr(serie_id: int | str) -> None:
    try:
        already_done = read_progress_sonarr()
        with open(PROGRESS_FOLDER, 'a+') as file:
            if str(serie_id) not in already_done:
                file.write(f'{str(serie_id)};')
    except Exception as e:
        print(f'An error occured: {e}')


def read_progress_sonarr() -> list:
    try:
        with open(PROGRESS_FOLDER, 'r') as file:
            series = file.read()
            serie_ids = [serie.strip()
                         for serie in series.split(';')
                         if serie.strip()]
            return serie_ids
    except FileNotFoundError:
        return []
    except Exception as e:
        print(f'An error occured: {e}')
        return []


def reset_progress_sonarr() -> None:
    with open(PROGRESS_FOLDER, 'w') as file:
        file.flush()
        pass


def main():
    global to_remux
    global export_external_tracks
    arg = argparse.ArgumentParser(
        description='Sonarr Subtitle (Auto)Managerr')
    arg.add_argument('-a', '--all', action='store_true',
                     help='Export all episode from Sonarr')
    arg.add_argument('-r', '--reset', action='store_true',
                     help='Reset from the benginginn')
    arg.add_argument('-g', '--grabs', action='store_true',
                     help='Treat queue from the grabing folder')
    arg.add_argument('-m', '--remux', action='store_true',
                     help='Remux external tracks to new video file')
    arg.add_argument('-x', '--external', action='store_true',
                     help='Export external tracks from season folder')
    args = arg.parse_args()
    if args.external:
        export_external_tracks = True
    if args.remux:
        to_remux = True
    if args.reset:
        to_remux = False
        reset_progress_sonarr()
        export_all_from_sonarr()
    if args.all and not args.reset:
        to_remux = False
        export_all_from_sonarr()
    if args.grabs:
        treat_queue_from_sonarr(GRABING_FOLDER)
    if not any(vars(args).values()):
        treat_queue_from_sonarr(GRABING_FOLDER)


if __name__ == "__main__":
    main()
    # tvdbid, seasonnumber, episodenumber, releasegroup
