const form = document.querySelector<HTMLFormElement>('#submission-form')!;
const api = form.dataset.api!;
const nameInput = document.querySelector<HTMLInputElement>('#addon-name')!;
const author = document.querySelector<HTMLInputElement>('#author-name')!;
const description = document.querySelector<HTMLTextAreaElement>('#addon-description')!;
const submitButton = document.querySelector<HTMLButtonElement>('#submit-button')!;
const error = document.querySelector<HTMLElement>('#form-error')!;
const statusPanel = document.querySelector<HTMLElement>('#submission-status')!;
const statusError = document.querySelector<HTMLElement>('#status-error')!;
const checkButton = document.querySelector<HTMLButtonElement>('#check-status')!;
const receipt = document.querySelector<HTMLInputElement>('#submission-receipt')!;
const publishedLink = document.querySelector<HTMLAnchorElement>('#published-link')!;
const storageKey = `stremio-addon-submission-receipt:${api}`;
let challenge = '';
let timer: ReturnType<typeof setTimeout> | undefined;
let pollingStarted = 0;
let checking = false;

async function request(path: string, payload: unknown) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 20000);
  try {
    const response = await fetch(`${api}/${path}`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload), signal: controller.signal, credentials: 'omit',
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'The service is temporarily unavailable. Please try again.');
    document.querySelector<HTMLElement>('#preview-notice')!.hidden = !result.preview;
    return result;
  } finally {
    clearTimeout(timeout);
  }
}

function showError(target: HTMLElement, failure: unknown) {
  target.textContent = failure instanceof Error && failure.name !== 'AbortError'
    ? failure.message : 'The service could not be reached. Please try again shortly.';
  target.hidden = false;
}

async function prepare() {
  try {
    const result = await request('challenge', {});
    challenge = result.challenge;
    error.hidden = true;
  } catch (failure) {
    showError(error, failure);
  } finally {
    submitButton.disabled = false;
  }
}

function updatePreview() {
  document.querySelector<HTMLElement>('#preview-name')!.textContent = nameInput.value.trim() || 'Your addon name';
  const firstLetter = Array.from(nameInput.value.trim())[0] || 'A';
  document.querySelector<HTMLElement>('#preview-initial')!.textContent = firstLetter.toUpperCase();
  document.querySelector<HTMLElement>('#preview-author')!.textContent = `By ${author.value.trim() || 'Anonymous'}`;
  document.querySelector<HTMLElement>('#preview-description')!.textContent = description.value.trim() || 'A clear, useful description helps people discover what makes your addon different.';
  document.querySelector<HTMLElement>('#description-count')!.textContent = `${description.value.length.toLocaleString()} / 3,000`;
}
[nameInput, author, description].forEach(field => field.addEventListener('input', updatePreview));

function displayStatus(result: { state: string; message: string; url?: string }) {
  const labels: Record<string, string> = {
    queued: 'Submission received', reviewing: 'Review in progress', retrying: 'Review will retry',
    rejected: 'Submission not approved', needs_attention: 'Site owner review needed',
    deploying: 'Approved · publication in progress', published: 'Your addon is live', approved_preview: 'Preview review passed',
  };
  statusPanel.hidden = false;
  document.querySelector<HTMLElement>('#status-heading')!.textContent = labels[result.state] || 'Submission status';
  document.querySelector<HTMLElement>('#status-message')!.textContent = result.message;
  publishedLink.hidden = true;
  if (result.state === 'published' && typeof result.url === 'string') {
    try {
      const url = new URL(result.url);
      if (url.origin === 'https://stremioaddonmanager.org' && /^\/blog\/addons\/community-[a-z0-9-]+$/.test(url.pathname)) {
        publishedLink.href = url.href;
        publishedLink.hidden = false;
      }
    } catch {}
  }
  clearTimeout(timer);
  if (['queued', 'reviewing', 'retrying', 'deploying'].includes(result.state) && Date.now() - pollingStarted < 600000) {
    timer = setTimeout(checkStatus, 15000);
  }
}

async function checkStatus() {
  if (!receipt.value || checking) return;
  checking = true;
  checkButton.disabled = true;
  statusError.hidden = true;
  const requestedReceipt = receipt.value;
  try {
    const result = await request('status', { ticket: requestedReceipt });
    if (receipt.value === requestedReceipt) displayStatus(result);
  } catch (failure) {
    showError(statusError, failure);
  } finally {
    checking = false;
    checkButton.disabled = false;
  }
}

form.addEventListener('submit', async event => {
  event.preventDefault();
  if (!form.reportValidity()) return;
  error.hidden = true;
  if (!challenge) { await prepare(); return; }
  submitButton.disabled = true;
  submitButton.querySelector('span')!.textContent = 'Sending your submission…';
  try {
    const values = new FormData(form);
    const result = await request('submit', { ...Object.fromEntries(values), consent: values.has('consent'), challenge });
    receipt.value = result.ticket;
    try { localStorage.setItem(storageKey, result.ticket); } catch {}
    pollingStarted = Date.now();
    displayStatus(result);
    statusPanel.scrollIntoView({ behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth', block: 'center' });
    submitButton.querySelector('span')!.textContent = 'Submission received';
  } catch (failure) {
    showError(error, failure);
    submitButton.disabled = false;
    submitButton.querySelector('span')!.textContent = 'Submit for review';
    if (failure instanceof Error && failure.message.includes('form session expired')) challenge = '';
  }
});
checkButton.addEventListener('click', () => { pollingStarted = Date.now(); checkStatus(); });
document.querySelector('#copy-receipt')!.addEventListener('click', async event => {
  const button = event.currentTarget as HTMLButtonElement;
  try { await navigator.clipboard.writeText(receipt.value); button.textContent = 'Copied'; }
  catch { receipt.focus(); receipt.select(); }
});
document.querySelector('#receipt-form')!.addEventListener('submit', event => {
  event.preventDefault();
  if (checking) return;
  clearTimeout(timer);
  receipt.value = document.querySelector<HTMLInputElement>('#saved-receipt')!.value.trim();
  statusPanel.hidden = false;
  publishedLink.hidden = true;
  document.querySelector<HTMLElement>('#status-heading')!.textContent = 'Checking receipt';
  document.querySelector<HTMLElement>('#status-message')!.textContent = '';
  pollingStarted = Date.now();
  checkStatus();
});
try {
  const saved = localStorage.getItem(storageKey);
  if (saved && /^[a-f0-9]{64}$/.test(saved)) {
    receipt.value = saved;
    document.querySelector<HTMLInputElement>('#saved-receipt')!.value = saved;
    pollingStarted = Date.now();
    checkStatus();
  }
} catch {}
updatePreview();
prepare();
