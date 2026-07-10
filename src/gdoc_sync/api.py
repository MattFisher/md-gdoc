"""Thin wrapper over the Drive and Docs services."""

import re
import time

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

_FOLDER_MIME = "application/vnd.google-apps.folder"


def _unescape_md(text):
    """Remove backslash escapes that Drive adds to markdown special chars."""
    return re.sub(r"\\(.)", r"\1", text)


def _split_by_tabs(full_md, tabs):
    """Split Drive's concatenated export (tabs become H1s) into {tab_id: body}."""
    title_to_id = {t["title"]: t["id"] for t in tabs}
    lines = full_md.split("\n")
    markers = []
    for i, line in enumerate(lines):
        s = line.strip()
        if s.startswith("# "):
            candidate = _unescape_md(s[2:].strip())
            if candidate in title_to_id:
                markers.append((i, title_to_id[candidate]))
    if not markers:
        return {tabs[0]["id"]: full_md}
    result = {}
    # Content before the first marker → first tab (if that tab has no marker)
    first_tab_id = tabs[0]["id"]
    if markers[0][0] > 0 and first_tab_id not in {m[1] for m in markers}:
        pre = "\n".join(lines[:markers[0][0]]).strip()
        result[first_tab_id] = (pre + "\n") if pre else "\n"
    for n, (start, tab_id) in enumerate(markers):
        end = markers[n + 1][0] if n + 1 < len(markers) else len(lines)
        content = "\n".join(lines[start + 1:end]).strip()
        result[tab_id] = (content + "\n") if content else "\n"
    return result


class GDocsApi:
    def __init__(self, creds):
        self._drive = build("drive", "v3", credentials=creds)
        self._docs = build("docs", "v1", credentials=creds)

    @staticmethod
    def doc_url(doc_id):
        return f"https://docs.google.com/document/d/{doc_id}/edit"

    def create_doc(self, title, folder_id=None):
        """Create a blank Google Doc and return (doc_id, url)."""
        doc = self._docs.documents().create(body={"title": title}).execute()
        doc_id = doc["documentId"]
        if folder_id:
            self._drive.files().update(
                fileId=doc_id, addParents=folder_id, fields="id,parents"
            ).execute()
        return doc_id, self.doc_url(doc_id)

    def export_markdown(self, doc_id):
        data = self._drive.files().export(fileId=doc_id, mimeType="text/markdown").execute()
        return data.decode("utf-8") if isinstance(data, bytes) else data

    def get_document(self, doc_id):
        return self._docs.documents().get(documentId=doc_id).execute()

    def list_tabs(self, doc_id):
        """Return [{id, title, index}] for each user-created tab, or [] for untabbed docs.

        Docs without user-created tabs have one implicit tab; we treat those as untabbed
        and return [].
        """
        doc = self._docs.documents().get(documentId=doc_id, includeTabsContent=True).execute()
        raw = doc.get("tabs", [])
        if len(raw) <= 1:
            return []
        return [
            {"id": t["tabProperties"]["tabId"],
             "title": t["tabProperties"]["title"],
             "index": t["tabProperties"]["index"]}
            for t in raw
        ]

    def get_body_content(self, doc_id, tab_id=None):
        """Return body content list for the doc (or a specific tab)."""
        if tab_id:
            doc = self._docs.documents().get(documentId=doc_id, includeTabsContent=True).execute()
            for t in doc.get("tabs", []):
                if t["tabProperties"]["tabId"] == tab_id:
                    return t["documentTab"]["body"]["content"]
            raise SystemExit(f"Tab {tab_id!r} not found in {doc_id!r}")
        return self._docs.documents().get(documentId=doc_id).execute()["body"]["content"]

    def export_tab_markdown(self, doc_id, tab_id):
        """Export markdown for one tab by splitting the full Drive export."""
        tabs = self.list_tabs(doc_id)
        full_md = self.export_markdown(doc_id)
        if not tabs:
            return full_md
        split = _split_by_tabs(full_md, tabs)
        return split.get(tab_id, full_md)

    def batch_update(self, doc_id, requests):
        for attempt in range(5):
            try:
                self._docs.documents().batchUpdate(
                    documentId=doc_id, body={"requests": requests}
                ).execute()
                return
            except HttpError as e:
                if e.resp.status == 429 and attempt < 4:
                    time.sleep(2 ** attempt * 15)
                else:
                    raise

    def list_comments(self, doc_id):
        items, token = [], None
        while True:
            resp = self._drive.comments().list(
                fileId=doc_id, fields="*", includeDeleted=False,
                pageSize=100, pageToken=token,
            ).execute()
            items += resp.get("comments", [])
            token = resp.get("nextPageToken")
            if not token:
                return items

    # --- e2e helpers ---

    def create_comment(self, doc_id, content, quoted=None):
        body = {"content": content}
        if quoted:
            body["quotedFileContent"] = {"value": quoted}
        return self._drive.comments().create(
            fileId=doc_id, body=body, fields="*"
        ).execute()

    def delete_file(self, doc_id):
        self._drive.files().delete(fileId=doc_id).execute()

    def find_or_create_folder(self, name):
        escaped = name.replace("'", "\\'")
        q = f"name = '{escaped}' and mimeType = '{_FOLDER_MIME}' and trashed = false"
        found = self._drive.files().list(q=q, fields="files(id)").execute()["files"]
        if found:
            return found[0]["id"]
        f = self._drive.files().create(
            body={"name": name, "mimeType": _FOLDER_MIME}, fields="id"
        ).execute()
        return f["id"]
