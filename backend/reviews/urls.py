from django.urls import path

from .views import ReviewDecisionView, ReviewInboxView, SubmitForReviewView

urlpatterns = [
    path("documents/<int:pk>/submit-for-review/", SubmitForReviewView.as_view(), name="submit-for-review"),
    path("documents/<int:pk>/review-decision/", ReviewDecisionView.as_view(), name="review-decision"),
    path("reviews/mine/", ReviewInboxView.as_view(), name="reviews-mine"),
]
