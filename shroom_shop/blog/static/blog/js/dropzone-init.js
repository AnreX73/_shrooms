// blog/static/blog/js/dropzone-init.js

// Отключаем автосканирование — Dropzone не должен сам искать .dropzone на странице,
// потому что блоки появляются динамически через htmx, а не только при загрузке страницы
Dropzone.autoDiscover = false;

function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(';').shift();
}
function getCsrfToken() {
    return document.querySelector('meta[name=csrf-token]').content;
}

function initDropzone(el) {
    if (el.dropzone) return;

    const uploadUrl = el.dataset.uploadUrl;
    if (!uploadUrl) return;

    const isGallery = el.classList.contains('dropzone-gallery');
    const isShortVideo = el.classList.contains('dropzone-short-video');

    const dz = new Dropzone(el, {
        url: uploadUrl,
        paramName: 'file',
        maxFiles: isGallery ? null : 1,
        maxFilesize: isShortVideo ? 500 : 20,
        acceptedFiles: isShortVideo ? 'video/*' : 'image/*',
        previewsContainer: false, // своих превью Dropzone не рисует — рендерим сами из ответа сервера
        headers: { 'X-CSRFToken': getCsrfToken() },
    });

    dz.on('dragenter', () => el.classList.add('dz-drag-hover'));
    dz.on('dragleave', () => el.classList.remove('dz-drag-hover'));
    dz.on('drop', () => el.classList.remove('dz-drag-hover'));

    dz.on('uploadprogress', (file, progress) => {
        // если хотите единый прогресс-бар как в dashboard-версии — раскомментируйте и добавьте разметку
        // const fill = el.parentElement.querySelector('.upload-progress__fill');
        // if (fill) fill.style.width = progress + '%';
    });

    dz.on('success', (file, response) => {
    const targetId = el.dataset.target;
    if (!targetId) return;

    if (isGallery) {
        const container = document.getElementById(targetId);
        if (container) container.insertAdjacentHTML('beforeend', response);
    } else {
        // single_image и short_video — полностью заменяем контейнер новым HTML
        const target = document.getElementById(targetId);
        if (target) {
            target.outerHTML = response;
            if (isShortVideo) {
                const newContainer = document.getElementById(targetId);
                if (newContainer) pollVideoStatus(newContainer);
            }
        }
    }
});

    dz.on('error', (file, message, xhr) => {
    console.error('Dropzone error:', message);
    if (xhr) {
        console.error('Status:', xhr.status);
        console.error('Response:', xhr.responseText);
    }
    alert('Не удалось загрузить файл. Попробуйте ещё раз.');
});
}

function pollVideoStatus(container) {
    const blockMatch = container.id.match(/video-status-(\d+)/);
    if (!blockMatch) return;
    const blockId = blockMatch[1];

    const interval = setInterval(async () => {
        const res = await fetch(`/blog/blocks/${blockId}/video-status/`);
        if (!res.ok) return;
        const html = await res.text();
        const current = document.getElementById(`video-status-${blockId}`);
        if (!current) {
            clearInterval(interval); // блок уже удалён со страницы
            return;
        }
        current.outerHTML = html;

        // если статус финальный (ready/failed) — прекращаем опрос
        if (html.includes('data-status="ready"') || html.includes('data-status="failed"')) {
            clearInterval(interval);
        }
    }, 3000);
}

// инициализация всех dropzone-элементов, которые уже есть на странице при первой загрузке
function initAllDropzones(root = document) {
    root.querySelectorAll('.dropzone-image, .dropzone-gallery, .dropzone-short-video')
        .forEach(initDropzone);
}

document.addEventListener('DOMContentLoaded', () => initAllDropzones());

// после каждой htmx-подмены DOM (новый блок, смена типа блока и т.д.) — инициализируем заново
document.body.addEventListener('htmx:load', (evt) => {
    initAllDropzones(evt.detail.elt);
});