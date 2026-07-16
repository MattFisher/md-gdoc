"""Extract data-URI images from exported markdown into linked files.

Google's markdown export embeds every image as a base64 data URI (usually a
reference-style definition like ``[image1]: <data:image/png;base64,…>``),
which makes pulled files enormous. Each URI is decoded into a file next to
the markdown — named by content hash, so repeated pulls of the same image
are stable and duplicates are stored once — and replaced with a relative
link.
"""

import base64
import hashlib
import re

_DATA_URI = re.compile(r"data:image/([A-Za-z0-9.+-]+);base64,([A-Za-z0-9+/=]+)")

_EXT = {"jpeg": "jpg", "svg+xml": "svg"}


def extract_images(md, md_path):
    """Rewrite data-URI images in md to files under <stem>.assets/ beside md_path."""
    assets = md_path.parent / (md_path.stem + ".assets")

    def _replace(m):
        subtype, b64 = m.groups()
        try:
            data = base64.b64decode(b64, validate=True)
        except ValueError:
            return m.group(0)
        name = hashlib.sha256(data).hexdigest()[:12] + "." + _EXT.get(subtype, subtype)
        assets.mkdir(parents=True, exist_ok=True)
        path = assets / name
        if not path.exists():
            path.write_bytes(data)
        return f"{assets.name}/{name}"

    return _DATA_URI.sub(_replace, md)
