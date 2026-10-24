(function() {
    const dialog = document.getElementById('appDialog');
    if (!dialog) return;

    const title = document.getElementById('appDialogTitle');
    const message = document.getElementById('appDialogMessage');
    const detail = document.getElementById('appDialogDetail');
    const confirmButton = document.getElementById('appDialogConfirm');
    const cancelButton = document.getElementById('appDialogCancel');
    const icon = document.getElementById('appDialogIcon');
    const queue = [];
    let activeRequest = null;

    function presentNext() {
        if (activeRequest || queue.length === 0) return;
        activeRequest = queue.shift();
        title.textContent = activeRequest.title || (activeRequest.confirm ? '请确认操作' : '提示');
        message.textContent = activeRequest.message;
        detail.textContent = activeRequest.detail || '';
        detail.hidden = !activeRequest.detail;
        dialog.classList.toggle('app-dialog-confirm', activeRequest.confirm);
        dialog.classList.toggle('app-dialog-warning', activeRequest.variant === 'warning');
        icon.innerHTML = activeRequest.confirm
            ? '<i class="fas fa-question" aria-hidden="true"></i>'
            : activeRequest.variant === 'warning'
                ? '<i class="fas fa-exclamation" aria-hidden="true"></i>'
                : '<i class="fas fa-check" aria-hidden="true"></i>';
        cancelButton.hidden = !activeRequest.confirm;
        confirmButton.textContent = activeRequest.confirm ? (activeRequest.confirmText || '确认') : '知道了';
        dialog.showModal();
    }

    function requestDialog(options) {
        return new Promise(resolve => {
            queue.push({...options, resolve});
            presentNext();
        });
    }

    function finishDialog(result) {
        if (!activeRequest) return;
        const request = activeRequest;
        activeRequest = null;
        dialog.close();
        request.resolve(result);
        queueMicrotask(presentNext);
    }

    confirmButton.addEventListener('click', () => finishDialog(true));
    cancelButton.addEventListener('click', () => finishDialog(false));
    dialog.addEventListener('cancel', event => {
        event.preventDefault();
        finishDialog(false);
    });
    dialog.addEventListener('click', event => {
        if (event.target === dialog) finishDialog(false);
    });

    window.showAppDialog = requestDialog;
    window.showAppConfirm = function(text, options = {}) {
        return requestDialog({...options, message: String(text), confirm: true});
    };
    window.alert = function(text) {
        const messageText = String(text);
        const warning = /错误|失败|不正确|不能为空|不能|请先|至少/.test(messageText);
        return requestDialog({
            message: messageText,
            title: warning ? '请检查后重试' : '操作成功',
            variant: warning ? 'warning' : 'success'
        });
    };
})();
