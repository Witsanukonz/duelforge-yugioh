import mimetypes
import re
from pathlib import Path

from django.conf import settings
from django.http import FileResponse, Http404, HttpResponse, StreamingHttpResponse


ALLOWED_TRACKS = {
    "gods-anger.mp3",
    "track-02.mp3",
    "track-03.mp3",
    "track-04.mp3",
    "track-05.mp3",
}
RANGE_PATTERN = re.compile(r"bytes=(\d*)-(\d*)$")


def _stream_range(file_handle, remaining, chunk_size=64 * 1024):
    try:
        while remaining > 0:
            chunk = file_handle.read(min(chunk_size, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk
    finally:
        file_handle.close()


def audio_track(request, filename):
    if filename not in ALLOWED_TRACKS:
        raise Http404("Unknown audio track")

    audio_root = Path(settings.SITE_AUDIO_ROOT).resolve()
    track_path = (audio_root / filename).resolve()
    if track_path.parent != audio_root or not track_path.is_file():
        raise Http404("Audio track not found")

    file_size = track_path.stat().st_size
    content_type = mimetypes.guess_type(track_path.name)[0] or "audio/mpeg"
    range_header = request.headers.get("Range", "").strip()

    if not range_header:
        response = FileResponse(track_path.open("rb"), content_type=content_type)
        response["Content-Length"] = file_size
    else:
        match = RANGE_PATTERN.fullmatch(range_header)
        if not match or file_size == 0:
            response = HttpResponse(status=416)
            response["Content-Range"] = f"bytes */{file_size}"
            return response

        start_text, end_text = match.groups()
        if not start_text:
            suffix_length = int(end_text or 0)
            if suffix_length <= 0:
                response = HttpResponse(status=416)
                response["Content-Range"] = f"bytes */{file_size}"
                return response
            start = max(0, file_size - suffix_length)
            end = file_size - 1
        else:
            start = int(start_text)
            end = min(int(end_text), file_size - 1) if end_text else file_size - 1

        if start >= file_size or end < start:
            response = HttpResponse(status=416)
            response["Content-Range"] = f"bytes */{file_size}"
            return response

        length = end - start + 1
        file_handle = track_path.open("rb")
        file_handle.seek(start)
        response = StreamingHttpResponse(
            _stream_range(file_handle, length),
            status=206,
            content_type=content_type,
        )
        response["Content-Length"] = length
        response["Content-Range"] = f"bytes {start}-{end}/{file_size}"

    response["Accept-Ranges"] = "bytes"
    response["Content-Disposition"] = f'inline; filename="{track_path.name}"'
    response["Cache-Control"] = "public, max-age=3600"
    return response
