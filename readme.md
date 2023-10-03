# sonarr-sub-managerr

**A simple subtitles (automatic)manager for Sonarr written in python**

- Work in progress
- The code is quite ugly because this is my *I'm learning Python* project
- Feel free to participate in the project if you feel so
- I'm not really that comfortable with github either so expect some weird commits and no proper release tag at this moment
- There might be a Docker version in the future

## Goal
The goal is to mostly automate the extraction and remuxing of subtitles when you upgrade episodes from a serie

The idea is to export every subtitle tracks after the *on import* or *on upgrade* events from Sonarr

While also retaining the ability to fully export your entire collection

The subtitles will be saved using that nomenclature 

/subtitles/**tvdbid**/SXX/EXX/SXX.EXX.[Release-Group]-[Trackname].default-flag.track-lang.forced-flag.extention

**In exemple**

*/subtitles/305074/S03/E03/S03.E03.\[Tsundere-raws\]-\[Sous-titres complets ADN\].default.fr.ass*

*/subtitles/375271/S01/E01/S01.E01\[EMBER\]-\[Signs & Songs-L.Y\].en.forced.ass*

I choose to export with the TvDbID as folder name rather than the SonarrID to avoid conflicts

I also want the script to parse subtitle files (*ass, ssa, srt*) to guess their language if there's no metadata available from the container using language identification *langid*

## Usage
The queue will be treated from the text files generated from Sonarr

Sonarr calls a shell script **subs.sh** that generate a text file with all the necessary environment variables

Then python read from those text files and delete them after the operation is completed

From Sonarr, go to Settings->Connect->Add new

Select *On Import*  and *On Upgrade* and add the path to the shell script

In order to use the function **export all** from Sonarr, you need to configure Sonarr's host ip address as well as the API key in [configus.py](https://github.com/monheimx9/sonarr-sub-managerr/blob/main/configus.py)

You can also modify the language tags (IETF [BCP47](https://datatracker.ietf.org/doc/html/rfc5646)) in the config file

Then start the script using the arguments bellow when there's at least one episode imported or upgraded

By default **unmonitored** episodes aren't treated, not in full export, nor when the queue is treated

## Features
- [x] Treat queue from Sonarr grab folder ./grabs/ -g (--**g**rab)
- [ ] Switch to verbose mode -v (--**v**erbose)
- [x] Export the entire Sonarr collection -a (--**a**ll) (Start from the last exported serie)
- [x] Reset export from the Start -r (--**r**eset)
- [ ] Having a prompt and input to ask for user guidance on certain events
- [ ] Correct mkv properties with mkvpropedit if language is undefined and can be identified
- [x] Choose between only export or remux with new upgraded episode -m (--re**m**ux)
- [x] Export external tracks already present in the season folder -x (--e**x**ternal)
- [ ] Re-sync subtitles with [ffsubsync](https://github.com/smacke/ffsubsync)
- [ ] Parse subtitles files to guess language

## Knows issues and caveats
Sometimes it happen that you might have one video file that covers multiple episodes (like a Kai version or a special release)

In those edge cases I suggest to not monitor the episodes in question before launching the program, I didn't dig enough for the moment to cover this use case

If you have external subtitle tracks in your shows collection, the naming conventions follows [Jellyfin](https://jellyfin.org/docs/general/server/media/external-files/) external files naming scheme

*Film_Or_Episode.trackname.default.en.forced.ass*

So be aware that it hasn't been tested with PLEX

At this day 09/19/2023, it has only been tested with Sonarr 3.0.10.1567
I'm not planning to move to Sonarr 4 until a stable version is out

