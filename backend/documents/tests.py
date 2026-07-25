from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from rest_framework.test import APITestCase

from reviews.models import ReviewAssignment

from .models import Document, DocumentPermission, DocumentVersion, Folder
from .permissions import has_permission

User = get_user_model()


def make_file(name="test.txt", content=b"hello world"):
    return SimpleUploadedFile(name, content, content_type="text/plain")


class DuplicateTitleTests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user("owner", password="pass12345")

    def test_find_duplicate_titles(self):
        Document.objects.create(title="Policy.pdf", owner=self.owner)
        second = Document.objects.create(title="Policy.pdf", owner=self.owner)
        dupes = Document.find_duplicate_titles("policy.pdf", exclude_pk=second.pk)
        self.assertEqual(len(dupes), 1)

    def test_no_duplicates_for_unique_title(self):
        Document.objects.create(title="Unique.pdf", owner=self.owner)
        self.assertEqual(Document.find_duplicate_titles("Something else"), [])

    def test_document_code_assigned_and_unique(self):
        d1 = Document.objects.create(title="A", owner=self.owner)
        d2 = Document.objects.create(title="B", owner=self.owner)
        self.assertTrue(d1.code)
        self.assertNotEqual(d1.code, d2.code)


class PermissionResolutionTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user("admin", password="pass12345", role=User.ROLE_ADMIN)
        self.owner = User.objects.create_user("owner", password="pass12345")
        self.grantee = User.objects.create_user("grantee", password="pass12345")
        self.stranger = User.objects.create_user("stranger", password="pass12345")
        self.document = Document.objects.create(title="Doc", owner=self.owner)

    def test_admin_always_allowed(self):
        self.assertTrue(has_permission(self.admin, self.document, "approve"))
        self.assertTrue(has_permission(self.admin, self.document, "edit"))

    def test_owner_can_view_edit_download_not_approve(self):
        self.assertTrue(has_permission(self.owner, self.document, "view"))
        self.assertTrue(has_permission(self.owner, self.document, "edit"))
        self.assertTrue(has_permission(self.owner, self.document, "download"))
        self.assertFalse(has_permission(self.owner, self.document, "approve"))

    def test_stranger_has_no_access(self):
        self.assertFalse(has_permission(self.stranger, self.document, "view"))

    def test_active_grant_allows_action(self):
        DocumentPermission.objects.create(
            document=self.document, user=self.grantee, granted_by=self.owner,
            can_view=True, can_edit=False, can_approve=True, can_download=True,
        )
        self.assertTrue(has_permission(self.grantee, self.document, "view"))
        self.assertTrue(has_permission(self.grantee, self.document, "approve"))
        self.assertFalse(has_permission(self.grantee, self.document, "edit"))

    def test_expired_grant_denies_action(self):
        DocumentPermission.objects.create(
            document=self.document, user=self.grantee, granted_by=self.owner,
            can_view=True, can_download=True,
            expires_at=timezone.now() - timedelta(days=1),
        )
        self.assertFalse(has_permission(self.grantee, self.document, "view"))

    def test_future_expiry_still_allows_action(self):
        DocumentPermission.objects.create(
            document=self.document, user=self.grantee, granted_by=self.owner,
            can_view=True, expires_at=timezone.now() + timedelta(days=1),
        )
        self.assertTrue(has_permission(self.grantee, self.document, "view"))


class ReviewWorkflowTests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user("owner2", password="pass12345")
        self.reviewer1 = User.objects.create_user("rev1", password="pass12345")
        self.reviewer2 = User.objects.create_user("rev2", password="pass12345")
        self.document = Document.objects.create(title="ReviewDoc", owner=self.owner)
        self.version = DocumentVersion.objects.create(
            document=self.document, version_number=1, file=make_file(),
            uploaded_by=self.owner, size=11, checksum="abc",
        )

    def test_document_approved_once_all_reviewers_approve(self):
        self.client.force_authenticate(self.owner)
        resp = self.client.post(
            f"/api/documents/{self.document.pk}/submit-for-review/",
            {"reviewer_ids": [self.reviewer1.pk, self.reviewer2.pk]},
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        self.document.refresh_from_db()
        self.assertEqual(self.document.status, Document.STATUS_IN_REVIEW)

        self.client.force_authenticate(self.reviewer1)
        resp = self.client.post(
            f"/api/documents/{self.document.pk}/review-decision/",
            {"decision": "approve"}, format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.document.refresh_from_db()
        self.assertEqual(self.document.status, Document.STATUS_IN_REVIEW)

        self.client.force_authenticate(self.reviewer2)
        resp = self.client.post(
            f"/api/documents/{self.document.pk}/review-decision/",
            {"decision": "approve"}, format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.document.refresh_from_db()
        self.assertEqual(self.document.status, Document.STATUS_APPROVED)

    def test_document_rejected_if_any_reviewer_rejects(self):
        ReviewAssignment.objects.create(
            document=self.document, version=self.version, reviewer=self.reviewer1,
            assigned_by=self.owner,
        )
        self.document.status = Document.STATUS_IN_REVIEW
        self.document.save(update_fields=["status"])

        self.client.force_authenticate(self.reviewer1)
        resp = self.client.post(
            f"/api/documents/{self.document.pk}/review-decision/",
            {"decision": "reject", "comment": "needs work"}, format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.document.refresh_from_db()
        self.assertEqual(self.document.status, Document.STATUS_REJECTED)


class DocumentApiTests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user("owner3", password="pass12345")
        self.stranger = User.objects.create_user("stranger3", password="pass12345")
        self.admin = User.objects.create_user("admin3", password="pass12345", role=User.ROLE_ADMIN)

    def test_upload_creates_document_with_v1_and_code(self):
        self.client.force_authenticate(self.owner)
        resp = self.client.post(
            "/api/documents/",
            {"title": "Contract.pdf", "description": "desc", "file": make_file()},
            format="multipart",
        )
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertTrue(resp.data["code"].startswith("DOC-"))
        self.assertEqual(resp.data["latest_version_number"], 1)

    def test_upload_accepts_pdf_and_excel(self):
        self.client.force_authenticate(self.owner)
        for filename in ("Report.pdf", "Data.xlsx", "Legacy.xls"):
            resp = self.client.post(
                "/api/documents/",
                {"title": filename, "file": make_file(name=filename)},
                format="multipart",
            )
            self.assertEqual(resp.status_code, 201, resp.data)

    def test_upload_rejects_disallowed_file_type(self):
        self.client.force_authenticate(self.owner)
        resp = self.client.post(
            "/api/documents/",
            {"title": "Presentation.pptx", "file": make_file(name="Presentation.pptx")},
            format="multipart",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("file", resp.data)
        # regression guard: the error must be a flat string/list, not a
        # dict-inside-dict, or the frontend's error formatter breaks
        self.assertNotIsInstance(resp.data["file"][0] if isinstance(resp.data["file"], list) else resp.data["file"], dict)
        self.assertIn("Unsupported file type", str(resp.data["file"]))

    def test_new_version_rejects_disallowed_file_type(self):
        self.client.force_authenticate(self.owner)
        create_resp = self.client.post(
            "/api/documents/", {"title": "Versioned.pdf", "file": make_file()}, format="multipart"
        )
        doc_id = create_resp.data["id"]
        resp = self.client.post(
            f"/api/documents/{doc_id}/versions/",
            {"file": make_file(name="notes.docx")},
            format="multipart",
        )
        self.assertEqual(resp.status_code, 400)

    def test_duplicate_title_warning_returned(self):
        self.client.force_authenticate(self.owner)
        self.client.post(
            "/api/documents/", {"title": "Dup.pdf", "file": make_file()}, format="multipart"
        )
        resp = self.client.post(
            "/api/documents/", {"title": "Dup.pdf", "file": make_file()}, format="multipart"
        )
        self.assertEqual(len(resp.data["duplicate_warning"]), 1)

    def test_stranger_cannot_view_document(self):
        self.client.force_authenticate(self.owner)
        create_resp = self.client.post(
            "/api/documents/", {"title": "Secret.pdf", "file": make_file()}, format="multipart"
        )
        doc_id = create_resp.data["id"]

        self.client.force_authenticate(self.stranger)
        resp = self.client.get(f"/api/documents/{doc_id}/")
        self.assertEqual(resp.status_code, 403)

    def test_stranger_document_list_excludes_others_documents(self):
        self.client.force_authenticate(self.owner)
        self.client.post(
            "/api/documents/", {"title": "OwnerOnly.pdf", "file": make_file()}, format="multipart"
        )
        self.client.force_authenticate(self.stranger)
        resp = self.client.get("/api/documents/")
        titles = [d["title"] for d in resp.data["results"]]
        self.assertNotIn("OwnerOnly.pdf", titles)

    def test_grant_then_revoke_permission(self):
        self.client.force_authenticate(self.owner)
        create_resp = self.client.post(
            "/api/documents/", {"title": "Shared.pdf", "file": make_file()}, format="multipart"
        )
        doc_id = create_resp.data["id"]

        grant_resp = self.client.post(
            f"/api/documents/{doc_id}/permissions/",
            {"user": self.stranger.pk, "can_view": True, "can_download": True},
            format="json",
        )
        self.assertEqual(grant_resp.status_code, 201, grant_resp.data)

        self.client.force_authenticate(self.stranger)
        resp = self.client.get(f"/api/documents/{doc_id}/")
        self.assertEqual(resp.status_code, 200)

        # Owners can grant, but per policy only admins can revoke.
        self.client.force_authenticate(self.owner)
        perm_id = grant_resp.data["id"]
        owner_del_resp = self.client.delete(f"/api/documents/{doc_id}/permissions/{perm_id}/")
        self.assertEqual(owner_del_resp.status_code, 403)

        self.client.force_authenticate(self.admin)
        admin_del_resp = self.client.delete(f"/api/documents/{doc_id}/permissions/{perm_id}/")
        self.assertEqual(admin_del_resp.status_code, 204)

        self.client.force_authenticate(self.stranger)
        resp = self.client.get(f"/api/documents/{doc_id}/")
        self.assertEqual(resp.status_code, 403)

    def test_can_approve_grant_creates_pending_review(self):
        self.client.force_authenticate(self.owner)
        create_resp = self.client.post(
            "/api/documents/", {"title": "NeedsApproval.pdf", "file": make_file()}, format="multipart"
        )
        doc_id = create_resp.data["id"]
        self.assertEqual(create_resp.data["status"], Document.STATUS_DRAFT)

        grant_resp = self.client.post(
            f"/api/documents/{doc_id}/permissions/",
            {"user": self.stranger.pk, "can_view": True, "can_approve": True},
            format="json",
        )
        self.assertEqual(grant_resp.status_code, 201, grant_resp.data)

        document = Document.objects.get(pk=doc_id)
        self.assertEqual(document.status, Document.STATUS_IN_REVIEW)
        assignment = ReviewAssignment.objects.get(document=document, reviewer=self.stranger)
        self.assertEqual(assignment.status, ReviewAssignment.STATUS_PENDING)

    def test_view_only_grant_does_not_create_review(self):
        self.client.force_authenticate(self.owner)
        create_resp = self.client.post(
            "/api/documents/", {"title": "ViewOnly.pdf", "file": make_file()}, format="multipart"
        )
        doc_id = create_resp.data["id"]

        self.client.post(
            f"/api/documents/{doc_id}/permissions/",
            {"user": self.stranger.pk, "can_view": True, "can_download": True},
            format="json",
        )

        document = Document.objects.get(pk=doc_id)
        self.assertEqual(document.status, Document.STATUS_DRAFT)
        self.assertFalse(ReviewAssignment.objects.filter(document=document, reviewer=self.stranger).exists())
