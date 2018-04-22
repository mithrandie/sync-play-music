#!/usr/bin/env python
#-*-coding: utf-8 -*-

from datetime import datetime
from gmusicapi import Mobileclient
from gmusicapi import Musicmanager
import logging
import mutagen
import os
from os import path
import sys
import yaml

BLACK, RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE = range(8)

reload(sys)
sys.setdefaultencoding('utf-8')

logging.basicConfig(filename='sync-play-music.log',level=logging.DEBUG)
configFile = path.join(path.abspath(path.dirname(__file__)), "config.yml")

def exit_with_error(message, code = 0):
    logging.error(message)
    sys.stderr.write("\x1b[1;%dm" % (30 + RED) + message + "\x1b[0m\n")
    sys.exit(code)

def warn(message):
    logging.warning(message)
    sys.stdout.write("\x1b[1;%dm" % (30 + YELLOW) + message + "\x1b[0m\n")

def info(message):
    logging.info(message)
    sys.stdout.write("\x1b[1;%dm" % (30 + GREEN) + message + "\x1b[0m\n")

def log(message):
    logging.info(message)

def message(message):
    logging.info(message)
    sys.stdout.write(message + "\n")


def get_config(configPath, default=''):
    return search_config(config, configPath.split('.'), default)

def search_config(config_tree, items, default):
    if items[0] in config_tree:
        config_tree = config_tree[items.pop(0)]
        if len(items) < 1:
            return config_tree
        else:
            return search_config(config_tree, items, default)
    else:
        return default


logging.info("######## STARTED at %s ########" % datetime.now().isoformat())

if False == path.isfile(configFile):
    exit_with_error("Config file does not exist.")

try:
    with open(configFile, 'r') as f:
        config = yaml.load(f)
except Exception as e:
    exit_with_error("Cannot read config file:" + str(e))


manager = Musicmanager()
if False == manager.login():
    warn("Please authorize your account and re-run this script.")
    manager.perform_oauth()
    sys.exit(0)

client = Mobileclient()
if False == client.login(get_config("Auth.Account"), get_config("Auth.Password"), Mobileclient.FROM_MAC_ADDRESS):
    exit_with_error("Authorization failed.")


message("Retriving Uploaded Songs...")
library = client.get_all_songs()

storedTracks = {}
deletedTrackList = []
duplicateTrackList = []
for track in library:
    trackInfo = {
            "id": track["id"],
            "title": track["title"],
            "album": track["album"] if "album" in track else "",
            "artist": track["artist"] if "artist" in track else "",
            "discNumber": track["discNumber"] if "discNumber" in track else 0,
            "trackNumber": track["trackNumber"] if "trackNumber" in track else 0
            }

    if track["deleted"]:
        deletedTrackList.append(trackInfo)
    else:
        trackKey = (
                track["title"],
                track["album"] if "album" in track else "",
                track["artist"] if "artist" in track else "",
                track["discNumber"] if "discNumber" in track else 0,
                track["trackNumber"] if "trackNumber" in track else 0
                )

        if trackKey in storedTracks:
            duplicateTrackList.append(trackInfo)
        else:
            storedTracks[trackKey] = trackInfo

info("Songs on Play Music: %d, Deleted: %d, Duplicate: %d" % (len(storedTracks), len(deletedTrackList), len(duplicateTrackList)))


message("Searching Local Songs...")
localTracks = {}
incompatibleTrackList = []
localDuplicateTrackList = []
directories = get_config("Upload.Directories")
for dir in directories:
    if False == path.isdir(dir):
        exit_with_error("Directory does not exist: %s" % dir)

    for root, _, files in os.walk(dir):
        for filename in files:
            filepath = path.join(root, filename)
            _, ext = path.splitext(filepath)

            if ext not in [".mp3", ".m4a", ".flac"]:
                continue

            media = mutagen.File(filepath)
            if media is None:
                continue

            incompatible = False

            mediaType = media.__class__.__name__
            if mediaType == "MP3":
                trackInfo = {
                        "title": media["TIT2"].text[0],
                        "album": media["TALB"].text[0] if "TALB" in media else "",
                        "artist": media["TPE1"].text[0] if "TPE1" in media else "",
                        "discNumber": int(media["TPOS"].text[0].split("/")[0]) if "TPOS" in media else 0,
                        "trackNumber": int(media["TRCK"].text[0].split("/")[0]) if "TRCK" in media else 0,
                        "filepath": filepath
                        }
            elif mediaType == "FLAC":
                trackInfo = {
                        "title": media["title"][0],
                        "album": media["album"][0] if "album" in media else "",
                        "artist": media["artist"][0] if "artist" in media else "",
                        "discNumber": int(media["discnumber"][0].split("/")[0]) if "discnumber" in media else 0,
                        "trackNumber": int(media["tracknumber"][0].split("/")[0]) if "tracknumber" in media else 0,
                        "filepath": filepath
                        }
            elif mediaType == "MP4":
                trackInfo = {
                        "title": media["\xa9nam"][0],
                        "album": media["\xa9alb"][0] if "\xa9alb" in media else "",
                        "artist": media["\xa9ART"][0] if "\xa9ART" in media else "",
                        "discNumber": int(media["disk"][0][0]) if "disk" in media else 0,
                        "trackNumber": int(media["trkn"][0][0]) if "trkn" in media else 0,
                        "filepath": filepath
                        }

                if media.info.codec == "alac":
                    if media.info.bits_per_sample != 16:
                        incompatible = True
                elif media.info.codec.startswith("mp4a.40."):
                    None
                else:
                    continue
            else:
                continue

            if incompatible:
                incompatibleTrackList.append(trackInfo)
            else:
                trackKey = (
                        trackInfo["title"],
                        trackInfo["album"],
                        trackInfo["artist"],
                        trackInfo["discNumber"],
                        trackInfo["trackNumber"]
                        )

                if trackKey in localTracks:
                    localDuplicateTrackList.append(trackInfo)
                else:
                    localTracks[trackKey] = trackInfo

info("Songs on Local: %d, Incompatible: %d, Duplicate: %d" % (len(localTracks), len(incompatibleTrackList), len(localDuplicateTrackList)))


message("Deleting...")
deleteSongs = []
deleteTracks = []
for track in duplicateTrackList:
    deleteSongs.append(track["id"])
    deleteTracks.append(track)

for trackKey, track in storedTracks.items():
    if trackKey not in localTracks:
        deleteSongs.append(track["id"])
        deleteTracks.append(track)

if 0 < len(deleteSongs):
    client.delete_songs(deleteSongs)
    for track in deleteTracks:
        message("Deleted: %s from %s <%s>" % (track["title"], track["album"], track["artist"]))

info("Delete on Play Music has been completed: %s song(s)" % len(deleteSongs))


message("Uploading...")
uploadSongs = []
for trackKey, track in localTracks.items():
    if trackKey not in storedTracks:
        uploadSongs.append(track["filepath"])

if 0 < len(uploadSongs):
    result = manager.upload(uploadSongs)
    info("  Uploaded: %d, Not Uploaded: %d" % (len(result[0]), len(result[2])))

    uploaded = result[0]
    for f in uploaded.keys():
        message("    Uploaded: %s" % f)

    notUploaded = result[2]
    for f, r in notUploaded.items():
        message("    Not Uploaded: [%s] %s" % (f, r))

info("Upload to Play Music has been completed: %s song(s)" % len(uploadSongs))


logging.info("######## TERMINATED at %s ########" % datetime.now().isoformat())
sys.exit(0)

