import subprocess
import tempfile
import os
import json
from django.core.files import File
from .models import PostBlock



def get_duration(path):
    result = subprocess.run(
        ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', path],
        capture_output=True, text=True
    )
    data = json.loads(result.stdout)
    return float(data['format']['duration'])

def process_short_video(block_id):
    block = PostBlock.objects.get(pk=block_id)
    block.video_status = 'processing'
    block.save(update_fields=['video_status'])

    input_path = block.video_original.path

    with tempfile.TemporaryDirectory() as tmp:
        poster_path = os.path.join(tmp, f'poster_{block.pk}.jpg')
        processed_path = os.path.join(tmp, f'processed_{block.pk}.mp4')

        try:
            block.video_duration = get_duration(input_path)

            # кадр для постера
            subprocess.run([
                'ffmpeg', '-y', '-i', input_path, '-ss', '00:00:00.5',
                '-vframes', '1', poster_path
            ], check=True, capture_output=True)

            # компрессия/приведение к web-формату
            subprocess.run([
                'ffmpeg', '-y', '-i', input_path,
                '-vf', "scale='min(1080,iw)':-2",
                '-c:v', 'libx264', '-preset', 'medium', '-crf', '26',
                '-c:a', 'aac', '-b:a', '128k',
                '-movflags', '+faststart',
                processed_path
            ], check=True, capture_output=True)

            with open(processed_path, 'rb') as f:
                block.video_processed.save(f'processed_{block.pk}.mp4', File(f), save=False)
            with open(poster_path, 'rb') as f:
                block.video_poster.save(f'poster_{block.pk}.jpg', File(f), save=False)

            block.video_status = 'ready'
            block.save()

        except subprocess.CalledProcessError:
            block.video_status = 'failed'
            block.save(update_fields=['video_status'])