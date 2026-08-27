
document.addEventListener('alpine:init', () => {
    Alpine.data('richTextField', (blockId) => ({
        toolbarVisible: false,
        toolbarTop: 0,
        toolbarLeft: 0,
        savedRange: null,

        init() {
            document.addEventListener('selectionchange', () => this.updateToolbar());
        },

        updateToolbar() {
            const sel = window.getSelection();
            const editable = this.$refs.editable;
            if (!editable || sel.rangeCount === 0 || sel.isCollapsed
                || !editable.contains(sel.anchorNode)) {
                return; // не трогаем toolbarVisible здесь принудительно в false —
                        // иначе он гаснет в момент клика по пикеру
            }
            this.savedRange = sel.getRangeAt(0).cloneRange();
            const rect = this.savedRange.getBoundingClientRect();
            const parentRect = editable.getBoundingClientRect();
            this.toolbarTop = rect.top - parentRect.top - 40;
            this.toolbarLeft = rect.left - parentRect.left;
            this.toolbarVisible = true;
        },

        restoreSelection() {
            if (!this.savedRange) return;
            const sel = window.getSelection();
            sel.removeAllRanges();
            sel.addRange(this.savedRange);
        },

        bold() {
            this.$refs.editable.focus();
            this.restoreSelection();
            document.execCommand('bold');
        },

        color(value) {
            this.$refs.editable.focus();
            this.restoreSelection();
            document.execCommand('foreColor', false, value);
            this.toolbarVisible = false;
        },

        handleFocusOut(event) {
        const wrapper = event.currentTarget;
        // ждём тик, пока браузер не установит фокус на новый элемент,
        // и только потом проверяем — остались ли мы внутри обёртки
        setTimeout(() => {
            if (wrapper.contains(document.activeElement)) return; // фокус внутри — не сохраняем

            this.toolbarVisible = false;
            this.$refs.hidden.value = this.$refs.editable.innerHTML;
            htmx.trigger(this.$refs.hidden, 'rt:blur');
        }, 0);
    }
    }));
});



document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('.post-gallery').forEach(function (el) {
        new Splide(el, {
            type: 'loop',
            perPage: 1,
            arrows: true,
            pagination: true,
            gap: '1rem',
        }).mount();
    });
});