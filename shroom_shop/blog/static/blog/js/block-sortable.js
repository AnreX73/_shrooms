// blog/static/blog/js/block-sortable.js
function getCsrfToken() {
    return document.querySelector('meta[name=csrf-token]').content;
}
document.addEventListener('DOMContentLoaded', () => {
    const container = document.getElementById('blocks-container');
    if (!container) return;

    new Sortable(container, {
        handle: '.drag-handle',
        animation: 150,
        onEnd: async () => {
            const ids = [...container.querySelectorAll('.block-row')]
                .map(el => el.dataset.blockId);

            const params = new URLSearchParams();
            ids.forEach(id => params.append('block_id', id));

            await fetch('/blog/blocks/reorder/', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getCsrfToken(),
                    'Content-Type': 'application/x-www-form-urlencoded',
                },
                body: params,
            });
        },
    });
});