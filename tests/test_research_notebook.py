import json
from pathlib import Path
import importlib.util
from sqlalchemy import select

from portfolio_cms.models import Post
from tests.helpers import new_post, post_input
from portfolio_cms.content import apply_input, publish_post
from portfolio_cms.schemas import PublishChecklist


def test_editorial_import_preserves_articles_and_publishes_accessible_notes(client, session_factory, monkeypatch):
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location('publish_research_notes', root/'tools/publish_research_notes.py')
    importer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(importer)
    monkeypatch.setattr(importer, 'SessionLocal', session_factory)
    with session_factory() as db:
        data = post_input()
        existing = new_post(data)
        db.add(existing)
        apply_input(db, existing, data, None)
        publish_post(db, existing, None, PublishChecklist())
        saved = (existing.slug, existing.published_snapshot, existing.body_markdown_vi)
    importer.main()
    importer.main()
    with session_factory() as db:
        original = db.scalar(select(Post).where(Post.slug == saved[0]))
        assert (original.slug, original.published_snapshot, original.body_markdown_vi) == saved
        assert len(list(db.scalars(select(Post)))) == 4
    for record in json.loads((root/'content/research-notes.json').read_text(encoding='utf-8')):
        for prefix in ('', '/vi'):
            response = client.get(f'{prefix}/research/{record["slug"]}.html')
            assert response.status_code == 200
            assert 'Nguyễn Trường Bảo' in response.text
            assert 'Source-based research note' in response.text or 'Ghi chép từ hồ sơ nghiên cứu' in response.text
            assert '/assets/p070/' in response.text
    results = client.get('/vi/research.html?tag=P-070')
    assert results.status_code == 200
    assert results.text.count('class="research-card"') == 3
    assert 'name="q"' in results.text
    project = client.get('/vi/projects/p070-ai-redteam-soc.html')
    assert project.status_code == 200 and 'kind="captions"' in project.text
    assert 'preload="none"' in project.text
    video = client.get('/assets/p070/eviaura-demo.mp4', headers={'Range':'bytes=0-1023'})
    assert video.status_code == 206 and len(video.content) == 1024
