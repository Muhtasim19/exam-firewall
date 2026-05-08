// Auto refresh - preserves sort state via URL hash
setTimeout(function () {
    const hash = window.location.hash;
    if (hash) {
        window.location.href = window.location.pathname + hash;
    } else {
        window.location.reload();
    }
}, 10000);

// Confirm actions
document.addEventListener("DOMContentLoaded", function () {
    const blockButtons = document.querySelectorAll("form[action*='block']");
    blockButtons.forEach(btn => {
        btn.addEventListener("submit", function (e) {
            if (!confirm("Are you sure you want to block this device?")) {
                e.preventDefault();
            }
        });
    });

    const disableExam = document.querySelector("form[action*='exam/off']");
    if (disableExam) {
        disableExam.addEventListener("submit", function (e) {
            if (!confirm("Disable Exam Mode?")) {
                e.preventDefault();
            }
        });
    }
});
