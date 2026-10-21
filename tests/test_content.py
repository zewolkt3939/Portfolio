from sqlalchemy import select

from portfolio_cms.content import apply_input, publish_post, public_snapshot, restore_revision
from portfolio_cms.models import PostRevision
from portfolio_cms.schemas import PublishChecklist
from tests.helpers import new_post, post_input


CHECKLIST = PublishChecklist(retired_or_permitted=True, redacted=True, sources_checked=True)


def test_draft_publish_edit_and_revision_restore(db):
    original = post_input()
    post = new_post(original)
    db.add(post)
    apply_input(db, post, original, None)
    assert public_snapshot(post) is None
    publish_post(db, post, None, CHECKLIST)
    first_public = public_snapshot(post)

    changed_data = original.model_copy(update={"title_vi": "Tiêu đề bản nháp đã thay đổi"})
    apply_input(db, post, changed_data, None)
    assert post.has_unpublished_changes
    assert public_snapshot(post)["title_vi"] == first_public["title_vi"]

    first_revision = db.scalar(
        select(PostRevision).where(PostRevision.post_id == post.id, PostRevision.reason == "save").order_by(PostRevision.created_at)
    )
    restore_revision(db, post, first_revision, None)
    assert post.slug == original.slug
    assert post.title_vi == original.title_vi


def test_writeup_requires_publish_checklist(db):
    data = post_input(kind="writeup")
    post = new_post(data)
    db.add(post)
    apply_input(db, post, data, None)
    try:
        publish_post(db, post, None, PublishChecklist())
    except ValueError as exc:
        assert "checklist" in str(exc)
    else:
        raise AssertionError("write-up published without checklist")


def test_slug_is_locked_after_first_publish(db):
    data = post_input("stable-url")
    post = new_post(data)
    db.add(post)
    apply_input(db, post, data, None)
    publish_post(db, post, None, CHECKLIST)
    changed = data.model_copy(update={"slug": "changed-url"})
    try:
        apply_input(db, post, changed, None)
    except ValueError as exc:
        assert "URL ổn định" in str(exc)
    else:
        raise AssertionError("published slug was changed")
