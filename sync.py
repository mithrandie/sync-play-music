#!/usr/bin/env python
# -*-coding: utf-8 -*-

from datetime import datetime
from gmusicapi import Mobileclient
from gmusicapi import Musicmanager
import logging
import mutagen
from mutagen.flac import FLAC
from mutagen.mp3 import MP3
from mutagen.mp4 import MP4
import os
from os import path
import sys
import yaml

BLACK, RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE = range(8)


def exit_with_error(msg, code=0):
    logging.error(msg)
    sys.stderr.write("\x1b[1;%dm" % (30 + RED) + msg + "\x1b[0m\n")
    sys.exit(code)


def warn(msg):
    logging.warning(msg)
    sys.stdout.write("\x1b[1;%dm" % (30 + YELLOW) + msg + "\x1b[0m\n")


def info(msg):
    logging.info(msg)
    sys.stdout.write("\x1b[1;%dm" % (30 + GREEN) + msg + "\x1b[0m\n")


def log(msg):
    logging.info(msg)


def message(msg):
    logging.info(msg)
    sys.stdout.write(msg + "\n")


def get_config(conf, config_path, default=''):
    return search_config(conf, config_path.split('.'), default)


def search_config(config_tree, items, default):
    if items[0] in config_tree:
        config_tree = config_tree[items.pop(0)]
        if len(items) < 1:
            return config_tree
        else:
            return search_config(config_tree, items, default)
    else:
        return default


def main():
    logging.basicConfig(filename='sync-play-music.log', level=logging.DEBUG)
    config_file = path.join(path.abspath(path.dirname(__file__)), "config.yml")

    log("######## STARTED at %s ########" % datetime.now().isoformat())

    if not path.isfile(config_file):
        exit_with_error("Config file does not exist.")

    config = None

    try:
        with open(config_file, 'r') as f:
            config = yaml.load(f, Loader=yaml.BaseLoader)
    except Exception as e:
        exit_with_error("Cannot read config file:" + str(e))

    client = Mobileclient()
    if not client.oauth_login(Mobileclient.FROM_MAC_ADDRESS):
        warn("Please authorize your account for Music Client and re-run this script.")
        client.perform_oauth()
        sys.exit(0)

    manager = Musicmanager()
    if not manager.login():
        warn("Please authorize your account for Music Manager and re-run this script.")
        manager.perform_oauth()
        sys.exit(0)

    message("Retriving Uploaded Songs...")
    library = client.get_all_songs()

    stored_tracks = {}
    deleted_track_list = []
    duplicate_track_list = []
    for track in library:
        track_info = {
            "id": track["id"],
            "title": track["title"],
            "album": track["album"] if "album" in track else "",
            "artist": track["artist"] if "artist" in track else "",
            "discNumber": track["discNumber"] if "discNumber" in track else 0,
            "trackNumber": track["trackNumber"] if "trackNumber" in track else 0
        }

        if track["deleted"]:
            deleted_track_list.append(track_info)
        else:
            track_key = (
                track["title"],
                track["album"] if "album" in track else "",
                track["artist"] if "artist" in track else "",
                track["discNumber"] if "discNumber" in track else 0,
                track["trackNumber"] if "trackNumber" in track else 0
            )

            if track_key in stored_tracks:
                duplicate_track_list.append(track_info)
            else:
                stored_tracks[track_key] = track_info

    info("Songs on Play Music: %d, Deleted: %d, Duplicate: %d" % (
        len(stored_tracks), len(deleted_track_list), len(duplicate_track_list)))

    message("Searching Local Songs...")
    local_tracks = {}
    incompatible_track_list = []
    local_duplicate_track_list = []
    directories = get_config(config, "Upload.Directories")
    for d in directories:
        if not path.isdir(d):
            exit_with_error("Directory does not exist: %s" % d)

        for root, _, files in os.walk(d):
            for filename in files:
                filepath = path.join(root, filename)
                _, ext = path.splitext(filepath)

                if ext not in [".mp3", ".m4a", ".flac"]:
                    continue

                media = mutagen.File(filepath)
                if media is None:
                    continue

                incompatible = False

                if isinstance(media, MP3):
                    track_info = {
                        "title": media["TIT2"].text[0],
                        "album": media["TALB"].text[0] if "TALB" in media else "",
                        "artist": media["TPE1"].text[0] if "TPE1" in media else "",
                        "discNumber": int(media["TPOS"].text[0].split("/")[0]) if "TPOS" in media else 0,
                        "trackNumber": int(media["TRCK"].text[0].split("/")[0]) if "TRCK" in media else 0,
                        "filepath": filepath
                    }
                elif isinstance(media, FLAC):
                    track_info = {
                        "title": media["title"][0],
                        "album": media["album"][0] if "album" in media else "",
                        "artist": media["artist"][0] if "artist" in media else "",
                        "discNumber": int(media["discnumber"][0].split("/")[0]) if "discnumber" in media else 0,
                        "trackNumber": int(media["tracknumber"][0].split("/")[0]) if "tracknumber" in media else 0,
                        "filepath": filepath
                    }
                elif isinstance(media, MP4):
                    track_info = {
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
                        pass
                    else:
                        continue
                else:
                    continue

                if incompatible:
                    incompatible_track_list.append(track_info)
                else:
                    track_key = (
                        track_info["title"],
                        track_info["album"],
                        track_info["artist"],
                        track_info["discNumber"],
                        track_info["trackNumber"]
                    )

                    if track_key in local_tracks:
                        local_duplicate_track_list.append(track_info)
                    else:
                        local_tracks[track_key] = track_info

    info("Songs on Local: %d, Incompatible: %d, Duplicate: %d" % (
        len(local_tracks), len(incompatible_track_list), len(local_duplicate_track_list)))

    message("Deleting...")
    delete_songs = []
    delete_tracks = []
    for track in duplicate_track_list:
        delete_songs.append(track["id"])
        delete_tracks.append(track)

    for track_key, track in stored_tracks.items():
        if track_key not in local_tracks:
            delete_songs.append(track["id"])
            delete_tracks.append(track)

    if 0 < len(delete_songs):
        client.delete_songs(delete_songs)
        for track in delete_tracks:
            message("Deleted: %s from %s <%s>" % (track["title"], track["album"], track["artist"]))

    info("Delete on Play Music has been completed: %s song(s)" % len(delete_songs))

    message("Uploading...")
    upload_songs = []
    for track_key, track in local_tracks.items():
        if track_key not in stored_tracks:
            upload_songs.append(track["filepath"])

    if 0 < len(upload_songs):
        result = manager.upload(upload_songs)
        info("  Uploaded: %d, Not Uploaded: %d" % (len(result[0]), len(result[2])))

        uploaded = result[0]
        for f in uploaded.keys():
            message("    Uploaded: %s" % f)

        not_uploaded = result[2]
        for f, r in not_uploaded.items():
            message("    Not Uploaded: [%s] %s" % (f, r))

    info("Upload to Play Music has been completed: %s song(s)" % len(upload_songs))

    log("######## TERMINATED at %s ########" % datetime.now().isoformat())
    sys.exit(0)


if __name__ == "__main__":
    main()
