(() => {
  const csrf = document.body.dataset.csrf;
  const toast = document.querySelector('.admin-toast');
  const notify = (message, error = false) => {
    if (!toast) return;
    toast.textContent = message;
    toast.style.background = error ? '#752c28' : '#222722';
    toast.classList.add('visible');
    setTimeout(() => toast.classList.remove('visible'), 5000);
  };
  const jsonFetch = async (url, options = {}) => {
    const response = await fetch(url, {
      ...options,
      headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf, ...(options.headers || {})}
    });
    const data = await response.json();
    if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail));
    return data;
  };

  const notion = document.querySelector('#notion-import');
  if (notion) notion.addEventListener('submit', async event => {
    event.preventDefault();
    const status = notion.querySelector('.form-status');
    status.textContent = 'Đang đọc page và lưu ảnh…';
    try {
      const data = await jsonFetch('/api/admin/import/notion', {method: 'POST', body: JSON.stringify({url: notion.url.value})});
      status.textContent = data.warnings?.length ? data.warnings.join(' ') : 'Đã tạo bản nháp.';
      window.location.assign(data.edit_url);
    } catch (error) { status.textContent = error.message; }
  });

  const form = document.querySelector('#post-editor');
  if (!form) return;
  const source = document.querySelector('#markdown-source');
  const preview = document.querySelector('#markdown-preview');
  const state = document.querySelector('#save-state');
  let dirty = false;
  let previewTimer;
  const collect = () => Object.fromEntries([
    ...['slug','kind','title_vi','title_en','summary_vi','abstract_en','body_markdown_vi','platform','machine','difficulty','evidence_type','cover_url'].map(name => [name, form.elements[name].value || null]),
    ['tags', form.elements.tags.value.split(',').map(value => value.trim()).filter(Boolean)]
  ]);
  const updatePreview = async () => {
    try {
      const data = await jsonFetch('/api/admin/preview', {method: 'POST', body: JSON.stringify({body_markdown_vi: source.value})});
      preview.innerHTML = data.html;
      document.querySelector('#reading-time').textContent = `${data.reading_minutes} phút đọc`;
      preview.querySelectorAll('pre').forEach(block => {
        const button = document.createElement('button'); button.type = 'button'; button.textContent = 'Copy'; button.className = 'copy-code';
        button.addEventListener('click', () => navigator.clipboard.writeText(block.innerText)); block.prepend(button);
      });
    } catch (error) { preview.textContent = error.message; }
  };
  const changed = () => { dirty = true; state.textContent = 'Có thay đổi chưa lưu.'; clearTimeout(previewTimer); previewTimer = setTimeout(updatePreview, 350); };
  form.addEventListener('input', changed);
  window.addEventListener('beforeunload', event => { if (dirty) { event.preventDefault(); event.returnValue = ''; } });
  const save = async (silent = false) => {
    const payload = collect(); payload.title_en ||= null; payload.platform ||= null; payload.machine ||= null; payload.difficulty ||= null; payload.cover_url ||= null;
    const id = form.dataset.postId;
    try {
      const data = await jsonFetch(id ? `/api/admin/posts/${id}` : '/api/admin/posts', {method: id ? 'PUT' : 'POST', body: JSON.stringify(payload)});
      dirty = false; form.dataset.postId = data.id; state.textContent = `Đã lưu lúc ${new Date().toLocaleTimeString('vi-VN')}.`;
      document.querySelector('[data-open-publish]').disabled = false;
      const fullPreview = document.querySelector('[data-full-preview]'); fullPreview.hidden = false; fullPreview.href = `/admin/posts/${data.id}/preview`;
      document.querySelector('[data-action="archive"]').hidden = false;
      if (!id) history.replaceState({}, '', `/admin/posts/${data.id}/edit`);
      if (!silent) notify('Đã lưu bản nháp.');
      return data;
    } catch (error) { notify(error.message, true); throw error; }
  };
  document.querySelector('[data-action="save"]').addEventListener('click', () => save());
  document.querySelector('[data-action="archive"]').addEventListener('click', async () => {
    if (!confirm('Archive bài này? Bài sẽ biến mất khỏi website public nhưng vẫn giữ dữ liệu và lịch sử.')) return;
    try { await jsonFetch(`/api/admin/posts/${form.dataset.postId}/archive`, {method:'POST'}); dirty=false; location.assign('/admin/posts?status=archived'); } catch(error){notify(error.message,true);}
  });
  setInterval(() => { if (dirty) save(true).catch(() => {}); }, 30000);
  const dialog = document.querySelector('#publish-dialog');
  document.querySelector('[data-open-publish]').addEventListener('click', async () => { if (dirty) await save(true); dialog.showModal(); });
  dialog.querySelector('[data-action="publish"]').addEventListener('click', async () => {
    const payload = Object.fromEntries(['retired_or_permitted','redacted','sources_checked'].map(name => [name, dialog.elements[name].checked]));
    try { await jsonFetch(`/api/admin/posts/${form.dataset.postId}/publish`, {method:'POST', body:JSON.stringify(payload)}); dirty=false; notify('Bài đã được publish.'); dialog.close(); setTimeout(()=>location.reload(),700); } catch(error){notify(error.message,true);}
  });
  document.querySelectorAll('[data-restore]').forEach(button => button.addEventListener('click', async () => {
    if (!confirm('Khôi phục phiên bản này vào editor? Bài public chỉ đổi khi bạn publish lại.')) return;
    try { await jsonFetch(`/api/admin/posts/${form.dataset.postId}/revisions/${button.dataset.restore}/restore`, {method:'POST'}); location.reload(); } catch(error){notify(error.message,true);}
  }));
  const media = document.querySelector('#media-file');
  media.addEventListener('change', async () => {
    if (!media.files[0]) return;
    const alt = prompt('Mô tả ảnh bằng tiếng Việt (alt text):') || '';
    const data = new FormData(); data.append('image', media.files[0]); data.append('alt_vi', alt);
    try {
      const response = await fetch('/api/admin/media', {method:'POST', headers:{'X-CSRF-Token':csrf}, body:data}); const result = await response.json();
      if (!response.ok) throw new Error(result.detail); const insertion = `\n![${result.alt_vi}](${result.url})\n`; const start=source.selectionStart; source.setRangeText(insertion,start,source.selectionEnd,'end'); changed(); notify('Đã tải và chèn ảnh.');
    } catch(error){notify(error.message,true);}
  });
  updatePreview();
})();
