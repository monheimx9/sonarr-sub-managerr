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

While also having the ability to fully export your entire collection

The subtitles will be saved using that nomenclature 

/subtitles/*tvdbid*/SEASON/EPISODE/SXX.EXX.[Release-Group]-[Trackname].default-flag.track-lang.forced-flag.extention

I also want the script to parse subtitle files (*ass, ssa, srt*) to guess their language if there's no metadata available from the container

## Usage
The queue will be treated from the text files generated from Sonarr

Sonarr calls a shell script **subs.sh** that generate a text file with all the necessary environment variables

Then python read from those text files and delete them after the operation is completed

From Sonarr, go to Settings->Connect->Add new

Select *On Import*  and *On Upgrade* and add the path to the shell script



## Features
- [x] Treat queue from Sonarr grab folder ./grabs/ -g (--grab)
- [ ] Switch to verbose mode -v (--verbose)
- [x] Export the entire Sonarr collection -a (--all) (Start from the last exported serie)
- [x] Reset export from the Start -r (--reset)
- [ ] Having a prompt and input to ask for user guidance on certain events
- [ ] Choose between only export or remux with new upgraded episode -m (--re*m*ux)
- [ ] Export external tracks already present in the season folder -x (--e*x*ternal)
- [ ] Re-sync subtitles with [ffsubsync](https://github.com/smacke/ffsubsync)
- [ ] Parse subtitles files to guess language

