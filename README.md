# Sync Play Music

A Utility for syncronizing music files between Google Play Music and your computer.

## Supported file types

- MP3
- AAC
- ALAC(16 bits per sample rate)
- FLAC

## Requirements

- Python 2.7

### Optional

- [Virtualenv](https://virtualenv.pypa.io/en/stable/)
- [avconv](https://libav.org/avconv.html) or [ffmpeg](http://ffmpeg.org/ffmpeg.html) (If you want to upload non-MP3 files.)

## Configuration

### Virtualenv

```x-sh
$ cd REPOSITORY_ROOT
$ virtualenv syncgmenv
$ source syncgmenv/bin/activate
$ pip install -r syncgmenv/requirements.txt
```

### Configuration file

Copy config.yml.sample to config.yml and edit in it.

## Run

Run sync.py!!!

