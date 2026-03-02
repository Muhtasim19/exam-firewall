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
// 🔥 Random Background Color Blast
function changeBackground() {
  const colors = [
    "#ff00cc", "#00ffee", "#ff6600",
    "#3333ff", "#00ff88", "#ff0066"
  ];
  const randomColor = colors[Math.floor(Math.random() * colors.length)];
  document.body.style.background = randomColor;
}

// 🎲 Add Random Table Row
function addRow() {
  const table = document.querySelector("table");
  const row = table.insertRow(-1);

  const cell1 = row.insertCell(0);
  const cell2 = row.insertCell(1);

  cell1.innerHTML = "🔥 Crazy " + Math.floor(Math.random() * 100);
  cell2.innerHTML = "⚡ Energy " + Math.floor(Math.random() * 1000);
}

// 💥 Crazy Click Explosion Effect
document.addEventListener("click", function(e) {
  const circle = document.createElement("div");
  circle.style.position = "absolute";
  circle.style.width = "20px";
  circle.style.height = "20px";
  circle.style.background = "white";
  circle.style.borderRadius = "50%";
  circle.style.left = e.pageX + "px";
  circle.style.top = e.pageY + "px";
  circle.style.pointerEvents = "none";
  circle.style.animation = "explode 0.6s ease-out forwards";

  document.body.appendChild(circle);

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
