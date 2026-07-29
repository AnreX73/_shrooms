const banner = document.getElementById('startBanner');
    const overlay = document.getElementById('bannerOverlay');
    const closeBtn = document.getElementById('bannerClose');

    // Показываем только если в этой сессии ещё не закрывали
    if (banner && !sessionStorage.getItem('startBannerShown')) {
        banner.style.display = 'block';
    }

    const hideBanner = () => {
        banner.style.display = 'none';
        sessionStorage.setItem('startBannerShown', 'true');
    };

    if (closeBtn) closeBtn.addEventListener('click', hideBanner);
    if (overlay) overlay.addEventListener('click', hideBanner);


document.addEventListener('DOMContentLoaded', function () {
    // SWIPER
    const galleryThumbs = new Swiper('.gallery-thumbs', {
        spaceBetween: 10,
        slidesPerView: 4,
        freeMode: true,
        watchSlidesProgress: true,
        slideToClickedSlide: true,
        direction: 'horizontal', // база — мобильный вариант
        breakpoints: {
            481: {
                direction: 'vertical', // с 769px переключаем в колонку
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
        loopedSlides: galleryThumbs.slides.length, // чтобы зациклить все
    });

    // Пересчитать размеры после полной загрузки картинок (у тебя loading="lazy")
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

    // Модальное окно на cтранице товара
    const modal = document.getElementById('detailsModal');
    const openBtn = document.getElementById('openDetailsModal');
    const closeBtn = document.getElementById('closeDetailsModal');
    const modalOverlay = document.getElementById('detailsModalOverlay');

    openBtn?.addEventListener('click', () => modal.classList.add('active'));
    closeBtn?.addEventListener('click', () => modal.classList.remove('active'));
    modalOverlay?.addEventListener('click', () => modal.classList.remove('active'));
    modal?.addEventListener('click', (e) => {
        if (e.target === modal) modal.classList.remove('active');
    });
});



