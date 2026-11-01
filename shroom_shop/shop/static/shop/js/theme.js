/* Переключение светлой и тёмной темы.
   По умолчанию используется системная настройка, ручной выбор
   запоминается в localStorage и имеет приоритет. */
(function () {
    var STORAGE_KEY = 'shroom-theme';
    var root = document.documentElement;
    var media = window.matchMedia ? window.matchMedia('(prefers-color-scheme: dark)') : null;

    function readStored() {
        try {
            var value = window.localStorage.getItem(STORAGE_KEY);
            return value === 'light' || value === 'dark' ? value : null;
        } catch (error) {
            return null;
        }
    }

    function systemTheme() {
        return media && media.matches ? 'dark' : 'light';
    }

    function currentTheme() {
        return readStored() || systemTheme();
    }

    function updateButtons(theme) {
        var buttons = document.querySelectorAll('[data-theme-toggle]');
        var nextTitle = theme === 'dark' ? 'Светлая тема' : 'Тёмная тема';
        var nextLabel = theme === 'dark' ? 'Включить светлую тему' : 'Включить тёмную тему';

        for (var i = 0; i < buttons.length; i += 1) {
            buttons[i].setAttribute('aria-pressed', theme === 'dark' ? 'true' : 'false');
            buttons[i].setAttribute('aria-label', nextLabel);
            buttons[i].setAttribute('title', nextTitle);
        }
    }

    function applyTheme(theme) {
        root.setAttribute('data-theme', theme);
        root.style.colorScheme = theme;
        updateButtons(theme);
    }

    function toggleTheme() {
        var next = currentTheme() === 'dark' ? 'light' : 'dark';
        try {
            window.localStorage.setItem(STORAGE_KEY, next);
        } catch (error) {
            /* localStorage может быть недоступен — тема всё равно применится. */
        }
        applyTheme(next);
    }

    applyTheme(currentTheme());

    document.addEventListener('click', function (event) {
        var trigger = event.target.closest ? event.target.closest('[data-theme-toggle]') : null;
        if (!trigger) {
            return;
        }
        event.preventDefault();
        toggleTheme();
    });

    if (media) {
        var onSystemChange = function () {
            if (!readStored()) {
                applyTheme(systemTheme());
            }
        };
        if (media.addEventListener) {
            media.addEventListener('change', onSystemChange);
        } else if (media.addListener) {
            media.addListener(onSystemChange);
        }
    }

    document.addEventListener('DOMContentLoaded', function () {
        applyTheme(currentTheme());
    });
})();
