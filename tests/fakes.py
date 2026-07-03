"""Shared fake of GDocsApi for orchestration tests."""


class FakeApi:
    def __init__(self, export_md="", comments=None, document=None, export_md_after_update=None):
        self.export_md = export_md
        self._export_md_after_update = export_md_after_update
        self.comments = comments or []
        self.document = document or {"body": {"content": []}}
        self.batch_updates = []

    def export_markdown(self, doc_id):
        return self.export_md

    def list_comments(self, doc_id):
        return self.comments

    def get_document(self, doc_id):
        return self.document

    def batch_update(self, doc_id, requests):
        self.batch_updates.append(requests)
        if self._export_md_after_update is not None:
            self.export_md = self._export_md_after_update

    def create_doc(self, title, folder_id=None):
        return "fake-id", "https://docs.google.com/document/d/fake-id/edit"
