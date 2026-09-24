document.addEventListener("click", function (event) {
    var button = event.target.closest(".password-toggle");
    if (!button) {
        return;
    }

    var input = document.getElementById(button.dataset.target);
    if (!input) {
        return;
    }

    var show = input.type === "password";
    input.type = show ? "text" : "password";
    button.textContent = show ? "隱藏" : "顯示";
    button.setAttribute("aria-label", show ? "隱藏密碼" : "顯示密碼");
});
