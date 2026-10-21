"""Publish reviewed research notes without modifying existing CMS articles."""
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from sqlalchemy import select
from portfolio_cms.database import SessionLocal
from portfolio_cms.models import Post
from portfolio_cms.schemas import PostInput, PublishChecklist
from portfolio_cms.content import apply_input, publish_post

def main():
    records=json.loads((ROOT/'content/research-notes.json').read_text(encoding='utf-8'))
    created=skipped=0
    with SessionLocal() as db:
        for record in records:
            if db.scalar(select(Post).where(Post.slug==record['slug'])):
                skipped+=1
                continue
            payload={key:value for key,value in record.items() if key!='source'}
            payload['body_markdown_vi']=(ROOT/'seeds/posts'/record['source']).read_text(encoding='utf-8')
            data=PostInput(**payload)
            post=Post(slug=data.slug,title_vi=data.title_vi,summary_vi=data.summary_vi,abstract_en=data.abstract_en,body_markdown_vi=data.body_markdown_vi,body_html_cached="")
            db.add(post)
            apply_input(db,post,data,None,reason='reviewed-research-import')
            publish_post(db,post,None,PublishChecklist(retired_or_permitted=True,redacted=True,sources_checked=True))
            created+=1
    print(f'Research notes: {created} created, {skipped} existing articles preserved.')

if __name__=='__main__':
    main()
