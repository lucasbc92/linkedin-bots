"""IDs read out of LinkedIn URLs: a photo's asset ID, a conversation's thread ID."""
import re


def photo_id_from_src(src):
    """The asset ID in a LinkedIn profile-photo URL, or None for a placeholder.

    ``…/dms/image/v2/D4D03AQFeIgpwF-N4zg/profile-displayphoto-…?e=…&t=…`` —
    the path segment names the uploaded photo; the query is a signature that
    rotates, so it is left out.
    """
    m = re.search(r"/dms/image/v\d+/([^/?]+)/", src or "")
    return m.group(1) if m else None


def thread_id_from_url(url):
    """The conversation ID in a ``/messaging/thread/<id>/`` URL, or None."""
    m = re.search(r"/messaging/thread/([^/?#]+)", url or "")
    return m.group(1) if m else None
