def create_mix_from_youtube_ids(youtube_ids, mix_filename):
    import os
    import shutil
    from yt_dlp import YoutubeDL
    from pydub import AudioSegment

    rip_directory = './youtube_rips/' + mix_filename + '/'

    if os.path.isdir(rip_directory):
        shutil.rmtree(rip_directory)

    ydl_opts = {
        'paths': {
            'home': rip_directory,
            'temp': './temp',
        },
        'format': 'm4a/bestaudio/best',
        # ℹ️ See help(yt_dlp.postprocessor) for a list of available Postprocessors and their arguments
        'postprocessors': [{  # Extract audio using ffmpeg
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'wav',
        }],
        'outtmpl': {'default': '%(autonumber)s %(title)s.%(ext)s',}
    }

    with YoutubeDL(ydl_opts) as ydl:
        ydl.download(youtube_ids)

    all_tracks = []
    for filename in sorted(os.listdir(rip_directory)):
        if filename.endswith('.wav'):
            track = AudioSegment.from_file(rip_directory + filename)
            all_tracks.append(track)

    default_crossfade_time = 10 * 1000

    mixed_tracks = None
    for i, track in enumerate(all_tracks):
        if mixed_tracks == None:
            mixed_tracks = track
        else:
            last_track_length = len(all_tracks[i - 1])
            next_track_length = len(all_tracks[i])
            if min(last_track_length, next_track_length) < 30000:
                # Don't crossfade in or out of tracks shorter than 30 seconds
                crossfade_time = min(100, last_track_length, next_track_length)
            else:
                crossfade_time = min(
                    default_crossfade_time,
                    last_track_length / 3,
                    next_track_length / 3,
                )
            mixed_tracks = mixed_tracks.append(track, crossfade=crossfade_time)

    mixed_tracks.export('mixes/' + mix_filename + ".mp3", format="mp3", bitrate="320k")

    if os.path.isdir(rip_directory):
        shutil.rmtree(rip_directory)

# download()
# breakpoint()
