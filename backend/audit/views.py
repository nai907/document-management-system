from datetime import timedelta

from django.utils import timezone
from rest_framework import generics
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsAdminRole
from documents.models import Document, DocumentPermission
from reviews.models import ReviewAssignment

from .models import AuditLog
from .serializers import AuditLogSerializer

OVERDUE_REVIEW_DAYS = 5


class AuditLogListView(generics.ListAPIView):
    serializer_class = AuditLogSerializer
    permission_classes = [IsAdminRole]

    def get_queryset(self):
        qs = AuditLog.objects.select_related("actor", "document").all()
        params = self.request.query_params
        if user_id := params.get("user"):
            qs = qs.filter(actor_id=user_id)
        if action := params.get("action"):
            qs = qs.filter(action=action)
        if document_id := params.get("document"):
            qs = qs.filter(document_id=document_id)
        if date_from := params.get("date_from"):
            qs = qs.filter(timestamp__gte=date_from)
        if date_to := params.get("date_to"):
            qs = qs.filter(timestamp__lte=date_to)
        return qs


class DashboardSummaryView(APIView):
    permission_classes = [IsAdminRole]

    def get(self, request):
        now = timezone.now()
        overdue_cutoff = now - timedelta(days=OVERDUE_REVIEW_DAYS)
        soon = now + timedelta(days=7)

        counts_by_status = {
            choice: Document.objects.filter(status=choice).count()
            for choice, _ in Document.STATUS_CHOICES
        }

        overdue_reviews = ReviewAssignment.objects.select_related(
            "document", "reviewer"
        ).filter(status=ReviewAssignment.STATUS_PENDING, assigned_at__lte=overdue_cutoff)

        # Every document currently in review, with who's still holding it up -
        # the dashboard-wide version of the "still waiting on" view shown on
        # each document's own Review tab.
        pending_reviews = []
        for doc in Document.objects.filter(status=Document.STATUS_IN_REVIEW).select_related("owner"):
            latest = doc.latest_version
            if not latest:
                continue
            pending_reviewers = list(
                ReviewAssignment.objects.filter(
                    document=doc, version=latest, status=ReviewAssignment.STATUS_PENDING
                ).select_related("reviewer").values_list("reviewer__username", flat=True)
            )
            if pending_reviewers:
                pending_reviews.append({
                    "id": doc.id,
                    "code": doc.code,
                    "title": doc.title,
                    "owner": doc.owner.username,
                    "pending_reviewers": pending_reviewers,
                })

        expiring_permissions = DocumentPermission.objects.select_related(
            "document", "user", "group"
        ).filter(expires_at__isnull=False, expires_at__gte=now, expires_at__lte=soon)

        recent_activity = AuditLog.objects.select_related("actor", "document")[:25]

        return Response({
            "counts_by_status": counts_by_status,
            "total_documents": Document.objects.count(),
            "pending_reviews": pending_reviews,
            "overdue_reviews": [
                {
                    "id": r.id,
                    "document_id": r.document_id,
                    "document_code": r.document.code,
                    "document_title": r.document.title,
                    "reviewer": r.reviewer.username,
                    "assigned_at": r.assigned_at,
                }
                for r in overdue_reviews
            ],
            "expiring_permissions": [
                {
                    "id": p.id,
                    "document_id": p.document_id,
                    "document_code": p.document.code,
                    "grantee": p.user.username if p.user else f"group:{p.group.name}",
                    "expires_at": p.expires_at,
                }
                for p in expiring_permissions
            ],
            "recent_activity": AuditLogSerializer(recent_activity, many=True).data,
        })
