from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.utils import timezone

from audit.models import log as audit_log
from documents.models import (
    Document,
    DocumentPermission,
    DocumentVersion,
    Folder,
    Tag,
)
from reviews.models import ReviewAssignment

User = get_user_model()


class Command(BaseCommand):
    help = "Creates a realistic set of demo users, folders, documents, reviews, and permissions."

    def handle(self, *args, **options):
        self.users = self._create_users()
        self.folders = self._create_folders(self.users["admin"])
        self._create_documents()
        self.stdout.write(self.style.SUCCESS("Seed data ready."))

    # -- users ---------------------------------------------------------

    def _create_users(self):
        specs = [
            ("admin", "admin12345", User.ROLE_ADMIN, "IT", True, True),
            ("employee", "employee12345", User.ROLE_EMPLOYEE, "Sales", False, False),
        ]
        users = {}
        for username, password, role, department, is_staff, is_superuser in specs:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    "role": role,
                    "department": department,
                    "is_staff": is_staff,
                    "is_superuser": is_superuser,
                },
            )
            if created:
                user.set_password(password)
                user.save()
                self.stdout.write(f"Created user: {username} / {password} ({role}, {department})")
            users[username] = user
        return users

    # -- folders ---------------------------------------------------------

    def _create_folders(self, admin):
        names = ["HR Policies", "Finance", "Legal", "Engineering", "Marketing"]
        folders = {name: Folder.objects.get_or_create(name=name, created_by=admin)[0] for name in names}
        folders["Finance Budgets"] = Folder.objects.get_or_create(
            name="Budgets", parent=folders["Finance"], created_by=admin
        )[0]
        return folders

    # -- documents ---------------------------------------------------------

    def _create_documents(self):
        u = self.users
        f = self.folders

        self._doc(
            title="Employee Handbook.pdf", folder=f["HR Policies"], owner=u["employee"],
            description="Company handbook.",
            tags=["policy", "hr"], status=Document.STATUS_DRAFT,
            versions=[("Initial version", u["employee"])],
        )

        self._doc(
            title="Code of Conduct.pdf", folder=f["HR Policies"], owner=u["employee"],
            description="Standards of conduct expected of every employee.",
            tags=["policy", "hr"], status=Document.STATUS_APPROVED,
            versions=[("Initial version", u["employee"]), ("Clarified conflict-of-interest section", u["employee"])],
            reviewers=[(u["admin"], "approved")],
        )

        self._doc(
            title="Remote Work Policy.pdf", folder=f["HR Policies"], owner=u["employee"],
            description="Guidelines for hybrid and remote work arrangements.",
            tags=["policy", "hr"], status=Document.STATUS_IN_REVIEW,
            versions=[("Draft for review", u["employee"])],
            reviewers=[(u["admin"], None)],
        )

        self._doc(
            title="2026 Budget Plan.xlsx", folder=f["Finance Budgets"], owner=u["employee"],
            description="Departmental budget allocations for fiscal year 2026.",
            tags=["finance", "budget"], status=Document.STATUS_DRAFT,
            versions=[("First draft", u["employee"])],
        )

        self._doc(
            title="Q1 Financial Report.pdf", folder=f["Finance"], owner=u["admin"],
            description="Consolidated Q1 results for the finance department.",
            tags=["finance", "report"], status=Document.STATUS_APPROVED,
            versions=[("Initial version", u["admin"])],
            reviewers=[(u["employee"], "approved")],
            permissions=[(u["employee"], dict(can_view=True, can_download=True), None)],
        )

        self._doc(
            title="Q1 Marketing Report.pdf", folder=f["Marketing"], owner=u["employee"],
            description="Marketing team's own Q1 numbers - unrelated to Finance's report.",
            tags=["marketing", "report"], status=Document.STATUS_DRAFT,
            versions=[("Draft", u["employee"])],
        )

        self._doc(
            title="Vendor Contract - Acme Corp.pdf", folder=f["Legal"], owner=u["employee"],
            description="Master services agreement with Acme Corp.",
            tags=["legal", "contract"], status=Document.STATUS_IN_REVIEW,
            versions=[("Signed draft awaiting legal sign-off", u["employee"])],
            reviewers=[(u["admin"], None)], review_overdue_days=8,
        )

        self._doc(
            title="NDA Template.docx", folder=f["Legal"], owner=u["admin"],
            description="Standard mutual non-disclosure agreement template.",
            tags=["legal", "template"], status=Document.STATUS_APPROVED,
            versions=[("Initial version", u["admin"])],
            reviewers=[(u["employee"], "approved")],
            permissions=[
                (u["employee"], dict(can_view=True, can_edit=True, can_download=True), timedelta(days=3)),
            ],
        )

        self._doc(
            title="Software License Agreement.pdf", folder=f["Legal"], owner=u["employee"],
            description="Proposed license terms rejected pending revisions.",
            tags=["legal", "contract"], status=Document.STATUS_REJECTED,
            versions=[("Initial version", u["employee"])],
            reviewers=[(u["admin"], "rejected", "Liability clause needs revision before this can be approved.")],
        )

        self._doc(
            title="API Design Guidelines.md", folder=f["Engineering"], owner=u["employee"],
            description="Conventions for designing internal and public APIs.",
            tags=["engineering", "guidelines"], status=Document.STATUS_DRAFT,
            versions=[("Initial draft", u["employee"]), ("Added pagination conventions", u["employee"])],
        )

        self._doc(
            title="Deployment Runbook.pdf", folder=f["Engineering"], owner=u["employee"],
            description="Step-by-step production deployment and rollback procedure.",
            tags=["engineering", "ops"], status=Document.STATUS_APPROVED,
            versions=[("Initial version", u["employee"])],
            reviewers=[(u["admin"], "approved")],
        )

        self._doc(
            title="Brand Guidelines.pdf", folder=f["Marketing"], owner=u["employee"],
            description="Logo usage, color palette, and tone of voice guidelines.",
            tags=["marketing", "brand"], status=Document.STATUS_APPROVED,
            versions=[("Initial version", u["employee"])],
            reviewers=[(u["admin"], "approved")],
        )

        self._doc(
            title="Q1 Campaign Plan.pptx", folder=f["Marketing"], owner=u["employee"],
            description="Marketing campaign plan for Q1 launches.",
            tags=["marketing", "campaign"], status=Document.STATUS_IN_REVIEW,
            versions=[("Draft for review", u["employee"])],
            reviewers=[(u["admin"], None)],
        )

    # -- helper ---------------------------------------------------------

    def _doc(
        self, title, folder, owner, description, tags=None,
        status=Document.STATUS_DRAFT, versions=(), reviewers=(), permissions=(),
        review_overdue_days=None,
    ):
        if Document.objects.filter(title=title, folder=folder, owner=owner).exists():
            return

        document = Document.objects.create(
            title=title, description=description, folder=folder, owner=owner, status=status,
        )
        if tags:
            document.tags.set([Tag.objects.get_or_create(name=t)[0] for t in tags])

        last_version = None
        for i, (note, uploaded_by) in enumerate(versions, start=1):
            content = f"Demo content for {title} - version {i}".encode()
            last_version = DocumentVersion.objects.create(
                document=document, version_number=i,
                file=ContentFile(content, name=f"v{i}_{title}"),
                uploaded_by=uploaded_by, change_note=note,
                size=len(content), checksum=f"demo-checksum-{document.id}-{i}",
            )
            audit_log(
                uploaded_by, "upload" if i == 1 else "new_version",
                document=document, version=i,
            )

        for entry in reviewers:
            reviewer, decision = entry[0], entry[1]
            comment = entry[2] if len(entry) > 2 else ""
            assignment = ReviewAssignment.objects.create(
                document=document, version=last_version, reviewer=reviewer,
                assigned_by=owner, status=decision or ReviewAssignment.STATUS_PENDING,
                comment=comment,
                decided_at=timezone.now() if decision else None,
            )
            if review_overdue_days:
                ReviewAssignment.objects.filter(pk=assignment.pk).update(
                    assigned_at=timezone.now() - timedelta(days=review_overdue_days)
                )
            audit_log(owner, "submit_for_review", document=document, version=last_version.version_number)
            if decision:
                audit_log(reviewer, decision, document=document, version=last_version.version_number, comment=comment)

        for grantee, flags, expires_delta in permissions:
            expires_at = timezone.now() + expires_delta if expires_delta else None
            DocumentPermission.objects.create(
                document=document, user=grantee, granted_by=owner, expires_at=expires_at, **flags
            )
            audit_log(owner, "permission_grant", document=document, grantee=grantee.username)

        self.stdout.write(f"Created document: {title} ({document.code}, {status})")
