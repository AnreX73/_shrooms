// ── CSRF: единая точка получения токена ───────────────────────────────────────
// Имя cookie CSRF задаётся в settings.py (CSRF_COOKIE_NAME), поэтому читать
// «csrftoken» напрямую нельзя. Приоритет — токен из разметки (meta/input).
function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(';').shift();
}

function getCsrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    if (meta && meta.content) return meta.content;

    const input = document.querySelector('[name=csrfmiddlewaretoken]');
    if (input && input.value) return input.value;

    return getCookie('csrftoken_shroomsshop') || getCookie('csrftoken') || '';
}

document.addEventListener('DOMContentLoaded', function() {
    // ── 1. СТАРТОВЫЙ БАННЕР ─────────────────────────────────────────────────────
    const banner = document.getElementById('startBanner');
    
    if (!banner) {
        console.warn('⚠️ Элемент #startBanner не найден в DOM.');
    } else {
        const overlay = document.getElementById('bannerOverlay');
        const closeBtn = document.getElementById('bannerClose');

        const urlParams = new URLSearchParams(window.location.search);
        const forceShow = urlParams.get('show_banner') === '1';
        const isShown = sessionStorage.getItem('startBannerShown');

        console.log('🔍 Отладка баннера:', { 
            forceShow: forceShow, 
            isShownInStorage: isShown, 
            shouldShow: forceShow || !isShown 
        });

        if (forceShow || !isShown) {
            banner.style.display = 'block';
            
            if (forceShow) {
                urlParams.delete('show_banner');
                const newUrl = urlParams.toString() 
                    ? `${window.location.pathname}?${urlParams.toString()}`
                    : window.location.pathname;
                window.history.replaceState({}, document.title, newUrl);
                console.log('✅ Баннер показан принудительно, параметр удалён из URL');
            }
        }

        const hideBanner = () => {
            banner.style.display = 'none';
            sessionStorage.setItem('startBannerShown', 'true');
            console.log('🚪 Баннер закрыт пользователем');
        };

        if (closeBtn) {
            closeBtn.addEventListener('click', hideBanner);
            console.log('✅ Кнопка закрытия (#bannerClose) найдена и активна');
        } else {
            console.error('❌ ОШИБКА: Кнопка с id="bannerClose" НЕ НАЙДЕНА в HTML!');
        }

        if (overlay) {
            overlay.addEventListener('click', hideBanner);
        }
    }

    // ── 2. SWIPER ГАЛЕРЕЯ ───────────────────────────────────────────────────────
    const galleryThumbs = new Swiper('.gallery-thumbs', {
        spaceBetween: 10,
        slidesPerView: 4,
        freeMode: true,
        watchSlidesProgress: true,
        slideToClickedSlide: true,
        direction: 'horizontal',
        breakpoints: {
            481: {
                direction: 'vertical',
                slidesPerView: 4,
            }
        }
    });

    const galleryMain = new Swiper('.gallery-main', {
        spaceBetween: 10,
        navigation: {
            nextEl: '.gallery-main .swiper-button-next',
            prevEl: '.gallery-main .swiper-button-prev',
        },
        thumbs: {
            swiper: galleryThumbs,
        },
        loop: true,
        loopedSlides: galleryThumbs.slides.length,
    });

    window.addEventListener('load', () => {
        galleryThumbs.update();
        galleryMain.update();
    });

    // Кнопка избранного
    document.querySelectorAll('.favorite-btn').forEach(btn => {
        btn.addEventListener('click', function () {
            this.classList.toggle('active');
        });
    });

    // Модальное окно на странице товара
    const modal = document.getElementById('detailsModal');
    const openBtn = document.getElementById('openDetailsModal');
    const closeBtnModal = document.getElementById('closeDetailsModal'); // переименовал, чтобы не путать с closeBtn баннера
    const modalOverlay = document.getElementById('detailsModalOverlay');

    openBtn?.addEventListener('click', () => modal.classList.add('active'));
    closeBtnModal?.addEventListener('click', () => modal.classList.remove('active'));
    modalOverlay?.addEventListener('click', () => modal.classList.remove('active'));
    modal?.addEventListener('click', (e) => {
        if (e.target === modal) modal.classList.remove('active');
    });
});

// ── 3. МЕДИА-МЕНЕДЖЕР ТОВАРА ──────────────────────────────────────────────────
(function() {
    const mediaDropzone = document.getElementById('media-dropzone');
    if (!mediaDropzone) return;

    Dropzone.autoDiscover = false;

    const _urls = document.getElementById('js-urls').dataset;
    const CSRF_TOKEN = getCsrfToken();

    function buildUrl(template, id) {
        return template.replace('/0/', `/${id}/`);
    }

    const dz = new Dropzone('#media-dropzone', {
        url: _urls.upload,
        headers: { 'X-CSRFToken': CSRF_TOKEN },
        paramName: 'file',
        maxFilesize: 100,
        acceptedFiles: 'image/jpeg,image/png,image/webp,image/gif,video/mp4,video/quicktime,video/x-msvideo,video/webm',
        addRemoveLinks: false,
        previewsContainer: false,
        parallelUploads: 2,
        clickable: true,

        init() {
            const progressWrap = document.getElementById('upload-progress');
            const progressFill = document.getElementById('progress-fill');
            const progressText = document.getElementById('progress-text');

            this.on('uploadprogress', (file, progress) => {
                progressWrap.classList.remove('hidden');
                progressFill.style.width = progress + '%';
                progressText.textContent = `Загрузка: ${Math.round(progress)}%`;
            });

            this.on('success', (file, response) => {
                const empty = document.getElementById('empty-placeholder');
                if (empty) empty.remove();

                htmx.ajax(
                    'GET',
                    buildUrl(_urls.partialBase, response.id),
                    { target: '#media-grid', swap: 'beforeend' }
                );

                updateMediaCount(1);
                this.removeFile(file);
                progressWrap.classList.add('hidden');
                progressFill.style.width = '0%';
            });

            this.on('error', (file, msg, xhr) => {
                progressWrap.classList.add('hidden');
                progressFill.style.width = '0%';

                // HTML-страницу ошибки Django (403/500) в alert не показываем
                if (xhr && xhr.status === 403) {
                    console.error('403: CSRF-проверка не пройдена', xhr.responseText);
                    alert('Доступ запрещён (403). Обновите страницу и попробуйте снова.');
                } else if (typeof msg === 'string' && msg.trim().startsWith('<')) {
                    console.error('Ошибка загрузки:', msg);
                    alert('Не удалось загрузить файл: ошибка сервера. Подробности в консоли.');
                } else {
                    alert('Ошибка загрузки: ' + (typeof msg === 'string' ? msg : (msg && msg.error) || 'неизвестная ошибка'));
                }

                this.removeFile(file);
            });
        }
    });

    const grid = document.getElementById('media-grid');
    Sortable.create(grid, {
        animation: 200,
        handle: '.drag-handle',
        ghostClass: 'sortable-ghost',
        chosenClass: 'sortable-chosen',
        onEnd() {
            const ids = [...grid.querySelectorAll('[data-media-id]')]
                .map(el => parseInt(el.dataset.mediaId));
            fetch(_urls.reorder, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': CSRF_TOKEN,
                },
                body: JSON.stringify({ order: ids }),
            });
        }
    });

    window.deleteMedia = function(mediaId, btn) {
        if (!confirm('Удалить этот файл?')) return;
        fetch(buildUrl(_urls.deleteBase, mediaId), {
            method: 'POST',
            headers: { 'X-CSRFToken': CSRF_TOKEN },
        }).then(r => {
            if (r.ok) {
                btn.closest('.media-item').remove();
                updateMediaCount(-1);
                if (grid.querySelectorAll('.media-item').length === 0) {
                    grid.innerHTML = '<div class="media-empty" id="empty-placeholder">Пока нет файлов.</div>';
                }
            }
        });
    };

    function updateMediaCount(delta) {
        const el = document.getElementById('media-count');
        const next = (parseInt(el.textContent) || 0) + delta;
        const forms = ['файл', 'файла', 'файлов'];
        const n = Math.abs(next) % 100, n1 = n % 10;
        const form = (n > 10 && n < 20) ? forms[2]
                   : n1 === 1            ? forms[0]
                   : (n1 >= 2 && n1 <= 4) ? forms[1]
                   : forms[2];
        el.textContent = `${next} ${form}`;
    }
})();

// ── 4. МЕДИА К ОТЗЫВУ ─────────────────────────────────────────────────────────
(function() {
    const reviewDropzone = document.getElementById('review-dropzone');
    if (!reviewDropzone) return;

    Dropzone.autoDiscover = false;

    const _urls = document.getElementById('js-review-urls').dataset;
    const CSRF_TOKEN = getCsrfToken();

    function buildUrl(template, id) {
        return template.replace('/0/', `/${id}/`);
    }

    const grid = document.getElementById('review-media-grid');
    let photoCount = [...grid.querySelectorAll('[data-media-type="photo"]')].length;
    let videoCount = [...grid.querySelectorAll('[data-media-type="video"]')].length;

    function updateLimitCounters() {
        const pc = document.getElementById('photo-count');
        const vc = document.getElementById('video-count');
        if (pc) pc.textContent = photoCount;
        if (vc) vc.textContent = videoCount;
    }
    updateLimitCounters();

    const dz = new Dropzone('#review-dropzone', {
        url: _urls.upload,
        headers: { 'X-CSRFToken': CSRF_TOKEN },
        paramName: 'file',
        maxFilesize: 100,
        acceptedFiles: 'image/jpeg,image/png,image/webp,video/mp4,video/quicktime,video/x-msvideo',
        addRemoveLinks: false,
        previewsContainer: false,
        parallelUploads: 1,
        clickable: true,
        autoProcessQueue: true,
        dictDefaultMessage: '',
        dictFallbackMessage: '',
        dictFileTooBig: 'Файл слишком большой ({{filesize}}MB). Максимум {{maxFilesize}}MB.',
        dictInvalidFileType: 'Недопустимый тип файла.',
        dictResponseError: '',

        init() {
            const progressWrap = document.getElementById('upload-progress');
            const progressFill = document.getElementById('progress-fill');
            const progressText = document.getElementById('progress-text');

            this.on('uploadprogress', (file, progress) => {
                progressWrap.classList.remove('hidden');
                progressFill.style.width = progress + '%';
                progressText.textContent = `Загрузка: ${Math.round(progress)}%`;
            });

            this.on('success', (file, response) => {
                const empty = document.getElementById('review-empty');
                if (empty) empty.remove();

                htmx.ajax(
                    'GET',
                    buildUrl(_urls.partialBase, response.id),
                    { target: '#review-media-grid', swap: 'beforeend' }
                );

                if (response.media_type === 'photo') photoCount++;
                else videoCount++;
                updateLimitCounters();

                this.removeFile(file);
                progressWrap.classList.add('hidden');
                progressFill.style.width = '0%';
            });

            // ИСПРАВЛЕНО: убран задвоенный/сломанный блок this.on('error', ...)
            this.on('error', (file, msg) => {
                progressWrap.classList.add('hidden');
                const errMsg = typeof msg === 'string' ? msg : (msg.error || 'Ошибка загрузки');
                
                const errorBlock = document.getElementById('upload-error');
                const errorText = document.getElementById('upload-error-text');
                if (errorBlock && errorText) {
                    errorText.textContent = errMsg;
                    errorBlock.classList.remove('hidden');
                    setTimeout(() => errorBlock.classList.add('hidden'), 4000);
                }
                this.removeFile(file);
            });
        }
    });

    window.deleteReviewMedia = function(mediaId, btn) {
        if (!confirm('Удалить файл?')) return;
        fetch(buildUrl(_urls.deleteBase, mediaId), {
            method: 'POST',
            headers: { 'X-CSRFToken': CSRF_TOKEN },
        }).then(r => {
            if (r.ok) {
                const item = btn.closest('.media-item');
                if (item.dataset.mediaType === 'photo') photoCount--;
                else videoCount--;
                item.remove();
                updateLimitCounters();
            }
        });
    };
})();

// ── 5. HTMX КАТАЛОГ (ИСПРАВЛЕНО: убраны дубликаты) ────────────────────────────
document.body.addEventListener('htmx:beforeRequest', function(e) {
    if (e.detail.target.id === 'catalog-section') {
        document.querySelector('.products-grid')?.classList.add('loading');
    }
});

document.body.addEventListener('htmx:afterSwap', function(e) {
    if (e.detail.target.id === 'catalog-section') {
        setTimeout(() => {
            document.querySelectorAll('.product-card').forEach((card, i) => {
                card.style.animationDelay = `${i * 30}ms`;
                card.classList.add('card-enter');
            });
        }, 10);
    }
});

// ── 6. ФИЛЬТРЫ КАТАЛОГА (МОБИЛЬНЫЕ) ───────────────────────────────────────────
(function () {
    var panel = document.getElementById("catalog-filters");
    var toggle = document.getElementById("filters-toggle");
    var overlay = document.getElementById("filters-overlay");
    var closeBtn = document.getElementById("filters-close");
    var applyBtn = document.getElementById("filters-apply-mobile");

    if (!panel || !toggle) return;

    function openPanel() {
        panel.classList.add("is-open");
        overlay.classList.add("is-open");
        toggle.setAttribute("aria-expanded", "true");
        document.body.classList.add("no-scroll");
    }

    function closePanel() {
        panel.classList.remove("is-open");
        overlay.classList.remove("is-open");
        toggle.setAttribute("aria-expanded", "false");
        document.body.classList.remove("no-scroll");
    }

    toggle.addEventListener("click", openPanel);
    overlay.addEventListener("click", closePanel);
    closeBtn.addEventListener("click", closePanel);
    applyBtn.addEventListener("click", closePanel);

    document.addEventListener("keydown", function (e) {
        if (e.key === "Escape") closePanel();
    });

    document.body.addEventListener("htmx:afterSwap", function (e) {
        if (e.detail.target && e.detail.target.id === "catalog-results") {
            if (window.matchMedia("(max-width: 900px)").matches) {
                closePanel();
            }
        }
    });
})();