/**
 * VITALSYNC: User View Controller
 * Embeds the User Companion UI (user-ui) inside the Testing Lab
 * via an iframe. Reads VITE_USER_UI_URL for the target origin.
 * Falls back to localhost:3000 for local dev.
 */

const USER_UI_URL = import.meta.env.VITE_USER_UI_URL || 'http://localhost:3000';

const overlay   = document.getElementById('user-view-overlay');
const iframe    = document.getElementById('user-view-iframe');
const loading   = document.getElementById('user-view-loading');
const urlLabel  = document.getElementById('user-view-url-label');
const btnToggle = document.getElementById('btn-toggle-user-view');
const btnClose  = document.getElementById('btn-close-user-view');
const btnReload = document.getElementById('btn-user-view-reload');

let isOpen = false;
let iframeLoaded = false;

function openUserView() {
  if (!iframeLoaded) {
    loading.classList.remove('hidden');
    iframe.src = USER_UI_URL;
    urlLabel.textContent = USER_UI_URL.replace(/^https?:\/\//, '');
    iframe.onload = () => {
      loading.classList.add('hidden');
      iframeLoaded = true;
    };
  }
  overlay.classList.remove('hidden');
  // animate in
  requestAnimationFrame(() => overlay.classList.add('user-view-open'));
  btnToggle.setAttribute('aria-pressed', 'true');
  btnToggle.classList.add('active');
  isOpen = true;
  document.addEventListener('keydown', onEsc);
}

function closeUserView() {
  overlay.classList.remove('user-view-open');
  overlay.addEventListener('transitionend', () => {
    overlay.classList.add('hidden');
  }, { once: true });
  btnToggle.setAttribute('aria-pressed', 'false');
  btnToggle.classList.remove('active');
  isOpen = false;
  document.removeEventListener('keydown', onEsc);
}

function onEsc(e) {
  if (e.key === 'Escape') closeUserView();
}

btnToggle.addEventListener('click', () => {
  isOpen ? closeUserView() : openUserView();
});

btnClose.addEventListener('click', closeUserView);

btnReload.addEventListener('click', () => {
  iframeLoaded = false;
  loading.classList.remove('hidden');
  iframe.src = '';
  setTimeout(() => { iframe.src = USER_UI_URL; }, 50);
  iframe.onload = () => {
    loading.classList.add('hidden');
    iframeLoaded = true;
  };
});
