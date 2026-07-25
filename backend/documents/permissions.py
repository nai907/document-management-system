from django.db.models import Q
from django.utils import timezone
from rest_framework.permissions import BasePermission

from .models import Document, DocumentPermission

OWNER_DEFAULT_ACTIONS = {"view", "edit", "download"}


def visible_documents_for(user):
    """Queryset of documents `user` may at least view: admins see everything,
    everyone else sees what they own plus what's been explicitly granted to
    them or a group they belong to (grant must not be expired)."""
    if not user or not user.is_authenticated:
        return Document.objects.none()
    if user.is_superuser or user.role == user.ROLE_ADMIN:
        return Document.objects.all()

    now = timezone.now()
    active_grant = Q(
        permissions__can_view=True
    ) & (Q(permissions__expires_at__isnull=True) | Q(permissions__expires_at__gt=now))
    granted_directly = active_grant & Q(permissions__user=user)
    granted_via_group = active_grant & Q(permissions__group__in=user.groups.all())

    return Document.objects.filter(
        Q(owner=user) | granted_directly | granted_via_group
    ).distinct()


def has_permission(user, document, action):
    """Resolve whether `user` may perform `action` (view/edit/approve/download) on
    `document`. Order: admin always wins, then ownership (view/edit/download only,
    not approve - owners shouldn't self-approve), then explicit per-document grants
    to the user or any group they belong to, ignoring expired grants."""
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser or user.role == user.ROLE_ADMIN:
        return True
    if document.owner_id == user.id and action in OWNER_DEFAULT_ACTIONS:
        return True

    now = timezone.now()
    field = {
        "view": "can_view",
        "edit": "can_edit",
        "approve": "can_approve",
        "download": "can_download",
    }[action]

    grants = DocumentPermission.objects.filter(
        Q(user=user) | Q(group__in=user.groups.all()),
        document=document,
        **{field: True},
    ).filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
    return grants.exists()


class HasDocumentPermission(BasePermission):
    """DRF permission class factory: HasDocumentPermission('edit') checks the
    `document` resolved by the view (via get_document()) against has_permission()."""

    def __init__(self, action):
        self.action = action

    def __call__(self):
        # DRF instantiates permission_classes entries with no args; returning self
        # from __call__ lets `HasDocumentPermission('edit')` be used directly in
        # a permission_classes list.
        return self

    def has_permission(self, request, view):
        document = view.get_document()
        return has_permission(request.user, document, self.action)
