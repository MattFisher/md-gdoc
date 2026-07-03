"""Thin wrapper over the Drive and Docs services."""

import time

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

_FOLDER_MIME = "application/vnd.google-apps.folder"


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
