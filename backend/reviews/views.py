from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from audit.models import log as audit_log
from documents.models import Document

from .models import ReviewAssignment
from .serializers import ReviewAssignmentSerializer

User = get_user_model()


def _can_manage_review(user, document):
    return user.is_superuser or user.role == user.ROLE_ADMIN or document.owner_id == user.id


class SubmitForReviewView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        document = get_object_or_404(Document, pk=pk)
        if not _can_manage_review(request.user, document):
            raise PermissionDenied("Only the owner or an admin can submit this document for review.")

        reviewer_ids = request.data.get("reviewer_ids") or []
        if not reviewer_ids:
            raise ValidationError({"reviewer_ids": "Provide at least one reviewer id."})
        version = document.latest_version
        if not version:
            raise ValidationError("Document has no uploaded version yet.")

        reviewers = User.objects.filter(id__in=reviewer_ids)
        if reviewers.count() != len(set(reviewer_ids)):
            raise ValidationError({"reviewer_ids": "One or more reviewer ids do not exist."})

        assignments = [
            ReviewAssignment.objects.create(
                document=document, version=version, reviewer=reviewer, assigned_by=request.user,
            )
            for reviewer in reviewers
        ]
        document.status = Document.STATUS_IN_REVIEW
        document.save(update_fields=["status"])
        audit_log(
            request.user, "submit_for_review", document=document,
            version=version.version_number, reviewers=[r.username for r in reviewers],
        )
        return Response(
            ReviewAssignmentSerializer(assignments, many=True).data, status=status.HTTP_201_CREATED
        )


class ReviewDecisionView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        document = get_object_or_404(Document, pk=pk)
        version = document.latest_version
        assignment = get_object_or_404(
            ReviewAssignment,
            document=document, version=version, reviewer=request.user,
            status=ReviewAssignment.STATUS_PENDING,
        )
        decision = request.data.get("decision")
        if decision not in ("approve", "reject"):
            raise ValidationError({"decision": "Must be 'approve' or 'reject'."})

        assignment.status = (
            ReviewAssignment.STATUS_APPROVED if decision == "approve" else ReviewAssignment.STATUS_REJECTED
        )
        assignment.comment = request.data.get("comment", "")
        assignment.decided_at = timezone.now()
        assignment.save(update_fields=["status", "comment", "decided_at"])
        audit_log(
            request.user, "approve" if decision == "approve" else "reject",
            document=document, version=version.version_number, comment=assignment.comment,
        )

        if decision == "reject":
            document.status = Document.STATUS_REJECTED
            document.save(update_fields=["status"])
        else:
            remaining_pending = ReviewAssignment.objects.filter(
                document=document, version=version, status=ReviewAssignment.STATUS_PENDING
            ).exists()
            if not remaining_pending:
                document.status = Document.STATUS_APPROVED
                document.save(update_fields=["status"])

        return Response(ReviewAssignmentSerializer(assignment).data)


class ReviewInboxView(generics.ListAPIView):
    serializer_class = ReviewAssignmentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return ReviewAssignment.objects.select_related("document", "reviewer").filter(
            reviewer=self.request.user, status=ReviewAssignment.STATUS_PENDING
        )
