// Commentary detail modal - lazy-loads generated per-book HCF records.

(function () {
  'use strict';

  let playsById = new Map();
  let playsList = [];
  let commentaryConfig = null;
  let escapeHTML = window.escapeHTML || (value => String(value == null ? '' : value));
  let commentatorByKey = new Map();
  let bookOrder = new Map();
  let bookTitles = new Map();
  let onStateChange = null;
  let currentDetailParam = '';
  let els = null;

  const bookCache = new Map();
  const COLUMNS = [
    { key: 'ref', label: 'Passage', sortable: true, defaultDir: 'asc' },
    { key: 'commentator', label: 'Commentator', sortable: true, defaultDir: 'asc' },
    { key: 'year', label: 'Date', sortable: true, defaultDir: 'asc' },
    { key: 'work', label: 'Work', sortable: true, defaultDir: 'asc' },
    { key: 'comment', label: 'Comment', sortable: false },
    { key: 'source', label: 'Sources', sortable: false }
  ];
  const state = {
    comments: [],
    sorted: false,
    title: '',
    meta: '',
    page: 1,
    pageSize: 50,
    sortKey: 'ref',
    sortDir: 'asc'
  };

  function getDetailPathTemplate() {
    const metadata = commentaryConfig && commentaryConfig.metadata;
    return (metadata && metadata.detail_path_template) || 'commentary/{book}.json';
  }

  function isCommentaryDetailCell(columnKey) {
    return columnKey === 'commentary_interest'
      || (typeof columnKey === 'string'
        && columnKey.startsWith('commentary_')
        && columnKey !== 'commentary_per_verse');
  }

  function getCommentatorKey(columnKey) {
    if (!columnKey || columnKey === 'commentary_interest') return '';
    return String(columnKey).replace(/^commentary_/, '');
  }

  function parseCanonicalId(value) {
    const parts = String(value || '').split('.');
    if (parts.length < 3) return null;
    const chapter = Number.parseInt(parts[1], 10);
    const verse = Number.parseInt(parts[2], 10);
    if (!parts[0] || !Number.isFinite(chapter) || !Number.isFinite(verse)) return null;
    return { book: parts[0], chapter, verse };
  }

  function bookForRow(row) {
    if (!row) return '';
    const parsed = parseCanonicalId(row.id || row.canonical_id);
    if (parsed) return parsed.book;
    const idParts = String(row.id || '').split('.');
    if (idParts.length === 2 && idParts[0] && /^\d+$/.test(idParts[1])) {
      return idParts[0];
    }
    if (row.play_abbr) return String(row.play_abbr);
    const locAbbr = String(row.location || '')
      .split('.')
      .find(part => part && !/^\d+$/.test(part));
    if (locAbbr) return locAbbr;
    const play = playsById && typeof playsById.get === 'function'
      ? playsById.get(row.play_id)
      : null;
    return play && play.abbr ? String(play.abbr) : '';
  }

  function playTitleForRow(row, book) {
    if (!row) return bookTitles.get(book) || book || '';
    if (row.play_title) return String(row.play_title);
    if (row.title) return String(row.title);
    const play = playsById && typeof playsById.get === 'function'
      ? playsById.get(row.play_id)
      : null;
    return play && play.title
      ? String(play.title)
      : (bookTitles.get(book) || book || '');
  }

  // Infer scope from the row shape because the initial table can show book
  // rows even while the granularity selector remains on Verse.
  function scopeForRow(row) {
    if (!row) return null;
    const parsed = parseCanonicalId(row.id || row.canonical_id);
    if (parsed) {
      return {
        genre: '',
        book: parsed.book,
        chapter: parsed.chapter,
        verse: parsed.verse,
        label: `${playTitleForRow(row, parsed.book)} ${parsed.chapter}:${parsed.verse}`
      };
    }

    const book = bookForRow(row);
    if (book) {
      const chapter = Number.parseInt(row.act, 10);
      if (Number.isFinite(chapter)) {
        return {
          genre: '',
          book,
          chapter,
          verse: null,
          label: `${playTitleForRow(row, book)} ${chapter}`
        };
      }
      return {
        genre: '',
        book,
        chapter: null,
        verse: null,
        label: playTitleForRow(row, book)
      };
    }

    if (row.genre) {
      const genre = String(row.genre);
      return { genre, book: '', chapter: null, verse: null, label: genre };
    }
    return null;
  }

  function formatCount(value) {
    if (typeof window.formatCellNumber === 'function') {
      return window.formatCellNumber(value);
    }
    return value == null ? '' : String(value);
  }

  function buildCommentaryDetailLink(value, row, granularity, columnKey) {
    const count = Number(value) || 0;
    const scope = scopeForRow(row);
    if (!count || !scope) {
      const span = document.createElement('span');
      span.textContent = formatCount(value);
      return span;
    }

    const commentatorKey = getCommentatorKey(columnKey);
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'commentary-count-link';
    button.textContent = formatCount(value);
    if (scope.genre) button.dataset.genre = scope.genre;
    if (scope.book) button.dataset.book = scope.book;
    if (scope.chapter != null) button.dataset.chapter = String(scope.chapter);
    if (scope.verse != null) button.dataset.verse = String(scope.verse);
    button.dataset.count = String(count);
    button.dataset.scopeLabel = scope.label;
    button.dataset.commentatorKey = commentatorKey;
    if (commentatorKey && commentatorByKey.has(commentatorKey)) {
      button.dataset.commentatorLabel = commentatorByKey.get(commentatorKey).label;
    }
    button.title = commentatorKey
      ? `Read ${button.dataset.commentatorLabel || commentatorKey} comments`
      : 'Read individual historical comments';
    return button;
  }

  function totalPages(length, pageSize) {
    if (typeof window.getTotalPages === 'function') {
      return window.getTotalPages(length, pageSize);
    }
    return Math.max(1, Math.ceil(length / pageSize));
  }

  function pageRows(items, page, pageSize) {
    if (typeof window.paginateArray === 'function') {
      return window.paginateArray(items, page, pageSize);
    }
    return items.slice((page - 1) * pageSize, page * pageSize);
  }

  function ensureModal() {
    if (els) return els;
    const overlay = document.createElement('div');
    overlay.className = 'commentary-detail-overlay';
    const headerCells = COLUMNS.map((column) => {
      const className = column.sortable
        ? 'commentary-detail-sortable'
        : 'commentary-detail-unsortable';
      const title = column.sortable ? ' title="Click to sort"' : '';
      return `<th data-key="${column.key}" class="${className}"${title}>${escapeHTML(column.label)}</th>`;
    }).join('');
    overlay.innerHTML = `
      <div class="commentary-detail-modal" role="dialog" aria-modal="true" aria-label="Historical commentary">
        <div class="commentary-detail-head">
          <button type="button" class="commentary-detail-close" aria-label="Close">&times;</button>
          <h3 id="commentaryDetailTitle"></h3>
          <div class="commentary-detail-meta" id="commentaryDetailMeta"></div>
        </div>
        <div class="commentary-detail-body">
          <div class="commentary-detail-loading" id="commentaryDetailLoading">Loading comments...</div>
          <table class="commentary-detail-table is-hidden" id="commentaryDetailTable">
            <thead><tr>${headerCells}</tr></thead>
            <tbody></tbody>
          </table>
        </div>
        <div class="commentary-detail-pagination pagination is-hidden" id="commentaryDetailPagination">
          <button type="button" id="commentaryDetailFirst">First</button>
          <button type="button" id="commentaryDetailPrev">Prev</button>
          <span class="page-info" id="commentaryDetailPageInfo">Page 1 of 1</span>
          <button type="button" id="commentaryDetailNext">Next</button>
          <button type="button" id="commentaryDetailLast">Last</button>
          <label>
            Rows per page:
            <select id="commentaryDetailPageSize">
              <option value="25">25</option>
              <option value="50" selected>50</option>
              <option value="100">100</option>
              <option value="250">250</option>
            </select>
          </label>
          <span class="page-info" id="commentaryDetailTotalInfo"></span>
        </div>
      </div>
    `;
    document.body.appendChild(overlay);

    els = {
      overlay,
      body: overlay.querySelector('.commentary-detail-body'),
      title: overlay.querySelector('#commentaryDetailTitle'),
      meta: overlay.querySelector('#commentaryDetailMeta'),
      loading: overlay.querySelector('#commentaryDetailLoading'),
      table: overlay.querySelector('#commentaryDetailTable'),
      tbody: overlay.querySelector('#commentaryDetailTable tbody'),
      headRow: overlay.querySelector('#commentaryDetailTable thead tr'),
      pagination: overlay.querySelector('#commentaryDetailPagination'),
      first: overlay.querySelector('#commentaryDetailFirst'),
      prev: overlay.querySelector('#commentaryDetailPrev'),
      next: overlay.querySelector('#commentaryDetailNext'),
      last: overlay.querySelector('#commentaryDetailLast'),
      pageInfo: overlay.querySelector('#commentaryDetailPageInfo'),
      totalInfo: overlay.querySelector('#commentaryDetailTotalInfo'),
      pageSize: overlay.querySelector('#commentaryDetailPageSize')
    };

    overlay.querySelector('.commentary-detail-close').addEventListener('click', closeModal);
    overlay.addEventListener('click', (event) => {
      if (event.target === overlay) closeModal();
    });
    els.headRow.addEventListener('click', (event) => {
      const th = event.target && typeof event.target.closest === 'function'
        ? event.target.closest('th')
        : null;
      if (!th || !els.headRow.contains(th)) return;
      const column = COLUMNS.find(item => item.key === th.dataset.key);
      if (!column || !column.sortable) return;
      if (state.sortKey === column.key) {
        state.sortDir = state.sortDir === 'asc' ? 'desc' : 'asc';
      } else {
        state.sortKey = column.key;
        state.sortDir = column.defaultDir || 'asc';
      }
      state.sorted = false;
      state.page = 1;
      renderComments();
    });

    const goToPage = (page) => {
      const pages = totalPages(state.comments.length, state.pageSize);
      const next = Math.max(1, Math.min(page, pages));
      if (next === state.page) return;
      state.page = next;
      renderComments();
    };
    els.first.addEventListener('click', () => goToPage(1));
    els.prev.addEventListener('click', () => goToPage(state.page - 1));
    els.next.addEventListener('click', () => goToPage(state.page + 1));
    els.last.addEventListener('click', () => goToPage(Number.MAX_SAFE_INTEGER));
    els.pageSize.addEventListener('change', (event) => {
      state.pageSize = Number.parseInt(event.target.value, 10) || 50;
      state.page = 1;
      renderComments();
    });
    return els;
  }

  function notifyStateChange() {
    if (typeof onStateChange === 'function') onStateChange();
  }

  function closeModal() {
    if (els) els.overlay.classList.remove('open');
    if (currentDetailParam) {
      currentDetailParam = '';
      notifyStateChange();
    }
  }

  function setLoading(message) {
    const modal = ensureModal();
    modal.loading.textContent = message || 'Loading comments...';
    modal.loading.classList.remove('is-hidden');
    modal.table.classList.add('is-hidden');
    modal.tbody.innerHTML = '';
    modal.pagination.classList.add('is-hidden');
  }

  async function loadBook(book) {
    if (bookCache.has(book)) return bookCache.get(book);
    const path = getDetailPathTemplate().replace('{book}', encodeURIComponent(book));
    const promise = fetch(path).then((response) => {
      if (!response.ok) throw new Error(`Failed to load ${path}: ${response.status}`);
      return response.json();
    });
    bookCache.set(book, promise);
    return promise;
  }

  function booksForScope(scope) {
    if (scope.genre) {
      return playsList
        .filter(play => String(play.genre || '') === scope.genre && play.abbr)
        .map(play => String(play.abbr));
    }
    return scope.book ? [scope.book] : [];
  }

  function normalizeComment(record, bookData, index) {
    if (!Array.isArray(record)) return null;
    const authors = Array.isArray(bookData.authors) ? bookData.authors : [];
    const works = Array.isArray(bookData.works) ? bookData.works : [];
    const author = authors[Number(record[0])];
    const work = works[Number(record[1])];
    if (!author || !Array.isArray(work)) return null;
    const book = String(bookData.book || '');
    return {
      index,
      id: String(record[2] || `${book}-${index}`),
      book,
      bookIdx: bookOrder.has(book) ? bookOrder.get(book) : 999,
      startChapter: Number(record[3]) || 0,
      startVerse: Number(record[4]) || 0,
      endChapter: Number(record[5]) || Number(record[3]) || 0,
      endVerse: Number(record[6]) || Number(record[4]) || 0,
      year: Number(record[7]) || 0,
      text: String(record[8] || ''),
      restricted: Boolean(record[9]),
      hcfUrl: String(record[10] || ''),
      author,
      workTitle: String(work[0] || ''),
      sourceUrl: String(work[1] || ''),
      commentatorLower: String(author.name || '').toLowerCase(),
      workLower: String(work[0] || '').toLowerCase()
    };
  }

  function collectComments(bookDataList, scope, commentatorKey) {
    const comments = [];
    const seen = new Set();
    bookDataList.forEach((bookData) => {
      if (!bookData) return;
      const allComments = Array.isArray(bookData.comments) ? bookData.comments : [];
      const verses = bookData.verses && typeof bookData.verses === 'object'
        ? bookData.verses
        : {};
      Object.keys(verses).forEach((canonicalId) => {
        const parsed = parseCanonicalId(canonicalId);
        if (!parsed) return;
        if (scope.book && parsed.book !== scope.book) return;
        if (scope.chapter != null && parsed.chapter !== scope.chapter) return;
        if (scope.verse != null && parsed.verse !== scope.verse) return;
        const indexes = Array.isArray(verses[canonicalId]) ? verses[canonicalId] : [];
        indexes.forEach((indexValue) => {
          const index = Number(indexValue);
          const identity = `${bookData.book}:${index}`;
          if (!Number.isInteger(index) || seen.has(identity)) return;
          const comment = normalizeComment(allComments[index], bookData, index);
          if (!comment) return;
          if (commentatorKey && comment.author.key !== commentatorKey) return;
          seen.add(identity);
          comments.push(comment);
        });
      });
    });
    return comments;
  }

  function compareText(a, b) {
    return a < b ? -1 : a > b ? 1 : 0;
  }

  function compareRefs(a, b) {
    return (a.bookIdx - b.bookIdx)
      || (a.startChapter - b.startChapter)
      || (a.startVerse - b.startVerse)
      || (a.endChapter - b.endChapter)
      || (a.endVerse - b.endVerse)
      || compareText(a.commentatorLower, b.commentatorLower)
      || compareText(a.workLower, b.workLower);
  }

  function sortComments() {
    if (state.sorted) return;
    const direction = state.sortDir === 'desc' ? -1 : 1;
    let compare = compareRefs;
    if (state.sortKey === 'commentator') {
      compare = (a, b) => compareText(a.commentatorLower, b.commentatorLower) || compareRefs(a, b);
    } else if (state.sortKey === 'year') {
      compare = (a, b) => (a.year - b.year) || compareRefs(a, b);
    } else if (state.sortKey === 'work') {
      compare = (a, b) => compareText(a.workLower, b.workLower) || compareRefs(a, b);
    }
    state.comments.sort((a, b) => direction * compare(a, b));
    state.sorted = true;
  }

  function updateSortIndicators() {
    if (!els) return;
    els.headRow.querySelectorAll('th').forEach((th) => {
      th.classList.remove('sorted-asc', 'sorted-desc');
      if (th.dataset.key === state.sortKey) {
        th.classList.add(state.sortDir === 'asc' ? 'sorted-asc' : 'sorted-desc');
      }
    });
  }

  function formatReference(comment) {
    const title = bookTitles.get(comment.book) || comment.book;
    const start = `${comment.startChapter}:${comment.startVerse}`;
    if (comment.startChapter === comment.endChapter
      && comment.startVerse === comment.endVerse) {
      return `${title} ${start}`;
    }
    if (comment.startChapter === comment.endChapter) {
      return `${title} ${start}-${comment.endVerse}`;
    }
    return `${title} ${start}-${comment.endChapter}:${comment.endVerse}`;
  }

  function formatYear(year) {
    if (!year || year >= 9999) return 'Unknown';
    if (year < 0) return `${Math.abs(year)} BC`;
    return `AD ${year}`;
  }

  function safeExternalUrl(value) {
    if (!value) return '';
    try {
      const url = new URL(value, window.location.href);
      return url.protocol === 'http:' || url.protocol === 'https:' ? url.href : '';
    } catch (error) {
      return '';
    }
  }

  function appendExternalLink(cell, href, label) {
    const safeUrl = safeExternalUrl(href);
    if (!safeUrl) return;
    const link = document.createElement('a');
    link.href = safeUrl;
    link.target = '_blank';
    link.rel = 'noopener';
    link.textContent = label;
    cell.appendChild(link);
  }

  function renderComments() {
    const modal = ensureModal();
    modal.title.textContent = state.title;
    modal.meta.textContent = state.meta;
    modal.loading.classList.add('is-hidden');
    modal.tbody.innerHTML = '';

    if (!state.comments.length) {
      modal.loading.textContent = 'No commentary details are available for this count.';
      modal.loading.classList.remove('is-hidden');
      modal.table.classList.add('is-hidden');
      modal.pagination.classList.add('is-hidden');
      return;
    }

    sortComments();
    updateSortIndicators();
    modal.table.classList.remove('is-hidden');
    const pages = totalPages(state.comments.length, state.pageSize);
    state.page = Math.max(1, Math.min(state.page, pages));
    const rows = pageRows(state.comments, state.page, state.pageSize);
    const fragment = document.createDocumentFragment();

    rows.forEach((comment) => {
      const tr = document.createElement('tr');
      tr.id = `commentary-${comment.id}`;

      const refCell = document.createElement('td');
      refCell.className = 'commentary-ref-cell';
      refCell.textContent = formatReference(comment);
      tr.appendChild(refCell);

      const commentatorCell = document.createElement('td');
      commentatorCell.className = 'commentary-commentator-cell';
      const wikiUrl = safeExternalUrl(comment.author.wiki_url);
      if (wikiUrl) {
        const authorLink = document.createElement('a');
        authorLink.href = wikiUrl;
        authorLink.target = '_blank';
        authorLink.rel = 'noopener';
        authorLink.textContent = comment.author.name || 'Commentary';
        commentatorCell.appendChild(authorLink);
      } else {
        commentatorCell.textContent = comment.author.name || 'Commentary';
      }
      if (comment.author.category) {
        const category = document.createElement('span');
        category.className = 'commentary-commentator-meta';
        category.textContent = comment.author.category;
        commentatorCell.appendChild(category);
      }
      tr.appendChild(commentatorCell);

      const yearCell = document.createElement('td');
      yearCell.className = 'commentary-year-cell';
      yearCell.textContent = formatYear(comment.year);
      yearCell.title = 'Approximate date supplied by HistoricalChristianFaith';
      tr.appendChild(yearCell);

      const workCell = document.createElement('td');
      workCell.className = 'commentary-work-cell';
      workCell.textContent = comment.workTitle || 'Source work not identified';
      tr.appendChild(workCell);

      const commentCell = document.createElement('td');
      commentCell.className = 'commentary-comment-cell';
      const preview = document.createElement('div');
      preview.className = 'commentary-preview commentary-preview-clamp';
      preview.textContent = comment.text;
      if (!comment.restricted && comment.text.length > 360) {
        preview.classList.add('is-expandable');
        preview.title = 'Click to expand or collapse this comment';
        preview.addEventListener('click', () => {
          preview.classList.toggle('commentary-preview-clamp');
        });
      }
      commentCell.appendChild(preview);
      if (comment.restricted) {
        const note = document.createElement('div');
        note.className = 'commentary-rights-note';
        note.textContent = 'Short preview only; this modern text may remain under copyright.';
        commentCell.appendChild(note);
      }
      tr.appendChild(commentCell);

      const sourceCell = document.createElement('td');
      sourceCell.className = 'commentary-link-cell';
      appendExternalLink(sourceCell, comment.sourceUrl, 'Source work');
      appendExternalLink(sourceCell, comment.hcfUrl, 'HCF passage');
      tr.appendChild(sourceCell);
      fragment.appendChild(tr);
    });

    modal.tbody.appendChild(fragment);
    modal.body.scrollTop = 0;
    modal.pageInfo.textContent = `Page ${state.page} of ${pages}`;
    modal.totalInfo.textContent = `(${state.comments.length.toLocaleString('en-US')} comments)`;
    modal.first.disabled = state.page === 1;
    modal.prev.disabled = state.page === 1;
    modal.next.disabled = state.page === pages;
    modal.last.disabled = state.page === pages;
    modal.pageSize.value = String(state.pageSize);
    modal.pagination.classList.toggle('is-hidden', state.comments.length <= 25);
  }

  function describeComments(comments, commentatorLabel, expected, failedBooks) {
    const countLabel = comments.length === 1 ? 'comment' : 'unique comments';
    const parts = [`${comments.length.toLocaleString('en-US')} ${countLabel}`];
    const works = new Set(comments.map(comment => comment.workTitle).filter(Boolean));
    if (works.size > 1) parts.push(`${works.size.toLocaleString('en-US')} works`);
    if (commentatorLabel) parts.push(commentatorLabel);
    const restricted = comments.filter(comment => comment.restricted).length;
    if (restricted) parts.push(`${restricted.toLocaleString('en-US')} modern previews`);
    if (expected && expected !== comments.length) {
      parts.push(`${expected.toLocaleString('en-US')} verse-overlaps in the count`);
    }
    if (failedBooks && failedBooks.length) {
      parts.push(`details unavailable for ${failedBooks.join(', ')}`);
    }
    return parts.join(' | ');
  }

  function scopeToParam(scope, commentatorKey) {
    let base = '';
    if (scope.genre) {
      base = `genre:${scope.genre}`;
    } else if (scope.book) {
      base = scope.book;
      if (scope.chapter != null) base += `.${scope.chapter}`;
      if (scope.verse != null) base += `.${scope.verse}`;
    }
    if (!base) return '';
    return commentatorKey ? `${base}~${commentatorKey}` : base;
  }

  function paramToScope(value) {
    const [main, commentatorKey = ''] = String(value || '').split('~');
    if (!main) return null;
    if (main.startsWith('genre:')) {
      const genre = main.slice('genre:'.length);
      if (!genre) return null;
      return {
        scope: { genre, book: '', chapter: null, verse: null, label: genre },
        commentatorKey
      };
    }
    const parts = main.split('.');
    const book = parts[0];
    if (!book || !bookOrder.has(book)) return null;
    const chapter = parts.length > 1 ? Number.parseInt(parts[1], 10) : NaN;
    const verse = parts.length > 2 ? Number.parseInt(parts[2], 10) : NaN;
    let label = bookTitles.get(book) || book;
    if (Number.isFinite(chapter)) label += ` ${chapter}`;
    if (Number.isFinite(verse)) label += `:${verse}`;
    return {
      scope: {
        genre: '',
        book,
        chapter: Number.isFinite(chapter) ? chapter : null,
        verse: Number.isFinite(verse) ? verse : null,
        label
      },
      commentatorKey
    };
  }

  async function openScope(scope, commentatorKey, expectedCount) {
    const books = booksForScope(scope);
    if (!books.length) return;

    currentDetailParam = scopeToParam(scope, commentatorKey);
    notifyStateChange();
    const commentatorLabel = (commentatorByKey.get(commentatorKey) || {}).label || '';
    const modal = ensureModal();
    modal.overlay.classList.add('open');
    state.title = commentatorLabel
      ? `${commentatorLabel} on ${scope.label}`
      : `Historical commentary on ${scope.label}`;
    state.meta = 'Loading...';
    state.comments = [];
    state.sorted = false;
    state.page = 1;
    state.sortKey = 'ref';
    state.sortDir = 'asc';
    modal.title.textContent = state.title;
    modal.meta.textContent = state.meta;
    setLoading(books.length > 1
      ? `Loading comments from ${books.length} books...`
      : 'Loading comments...');

    try {
      const bookDataList = await Promise.all(
        books.map(book => loadBook(book).catch(() => null))
      );
      const failedBooks = books.filter((book, index) => !bookDataList[index]);
      if (failedBooks.length === books.length) {
        throw new Error('Unable to load commentary details.');
      }
      const comments = collectComments(bookDataList, scope, commentatorKey);
      state.comments = comments;
      state.sorted = false;
      const expected = Number(expectedCount) || comments.length;
      state.meta = describeComments(comments, commentatorLabel, expected, failedBooks);
      renderComments();
    } catch (error) {
      modal.title.textContent = state.title;
      modal.meta.textContent = '';
      modal.table.classList.add('is-hidden');
      modal.tbody.innerHTML = '';
      modal.loading.innerHTML = `<span class="warning">${escapeHTML(error.message || 'Unable to load commentary details.')}</span>`;
      modal.loading.classList.remove('is-hidden');
      modal.pagination.classList.add('is-hidden');
    }
  }

  function openFromTrigger(trigger) {
    const scope = {
      genre: trigger.dataset.genre || '',
      book: trigger.dataset.book || '',
      chapter: trigger.dataset.chapter
        ? Number.parseInt(trigger.dataset.chapter, 10)
        : null,
      verse: trigger.dataset.verse
        ? Number.parseInt(trigger.dataset.verse, 10)
        : null,
      label: trigger.dataset.scopeLabel
        || trigger.dataset.book
        || trigger.dataset.genre
        || ''
    };
    return openScope(
      scope,
      trigger.dataset.commentatorKey || '',
      Number(trigger.dataset.count) || 0
    );
  }

  document.addEventListener('click', (event) => {
    const trigger = event.target && typeof event.target.closest === 'function'
      ? event.target.closest('.commentary-count-link')
      : null;
    if (!trigger) return;
    event.preventDefault();
    event.stopPropagation();
    openFromTrigger(trigger);
  });

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && els && els.overlay.classList.contains('open')) {
      closeModal();
    }
  });

  window.initCommentaryDetail = function (deps) {
    deps = deps || {};
    playsById = deps.playsById || new Map();
    playsList = Array.isArray(deps.plays) ? deps.plays : [];
    commentaryConfig = deps.commentaryInterestConfig || null;
    onStateChange = typeof deps.onStateChange === 'function' ? deps.onStateChange : null;
    escapeHTML = deps.escapeHTML || window.escapeHTML || escapeHTML;
    bookOrder = new Map();
    bookTitles = new Map();
    playsList.forEach((play, index) => {
      const abbr = play && play.abbr ? String(play.abbr) : '';
      if (!abbr) return;
      bookOrder.set(abbr, index);
      bookTitles.set(abbr, String(play.title || abbr));
    });
    const commentators = commentaryConfig
      && commentaryConfig.metadata
      && Array.isArray(commentaryConfig.metadata.commentators)
      ? commentaryConfig.metadata.commentators
      : [];
    commentatorByKey = new Map(commentators.map(item => [
      String(item.key || ''),
      {
        label: String(item.label || item.name || item.key || ''),
        name: String(item.name || item.label || item.key || '')
      }
    ]).filter(([key]) => key));
  };

  window.isCommentaryDetailCell = isCommentaryDetailCell;
  window.buildCommentaryDetailLink = buildCommentaryDetailLink;
  window.getCommentaryDetailParam = () => currentDetailParam;
  window.closeCommentaryDetail = closeModal;
  window.openCommentaryDetailFromParam = function (value) {
    const parsed = paramToScope(value);
    if (!parsed) return false;
    openScope(parsed.scope, parsed.commentatorKey, 0);
    return true;
  };
})();
