# -*- coding: utf-8 -*-
import glob
import logging
import time
from shutil import copyfile

import constants
import moviepy.config as cf
import moviepy.video.fx.all as vfx
import os
import requests
from moviepy import Clip
from moviepy.video.io.VideoFileClip import VideoFileClip

logger = logging.getLogger(__name__)
try:
    cf.change_settings("FFMPEG_BINARY", "auto-detect")
except Exception as e:
    logger.exception(e)


def get_ffmpeg_info():
    return "ffmpeg binary path: " + cf.get_setting("FFMPEG_BINARY")


def resize(infile):
    logger.debug("resizing file " + infile)
    orig_file = VideoFileClip(infile)
    # scale the image so that it does not exceed maximum dimensions of 360x360
    # although the max dimensions are somewhat arbitrary, we have seen how just scaling the original image with
    # absolute disregard for min width x height produces not playable videos on the phone (only)
    # adjusted dimensions so that the files data/test_input/[iran_denis.mov, iran_pablo.mov] get converted properly
    # on MOBILE client (desktop was ok).
    # todo: 360 seems to be a magic number, find out why
    # todo: convert every file type to .mpg4 so that the screenshot is visible in telegram clients?

    # this is the max new size of either 'width' or 'height',
    # moviePy will scale the corresponding dimension automatically
    new_size = get_newsize(orig_file)

    #this will attempt to resize, if fails for some reason, carries on compressing. Resizing the video is not contributing much to the reduction of the video size by the way.
    try:
        clip_resized = orig_file.fx(vfx.resize, **new_size) if new_size < 1 else orig_file
    except:
        clip_resized = orig_file

    return clip_resized


def get_newsize(f):
    # 320p is the mobile format according to https://www.virag.si/2012/01/web-video-encoding-tutorial-with-ffmpeg-0-9/
    # it approximates image around 320p, but does not shrink the image more than 50%.
    if f.w > f.h:
        return max(0.5, min(round(320.0 / f.w, 1), 1))
    else:
        return max(0.5, min(round(320.0 / f.h, 1), 1))


def compress(infile, outfile, clip_resized, with_sound):
    logger.debug("compressing file: " + infile)
    orig_file = VideoFileClip(infile)
    orig_bitrate = os.stat(infile).st_size * 8 / orig_file.duration / 1000
    speed = 1.5
    kwargs = {}
    if not with_sound:
        clip_resized = clip_resized.without_audio()
        speed = 2
        fps = 10  # is just good enough
        # filesize calculation, source: https://trac.ffmpeg.org/wiki/Encode/H.264
        # bitrate [kilobit/s]= file_size [kilobits=>kbyte*8] / duration [secs]
        max_bitrate = max(60, 0.3 * orig_bitrate)  # int(250 * 8 / clip_accelerated.duration)
        # bitrate of the compressed image should not exceed the bitrate of original image
        bitrate_limit = min(max_bitrate, orig_bitrate)
        kwargs = {'fps': fps, 'bitrate': str(bitrate_limit) + "k"}

    clip_accelerated = clip_resized.fx(vfx.speedx, speed)
    try:
        # 'libx264' (also default) seems to have smaller pic size than mpeg4
        clip_accelerated.write_videofile(outfile, codec='libx264', **kwargs)
    except IOError as e:
        # there is a bug in VideoClip: if an error happens during the conversion, the temp audio clip is not cleaned up
        # see sourcecode of VideoClip.write_videofile()
        name, _ = os.path.splitext(os.path.basename(outfile))
        for filename in glob.glob(name + "TEMP_MPY_wvf_snd*"):
            os.remove(filename)

        # The video export failed, possibly because the codec specified for the video (libx264) is not compatible
        # with the given extension (3gp). Please specify a valid 'codec' argument in write_videofile.
        # This would be 'libx264' or 'mpeg4' for mp4, 'libtheora' for ogv, 'libvpx for webm.
        # Another possible reason is that the audio codec was not compatible with the video codec.
        # For instance the video extensions 'ogv' and 'webm' only allow 'libvorbis' (default) as avideo codec."
        logger.exception(e)
        raise e


def resize_and_compress(infile, outfile, with_sound):
    clip_resized = resize(infile)
    compress(infile, outfile, clip_resized, with_sound)


def process_file(fname, with_sound):
    outfile = os.path.basename(fname)
    resize_and_compress(fname, constants.output_dir + outfile, with_sound)
    # otherwise it's unicode
    return outfile


def get_timestamp():
    # http://stackoverflow.com/questions/18169099/python-get-milliseconds-since-epoch-millisecond-accuracy-not-seconds1000
    return str(int(time.time() * 1000))


def download_and_save(furl, file_name, real_user):
    dst_file_path = constants.downloads_dir + '%s_%s' % (get_timestamp(), file_name)
    if real_user:
        f = requests.get(furl)
        with open(dst_file_path, 'wb') as fd:
            for chunk in f.iter_content(1024):
                fd.write(chunk)
    else:
        copyfile(os.path.join(constants.test_input_dir, file_name), dst_file_path)
    logger.debug("saved file to %s" % dst_file_path)
    return dst_file_path
