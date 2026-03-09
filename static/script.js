// =========================
// AUTO REFRESH (10 seconds)
// =========================
setTimeout(function () {
    window.location.reload();
}, 10000);

// =========================
// CONFIRM ACTIONS
// =========================
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
