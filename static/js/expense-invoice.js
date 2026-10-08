// 新增費用：分攤成員勾選＋發票明細（日期／明細／金額／收據照片）可新增／刪除，並即時加總後帶入「金額」欄
// （使用者手動改過金額就不再覆蓋）。每列用流水號 key 對應欄位名稱，後端用 item_key 把同一列的欄位配在一起。
(function () {
    var form = document.querySelector('.expense-form');
    if (!form) return;

    var currency = document.currentScript ? document.currentScript.dataset.currency : '';
    var list = form.querySelector('[data-invoice-items]');
    var totalEl = form.querySelector('[data-invoice-total]');
    var amountInput = form.querySelector('input[name="amount"]');
    var expenseDateInput = form.querySelector('input[name="expense_date"]');
    var amountTouched = false;
    var nextKey = 0;

    function money(value) {
        return value.toLocaleString(undefined, { maximumFractionDigits: 2 });
    }

    function recalc() {
        var total = 0;
        list.querySelectorAll('.invoice-item').forEach(function (row) {
            total += parseFloat(row.querySelector('[data-item-amount]').value) || 0;
        });
        total = Math.round(total * 100) / 100;
        totalEl.textContent = currency + ' ' + money(total);
        if (!amountTouched) amountInput.value = total > 0 ? total : '';
        updateSplitPreview();
    }

    // 分攤成員：全選／只有我，並預覽每人要分攤多少
    var splitBox = form.querySelector('[data-split-members]');
    var splitChecks = splitBox ? splitBox.querySelectorAll('input[name="split_user_ids"]') : [];
    var splitPreview = splitBox ? splitBox.querySelector('[data-split-preview]') : null;

    function updateSplitPreview() {
        if (!splitPreview) return;
        var checked = [].filter.call(splitChecks, function (c) { return c.checked; });
        var amount = parseFloat(amountInput.value) || 0;
        if (!checked.length) splitPreview.textContent = '⚠️ 請至少勾選一位成員';
        else if (checked.length === 1 && checked[0].value === splitBox.dataset.me) splitPreview.textContent = '個人支出，不分攤';
        else splitPreview.textContent = checked.length + ' 人平分' + (amount ? '，每人約 ' + currency + ' ' + money(Math.floor(amount / checked.length * 100) / 100) : '');
        splitPreview.classList.toggle('warn', !checked.length);
    }

    if (splitBox) {
        splitBox.addEventListener('change', updateSplitPreview);
        splitBox.querySelector('[data-split-all]').addEventListener('click', function () {
            splitChecks.forEach(function (c) { c.checked = true; });
            updateSplitPreview();
        });
        splitBox.querySelector('[data-split-me]').addEventListener('click', function () {
            splitChecks.forEach(function (c) { c.checked = c.value === splitBox.dataset.me; });
            updateSplitPreview();
        });
        amountInput.addEventListener('input', updateSplitPreview);
        form.addEventListener('submit', function (event) {
            if (![].some.call(splitChecks, function (c) { return c.checked; })) {
                event.preventDefault();
                updateSplitPreview();
                splitBox.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
        });
    }

    function addRow() {
        var key = nextKey++;
        var row = document.createElement('div');
        row.className = 'invoice-item';
        row.innerHTML =
            '<input type="hidden" name="item_key" value="' + key + '">' +
            '<input type="date" name="item_date_' + key + '" aria-label="日期">' +
            '<input name="item_desc_' + key + '" maxlength="255" placeholder="例如 牛肉麵 x2" aria-label="明細">' +
            '<input type="number" name="item_amount_' + key + '" min="0" step="0.01" placeholder="0" aria-label="金額" data-item-amount>' +
            '<label class="invoice-file"><input type="file" name="item_receipt_' + key + '" accept="image/*,application/pdf"><span>📷 上傳照片</span></label>' +
            '<button type="button" class="invoice-remove" aria-label="刪除這列明細">✕</button>';
        // 日期預設帶入費用日期，方便一次填完
        if (expenseDateInput && expenseDateInput.value) row.querySelector('input[type="date"]').value = expenseDateInput.value;
        var fileInput = row.querySelector('input[type="file"]');
        fileInput.addEventListener('change', function () {
            var label = row.querySelector('.invoice-file span');
            var file = fileInput.files[0];
            label.textContent = file ? '✓ ' + file.name : '📷 上傳照片';
            row.querySelector('.invoice-file').classList.toggle('has-file', !!file);
        });
        row.querySelector('.invoice-remove').addEventListener('click', function () {
            row.remove();
            if (!list.children.length) addRow();
            recalc();
        });
        list.appendChild(row);
        return row;
    }

    list.addEventListener('input', recalc);
    amountInput.addEventListener('input', function () { amountTouched = amountInput.value !== ''; });
    form.querySelector('[data-add-invoice-item]').addEventListener('click', function () {
        addRow().querySelector('input[name^="item_desc_"]').focus();
    });
    addRow();
    updateSplitPreview();
})();
