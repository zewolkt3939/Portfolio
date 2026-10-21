(() => {
  document.documentElement.classList.add('js');
  const toggle = document.querySelector('.menu-toggle');
  const nav = document.querySelector('#primary-nav');
  if (toggle && nav) {
    toggle.hidden = false;
    const close = () => {
      toggle.setAttribute('aria-expanded', 'false');
      nav.classList.remove('is-open');
      toggle.querySelector('span').textContent = '+';
    };
    toggle.addEventListener('click', () => {
      const open = toggle.getAttribute('aria-expanded') !== 'true';
      toggle.setAttribute('aria-expanded', String(open));
      nav.classList.toggle('is-open', open);
      toggle.querySelector('span').textContent = open ? '−' : '+';
    });
    document.addEventListener('keydown', event => {
      if (event.key === 'Escape' && toggle.getAttribute('aria-expanded') === 'true') {
        close(); toggle.focus();
      }
    });
    matchMedia('(min-width: 761px)').addEventListener('change', close);
  }
  const filters = document.querySelector('.filter-bar');
  if (filters) {
    filters.hidden = false;
    filters.querySelectorAll('button').forEach(button => button.addEventListener('click', () => {
      filters.querySelectorAll('button').forEach(item => item.setAttribute('aria-pressed', String(item === button)));
      let count = 0;
      document.querySelectorAll('.research-card').forEach(card => {
        card.hidden = button.dataset.filter !== 'all' && card.dataset.topic !== button.dataset.filter;
        if (!card.hidden) count++;
      });
      document.querySelector('#result-count').textContent = document.documentElement.lang === 'vi'
        ? `${count} bài viết`
        : `${count} ${count === 1 ? 'article' : 'articles'}`;
    }));
  }
  document.querySelectorAll('[data-copy-email]').forEach(button => button.addEventListener('click', async () => {
    const status = document.querySelector('.toast');
    const vietnamese = document.documentElement.lang === 'vi';
    try {
      await navigator.clipboard.writeText(button.dataset.copyEmail);
      status.textContent = vietnamese ? 'Đã sao chép email' : 'Email copied';
    }
    catch {
      status.textContent = (vietnamese ? 'Sao chép địa chỉ này: ' : 'Copy this address: ') + button.dataset.copyEmail;
    }
    window.setTimeout(() => { status.textContent = ''; }, 5000);
  }));
  document.querySelectorAll('pre').forEach(block => {
    if (block.querySelector('.copy-code')) return;
    const button = document.createElement('button');
    button.type = 'button'; button.className = 'copy-code';
    button.textContent = document.documentElement.lang === 'vi' ? 'Sao chép' : 'Copy';
    button.addEventListener('click', async () => {
      await navigator.clipboard.writeText(block.innerText.replace(/^Copy|^Sao chép/, '').trim());
      button.textContent = document.documentElement.lang === 'vi' ? 'Đã chép' : 'Copied';
      setTimeout(() => { button.textContent = document.documentElement.lang === 'vi' ? 'Sao chép' : 'Copy'; }, 1800);
    });
    block.prepend(button);
  });
  const latest = document.querySelector('[data-latest-posts]');
  if (latest) {
    const vietnamese = document.documentElement.lang === 'vi';
    fetch('/api/v1/posts?page=1').then(response => {
      if (!response.ok) throw new Error('API unavailable');
      return response.json();
    }).then(data => {
      const list = latest.querySelector('[data-latest-list]');
      list.replaceChildren();
      data.items.slice(0, 5).forEach((post, index) => {
        const link = document.createElement('a'); link.className = 'work-row';
        link.href = `${vietnamese ? '/vi' : ''}/research/${post.slug}.html`;
        const number = document.createElement('span'); number.className = 'number'; number.textContent = String(index + 1).padStart(2, '0');
        const copy = document.createElement('div'); const title = document.createElement('h3'); title.textContent = vietnamese ? post.title_vi : (post.title_en || post.title_vi);
        const summary = document.createElement('p'); summary.textContent = vietnamese ? post.summary_vi : post.abstract_en;
        copy.append(title, summary);
        const meta = document.createElement('span'); meta.className = 'work-meta';
        const kindLabel = post.kind === 'writeup' ? 'Write-up' : 'Research';
        const platformLabel = post.platform || 'Lab';
        meta.innerHTML = `${kindLabel} · ${platformLabel}<br>${post.reading_minutes} ${vietnamese ? 'phút đọc' : 'min read'}`;
        const arrow = document.createElement('span'); arrow.className = 'arrow'; arrow.setAttribute('aria-hidden', 'true'); arrow.textContent = '↗';
        link.append(number, copy, meta, arrow); list.append(link);
      });
    }).catch(() => latest.hidden = true);
  }
})();


// Reading assistance is progressive: article text and navigation work without JS.
(() => {
  const vietnamese = document.documentElement.lang === 'vi';
  const article = document.querySelector('.article-content');
  if (article) {
    const progress = document.createElement('div');
    progress.className = 'reading-progress'; progress.setAttribute('aria-hidden','true');
    document.body.append(progress);
    let pending = false;
    const update = () => {
      const top = article.getBoundingClientRect().top + window.scrollY;
      const length = article.offsetHeight - window.innerHeight;
      const ratio = Math.max(0,Math.min(1,(window.scrollY-top)/Math.max(1,length)));
      progress.style.transform = `scaleX(${ratio})`; pending = false;
    };
    window.addEventListener('scroll',() => { if (!pending) { pending=true;requestAnimationFrame(update); } },{passive:true});
    window.addEventListener('resize',update); update();
  }
  const anchors = [...document.querySelectorAll('.case-toc a[href^="#"]')];
  if (anchors.length && 'IntersectionObserver' in window) {
    const observer = new IntersectionObserver(entries => {
      for (const entry of entries) if (entry.isIntersecting) {
        anchors.forEach(a => {
          const active = a.hash === `#${entry.target.id}`;
          a.classList.toggle('is-current',active);
          if (active) a.setAttribute('aria-current','location'); else a.removeAttribute('aria-current');
        });
      }
    },{rootMargin:'-10% 0px -60% 0px'});
    anchors.forEach(a => { const heading=document.getElementById(decodeURIComponent(a.hash.slice(1))); if(heading) observer.observe(heading); });
  }
  const figures = document.querySelectorAll('.article-content figure img,.project-study .case-content figure img');
  if (figures.length && typeof HTMLDialogElement !== 'undefined') {
    const dialog=document.createElement('dialog');dialog.className='image-dialog';
    dialog.setAttribute('aria-label',vietnamese?'Xem hình minh họa':'Figure viewer');
    const close=document.createElement('button');close.type='button';close.textContent=vietnamese?'Đóng hình ×':'Close figure ×';
    const large=document.createElement('img');large.alt='';dialog.append(close,large);document.body.append(dialog);
    close.addEventListener('click',()=>dialog.close());dialog.addEventListener('click',e=>{if(e.target===dialog)dialog.close();});
    figures.forEach(img=>{
      if(img.closest('a,button'))return;
      const button=document.createElement('button');button.type='button';button.className='figure-open';
      button.setAttribute('aria-label',`${vietnamese?'Phóng to hình: ':'Enlarge figure: '}${img.alt}`);
      img.before(button);button.append(img);
      button.addEventListener('click',()=>{large.src=img.currentSrc||img.src;large.alt=img.alt;dialog.showModal();});
    });
  }
  document.querySelectorAll('[data-video-seek]').forEach(button=>button.addEventListener('click',()=>{
    const video=document.getElementById(button.dataset.videoTarget||'p070-demo');
    if(video){video.currentTime=Number(button.dataset.videoSeek);video.play().catch(()=>{});video.focus();}
  }));
})();
