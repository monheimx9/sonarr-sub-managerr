import os
import argparse
# from iso639 import Lang
# from pysubparser import parser
# import ass
from episodus import Episode, SubSync, subtitle_export_name
from episodus import MkvAnalyzer
from episodus import Sonarr
from episodus import Subtitles
import configus

GRABING_FOLDER = configus.CONF_GRABING_FOLDER
SUBTITLE_PATH = configus.CONF_SUBTITLE_PATH
PROGRESS_FOLDER = configus.CONF_PROGRESS_FOLDER
LOG = configus.CONF_LOGGER

to_remux = False
export_external_tracks = False


def export_all_from_sonarr():
    LOG.info('Exporting sonarr\'s entire collection')
    global export_external_tracks
    sonarr = Sonarr(export_external_tracks)
    all_series = sonarr.series
    already_done = read_progress_sonarr()
    current_serie: int = 0
    total_series: int = len(all_series)
    for serie in all_series:
        current_serie += 1
        serie_id = serie.get("id")
        serie_tvid = serie.get("tvdbId")
        if str(serie_id) not in already_done:
            LOG.info(f'Current serie progress: {current_serie}/{total_series}')
            ep_list = sonarr.episode_list(serie_id)
            export_episodes(ep_list, sonarr, serie.get(
                'title'), serie_tvid, serie.get('path'))
            save_progress_sonarr(serie_id)


def export_specific_serie(serieID: int, is_tvdbid: bool = False) -> None:
    so = Sonarr()
    if is_tvdbid:
        s = so.serie(serieID, is_tvdbid)[0]
        s_id = s.get('id')
        eps = so.episode_list(s_id)
        tvid = serieID
    else:
        s = so.serie(serieID, is_tvdbid)
        eps = so.episode_list(serieID)
        tvid = s.get('tvdbId')
        s_id = serieID
    s_title = s.get('title')
    s_path = s.get('path')
    export_episodes(eps, so, s_title, tvid, s_path)
    save_progress_sonarr(s_id)


def export_episodes(ep_list, sonarr: Sonarr,
                    s_title: str, tvid, s_path: str) -> None:
    LOG.info(f'Treating tvdbId: {tvid} {s_title}')
    sonarr.external_tracks_guess_method(s_path)
    for episode in ep_list:
        monitored = episode.get("monitored")
        if not monitored:
            LOG.info(
                f'S{episode.get("seasonNumber")}'
                f'E{episode.get("episodeNumber")} not monitored')
        if monitored:
            ep_id = episode.get("id")
            ep = sonarr.episode(ep_id)
            if ep.file_exist:
                ep_path = ep.video_path
                season_num = ep.season
                ep_num = ep.number
                release = ep.release
                export_ep(ep_path, tvid,
                          ep_num, season_num, release)


def export_ep(ep_path: str,
              tvid: str,
              ep_num: str,
              season: str,
              rel_group: str) -> None:
    LOG.info(f'Start: S{season}E{ep_num} from rel. group {rel_group}')
    global to_remux
    mkv = MkvAnalyzer()
    subs = Subtitles()
    ep = Episode()
    subs_folder = f"{SUBTITLE_PATH}{tvid}/S{season}/E{ep_num}/"
    subs.analyze_folder(subs_folder)
    ep.video_path = ep_path
    if mkv.identify(ep_path):
        if mkv.analyze():
            if mkv.too_big:
                video_path = ep.copy_temp()
            else:
                video_path = ep.video_path
            for t in mkv.subs:
                t.release = rel_group
                t.episode = ep_num
                t.season = season
                sub_path_full = (f"{subs_folder}{subtitle_export_name(t)}")
                mkv.export(video_path, str(t.trackId), sub_path_full)
                # if not args.all or args.reset, only on standard queue
            if to_remux:
                ok = False
                subs.compare_with_mkv(mkv.subs)
                for s in subs.subs_list:
                    if s.to_remux:
                        ok = True
                        break
                if ok:
                    synced = SubSync(mkv.subs, subs.subs_list, video_path)
                    mkv.import_tracks(synced.syncronized, video_path)
                    synced.del_temp()
                else:
                    LOG.info('There is not track(s) to remux')
            ep.delete_temp()


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
    LOG.info('Treating queue from last imported/upgraded episodes')
    ep = Episode()
    sonarr = Sonarr()
    files = os.listdir(source_folder)
    for file in files:
        file_path_full = os.path.join(source_folder, file)
        ep.sonarr_var = get_sonarr_var(file_path_full)
        LOG.info(
            f'S{ep.season}E{ep.number} tvdbId: {ep.tvdbid} {ep.serie_title}')
        monitored = sonarr.is_monitored(ep.ep_id)
        if not monitored:
            LOG.info(
                f'S{ep.season}E{ep.number} from {ep.tvdbid} isn\'t monitored')
        if monitored:
            export_ep(ep.video_path, ep.tvdbid,
                      ep.number, ep.season, ep.release)
        LOG.debug(f'Removing {file_path_full}')
        if os.path.exists(file_path_full):
            os.remove(file_path_full)


def save_progress_sonarr(serie_id: int | str) -> None:
    try:
        already_done = read_progress_sonarr()
        with open(PROGRESS_FOLDER, 'a+') as file:
            if str(serie_id) not in already_done:
                file.write(f'{str(serie_id)};')
                LOG.info(f'Progress saved for serie ID: {serie_id}')
    except Exception as e:
        LOG.exception(f'An error occured: {e}')


def read_progress_sonarr() -> list:
    try:
        with open(PROGRESS_FOLDER, 'r') as file:
            series = file.read()
            serie_ids = [serie.strip()
                         for serie in series.split(';')
                         if serie.strip()]
            LOG.debug(f'Last serieID saved in progress is: {serie_ids[-1]}')
            return serie_ids
    except FileNotFoundError:
        LOG.info('Progress file not found')
        return []
    except Exception as e:
        LOG.exception(f'An error occured: {e}')
        return []


def reset_progress_sonarr() -> None:
    LOG.info('Resetting all progress from previous export')
    with open(PROGRESS_FOLDER, 'w') as file:
        file.flush()


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
    arg.add_argument('-S', '--serie', type=int, nargs=1,
                     help='Extract a specific serie by sonarrID')
    arg.add_argument('-T', '--tvdbid', type=int, nargs=1,
                     help='Use tvdbId instead of SonarrID')
    args = arg.parse_args()
    if args.external:
        export_external_tracks = True
        LOG.info('Export external tracks is set to True')
    if args.remux:
        to_remux = True
        LOG.info('Remuxing back to the new video is set to True')
    if args.serie:
        serieID: int = args.serie[0]
        export_specific_serie(serieID, False)
    if args.tvdbid:
        tvdbId: int = args.tvdbid[0]
        export_specific_serie(tvdbId, True)
    if args.reset:
        reset_progress_sonarr()
        export_all_from_sonarr()
    if args.all and not args.reset:
        export_all_from_sonarr()
    if args.grabs:
        treat_queue_from_sonarr(GRABING_FOLDER)
    if not any(vars(args).values()):
        treat_queue_from_sonarr(GRABING_FOLDER)


if __name__ == "__main__":
    main()
    # tvdbid, seasonnumber, episodenumber, releasegroup
