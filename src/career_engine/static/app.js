'use strict';
// All external text (postings, titles, URLs) is rendered with textContent only: never as HTML.

const REQUEST_HEADERS = {'X-Requested-With': 'career-engine'};
const STAGE_CHOICES = ['DRAFT', 'PREPARING', 'BLOCKED'];
const $ = (id) => document.getElementById(id);

function el(tag, options = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(options)) {
    if (key === 'text') node.textContent = value;
    else if (key === 'className') node.className = value;
    else if (key.startsWith('on')) node.addEventListener(key.slice(2), value);
    else node.setAttribute(key, value);
  }
  for (const child of children) node.append(child);
  return node;
}

function clear(node) {
  while (node.firstChild) node.removeChild(node.firstChild);
}

function unknown() {
  return el('span', {className: 'unknown', text: 'unknown'});
}

function valueOrUnknown(value) {
  return value === null || value === undefined || value === '' ? unknown() : document.createTextNode(String(value));
}

function showMessage(text) {
  $('error').hidden = true;
  $('message').textContent = text;
  $('message').hidden = false;
}

function showError(error) {
  $('message').hidden = true;
  const code = error && error.code ? '[' + error.code + '] ' : '';
  $('error').textContent = code + (error && error.message ? error.message : String(error));
  $('error').hidden = false;
}

function clearNotices() {
  $('message').hidden = true;
  $('error').hidden = true;
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    cache: 'no-store',
    ...options,
    headers: {...REQUEST_HEADERS, ...(options.headers || {})},
  });
  if (!response.ok) {
    let body = {};
    try { body = await response.json(); } catch (ignored) { /* non-JSON error body */ }
    const detail = Array.isArray(body.detail) ? 'Invalid request.' : body.detail;
    throw {code: body.error_code || 'HTTP_' + response.status, message: body.message || detail || 'Request failed.'};
  }
  return response;
}

async function apiJson(path, options) {
  return (await api(path, options)).json();
}

function showView(name) {
  clearNotices();
  $('offer-detail').hidden = true;
  $('application-detail').hidden = true;
  for (const panel of document.querySelectorAll('[data-view-panel]')) {
    panel.hidden = panel.dataset.viewPanel !== name;
  }
  for (const tab of document.querySelectorAll('button.tab')) {
    tab.setAttribute('aria-current', tab.dataset.view === name ? 'true' : 'false');
  }
  if (name === 'offers') loadOffers().catch(showError);
  if (name === 'tracker') loadTracker().catch(showError);
}

function describeProvenance(entry) {
  if (!entry || entry.status === 'unknown') return 'unknown (not present in source)';
  if (entry.status === 'rejected') return 'rejected: ' + entry.reason;
  return 'source characters ' + entry.start + '–' + entry.end;
}

function definitionList(pairs) {
  const list = el('dl');
  for (const [term, value] of pairs) {
    list.append(el('dt', {text: term}));
    const definition = el('dd');
    definition.append(value instanceof Node ? value : valueOrUnknown(value));
    list.append(definition);
  }
  return list;
}

/* ---------- Import ---------- */

async function importPosting() {
  clearNotices();
  $('import-result').hidden = true;
  const file = $('posting-file').files[0];
  const text = $('posting-text').value;
  if (file && text.trim()) return showError({message: 'Choose either a file or pasted text, not both.'});
  if (!file && !text.trim()) return showError({message: 'Provide posting text or choose a file.'});
  const query = new URLSearchParams();
  const label = $('source-ref').value.trim() || (file ? file.name : 'pasted-text');
  query.set('source_ref', label);
  for (const [field, id] of [['provider', 'provider'], ['board', 'board'], ['source_id', 'source-id']]) {
    const value = $(id).value.trim();
    if (value) query.set(field, value);
  }
  try {
    const response = await api('/api/imports?' + query.toString(), {
      method: 'POST',
      headers: {'Content-Type': 'text/plain; charset=utf-8'},
      body: file ? file : new Blob([text], {type: 'text/plain; charset=utf-8'}),
    });
    renderImportResult(await response.json());
  } catch (error) {
    showError(error);
  }
}

function renderImportResult(result) {
  const labels = {
    created: 'New offer created (revision 1).',
    revision_created: 'Source changed: new revision ' + result.revision_number + ' recorded.',
    unchanged: 'Identical to the current revision: nothing new stored.',
  };
  const panel = $('import-result');
  clear(panel);
  panel.className = 'panel';
  panel.append(
    el('h3', {text: labels[result.outcome] || result.outcome}),
    definitionList([
      ['Outcome', result.outcome],
      ['Offer ID', result.offer_id],
      ['Revision', result.revision_number],
      ['Source SHA-256', el('span', {className: 'hash', text: result.content_sha256})],
      ['Identity', result.identity.kind + ': ' + [result.identity.provider, result.identity.board, result.identity.external_id].join(' / ')],
    ]),
  );
  if (result.duplicate_suggestions.length) {
    panel.append(el('p', {className: 'note', text: 'Possible duplicates (no merge was performed):'}));
    panel.append(suggestionList(result.duplicate_suggestions));
  }
  panel.append(el('button', {type: 'button', id: 'open-imported-offer', text: 'Open offer', onclick: () => openOffer(result.offer_id)}));
  panel.hidden = false;
}

function suggestionList(suggestions) {
  const list = el('ul', {id: 'duplicate-suggestions'});
  for (const item of suggestions) {
    list.append(el('li', {},
      el('span', {text: (item.other_title || 'unknown title') + ' — ' + (item.other_company || 'unknown company') + ' (score ' + item.score + '; ' + item.reason + ') '}),
      el('button', {type: 'button', text: 'Open', onclick: () => openOffer(item.other_offer_id)})));
  }
  return list;
}

/* ---------- Offers ---------- */

async function loadOffers() {
  const offers = await apiJson('/api/offers');
  const body = $('offers-table').querySelector('tbody');
  clear(body);
  $('offers-empty').hidden = offers.length > 0;
  for (const offer of offers) {
    const row = el('tr', {'data-offer-id': offer.id});
    row.append(
      el('td', {}, valueOrUnknown(offer.title)),
      el('td', {}, valueOrUnknown(offer.company)),
      el('td', {}, valueOrUnknown(offer.locations && offer.locations.join('; '))),
      el('td', {}, valueOrUnknown(offer.contract)),
      el('td', {text: 'R' + offer.revision_number}),
      el('td', {text: offer.application_id ? 'yes' : 'no'}),
      el('td', {text: String(offer.suggestion_count)}),
      el('td', {}, el('button', {type: 'button', className: 'open-offer', text: 'Open', onclick: () => openOffer(offer.id)})),
    );
    body.append(row);
  }
}

async function openOffer(offerId) {
  try {
    showView('offers');
    renderOfferDetail(await apiJson('/api/offers/' + encodeURIComponent(offerId)));
  } catch (error) {
    showError(error);
  }
}

function renderOfferDetail(offer) {
  const panel = $('offer-detail');
  clear(panel);
  panel.className = 'panel';
  const current = offer.revisions[offer.revisions.length - 1];
  const fields = current.fields;
  const provenance = current.provenance.fields;
  panel.append(el('h3', {text: fields.title || 'Untitled offer'}));
  panel.append(definitionList([
    ['Offer ID', offer.id],
    ['Identity', offer.identity_kind + ': ' + [offer.provider, offer.board, offer.external_id].join(' / ')],
    ['Current revision', 'R' + current.revision_number],
  ]));

  const table = el('table', {id: 'offer-fields'});
  table.append(el('thead', {}, el('tr', {}, el('th', {text: 'Field'}), el('th', {text: 'Value'}), el('th', {text: 'Provenance'}))));
  const tbody = el('tbody');
  const rows = [
    ['Title', fields.title, 'title'],
    ['Company', fields.company, 'company'],
    ['Locations', fields.locations && fields.locations.join('; '), 'locations'],
    ['Contract', fields.contract, 'contract'],
    ['Salary (as written)', fields.salary_raw_text, 'salary_raw_text'],
    ['Application URL', fields.apply_url, 'apply_url'],
    ['Description', fields.description, 'description'],
  ];
  for (const [label, value, key] of rows) {
    tbody.append(el('tr', {'data-field': key},
      el('td', {text: label}), el('td', {}, valueOrUnknown(value)), el('td', {text: describeProvenance(provenance[key])})));
  }
  table.append(tbody);
  panel.append(table);

  panel.append(el('h3', {text: 'Revisions'}));
  const revisionList = el('ul', {id: 'revision-list'});
  for (const revision of offer.revisions) {
    revisionList.append(el('li', {'data-revision': String(revision.revision_number)},
      el('span', {text: 'R' + revision.revision_number + ' · ' + revision.snapshot.retrieved_at + ' · ' + revision.snapshot.source_ref + ' · '}),
      el('span', {className: 'hash', text: revision.snapshot.content_sha256}),
      document.createTextNode(' '),
      el('button', {type: 'button', className: 'view-source', text: 'View source', onclick: () => viewSource(revision.snapshot.id)})));
  }
  panel.append(revisionList);
  panel.append(el('pre', {id: 'source-view', hidden: ''}));

  if (offer.duplicate_suggestions.length) {
    panel.append(el('h3', {text: 'Possible duplicates (suggestions only)'}));
    panel.append(suggestionList(offer.duplicate_suggestions));
  }

  panel.append(el('h3', {text: 'Application'}));
  if (offer.application) {
    panel.append(el('p', {id: 'application-exists', text: 'Application exists, stage ' + offer.application.stage + '. '}));
    panel.append(el('button', {type: 'button', text: 'Open in tracker', onclick: () => openApplication(offer.application.id)}));
  } else {
    panel.append(el('p', {className: 'note', text: 'Importing an offer does not create an application.'}));
    panel.append(el('button', {type: 'button', id: 'create-application', className: 'primary', text: 'Create application',
      onclick: () => createApplication(offer.id)}));
  }
  panel.hidden = false;
}

async function viewSource(snapshotId) {
  try {
    const response = await api('/api/snapshots/' + encodeURIComponent(snapshotId) + '/content');
    const view = $('source-view');
    view.textContent = await response.text();
    view.hidden = false;
  } catch (error) {
    showError(error);
  }
}

async function createApplication(offerId) {
  try {
    const application = await apiJson('/api/applications', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({offer_id: offerId}),
    });
    await openApplication(application.id);
    showMessage('Application created in stage ' + application.stage + '.');
  } catch (error) {
    showError(error);
  }
}

/* ---------- Tracker ---------- */

async function loadTracker() {
  const applications = await apiJson('/api/applications');
  const body = $('tracker-table').querySelector('tbody');
  clear(body);
  $('tracker-empty').hidden = applications.length > 0;
  for (const application of applications) {
    body.append(el('tr', {'data-application-id': application.id},
      el('td', {}, valueOrUnknown(application.title)),
      el('td', {}, valueOrUnknown(application.company)),
      el('td', {className: 'stage', text: application.stage}),
      el('td', {text: String(application.version)}),
      el('td', {text: 'R' + application.offer_revision_number}),
      el('td', {text: application.created_at}),
      el('td', {text: application.dossier_path}),
      el('td', {}, el('button', {type: 'button', className: 'open-application', text: 'Details', onclick: () => openApplication(application.id)}))));
  }
}

async function openApplication(applicationId) {
  try {
    showView('tracker');
    renderApplicationDetail(await apiJson('/api/applications/' + encodeURIComponent(applicationId)));
  } catch (error) {
    showError(error);
  }
}

function renderApplicationDetail(application) {
  const panel = $('application-detail');
  clear(panel);
  panel.className = 'panel';
  panel.append(
    el('h3', {text: (application.title || 'Untitled offer') + ' — ' + (application.company || 'unknown company')}),
    definitionList([
      ['Application ID', application.id],
      ['Stage', el('strong', {id: 'application-stage', text: application.stage})],
      ['Version', String(application.version)],
      ['Recruiter status', application.recruiter_status],
      ['Manifest SHA-256', el('span', {className: 'hash', text: application.manifest_sha256})],
    ]));

  const select = el('select', {id: 'transition-stage'});
  for (const stage of STAGE_CHOICES) {
    if (stage !== application.stage) select.append(el('option', {value: stage, text: stage}));
  }
  panel.append(
    el('h3', {text: 'Update status'}),
    el('label', {for: 'transition-stage', text: 'New stage'}), select,
    el('label', {for: 'transition-reason', text: 'Reason (required)'}),
    el('input', {type: 'text', id: 'transition-reason', maxlength: '500'}),
    el('button', {type: 'button', id: 'transition-button', className: 'primary', text: 'Update status',
      onclick: () => submitTransition(application)}),
  );

  panel.append(el('h3', {text: 'History'}));
  const history = el('ol', {id: 'event-list'});
  for (const event of application.events) {
    history.append(el('li', {text: event.created_at + ' · ' + (event.from_stage || '∅') + ' → ' + event.to_stage + ' · ' + event.actor + ' · ' + event.reason}));
  }
  panel.append(history);
  panel.hidden = false;
}

async function submitTransition(application) {
  try {
    const updated = await apiJson('/api/applications/' + encodeURIComponent(application.id) + '/transitions', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        to_stage: $('transition-stage').value,
        reason: $('transition-reason').value,
        expected_version: application.version,
      }),
    });
    await loadTracker();
    renderApplicationDetail(updated);
    showMessage('Stage updated to ' + updated.stage + '.');
  } catch (error) {
    showError(error);
  }
}

/* ---------- Boot ---------- */

fetch('/api/system/status', {cache: 'no-store'})
  .then((response) => {
    if (!response.ok) throw Error('HTTP ' + response.status);
    return response.json();
  })
  .then((status) => {
    $('state').textContent = 'API ' + status.version + ' · ' + status.database + ' OK · Marker: ' + (status.marker ?? 'none');
  })
  .catch(() => { $('state').textContent = 'API unavailable'; });

for (const tab of document.querySelectorAll('button.tab')) {
  tab.addEventListener('click', () => showView(tab.dataset.view));
}
$('import-button').addEventListener('click', importPosting);
showView('import');
