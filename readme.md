# sonarr-sub-managerr

**A simple subtitles (automatic)manager for Sonarr written in python**

Work in progress

## Goal
The goal is to mostly automate the extraction and remuxing of subtitles when you upgrade episodes from a serie

The idea is to export every subtitle tracks after the *on import* or *on upgrade* events from Sonarr

While also having the ability to fully export your entire collection

The subtitles will be saved using that nomenclature /subtitles/*tvdbid*/SEASON/EPISODE/SXX.EXX.[Release-Group]-[Trackname].default-flag.track-lang.forced-flag.extention

## Features
- [x] Treat queue from Sonarr grab folder ./grabs/ -g (--grab)
- [ ] Switch to verbose mode -v (--verbose)
- [x] Export the entire Sonarr collection -a (--all) (Start from the last exported serie)
- [x] Reset export from the Start -r (--reset)
- [ ] Having a prompt and input to ask for user guidance on certain events
- [ ] Choose between only export or remux with new upgraded episode -m (--re*m*ux)
- [ ] Export external tracks already present in the season folder -x (--e*x*ternal)
- [ ] Re-sync subtitles with [ffsubsync](https://github.com/smacke/ffsubsync)


