(function () {
    "use strict";

    var currentType = "member";
    var selected = {}; // id -> name
    var alertsShownFor = null; // serialized id list we've already alerted for

    var typeTabs = document.getElementById("signin-type-tabs");
    var searchInput = document.getElementById("signin-search");
    var resultsBox = document.getElementById("signin-search-results");
    var selectedBox = document.getElementById("signin-selected");
    var selectedEmpty = document.getElementById("signin-selected-empty");
    var detailsCard = document.getElementById("signin-details-card");
    var submitBtn = document.getElementById("signin-submit-btn");
    var form = document.getElementById("signin-form");
    var memberIdsFields = document.getElementById("signin-member-ids-fields");
    var directionField = document.getElementById("signin-direction-field");
    var notesField = document.getElementById("signin-notes-field");
    var notesInput = document.getElementById("signin-notes");
    var sigField = document.getElementById("signin-signature-field");
    var alertModal = document.getElementById("signin-alert-modal");
    var alertMessages = document.getElementById("signin-alert-messages");
    var alertDismiss = document.getElementById("signin-alert-dismiss");

    var direction = "IN";

    // ── Type tabs ──────────────────────────────────────────────────────────
    typeTabs.addEventListener("click", function (e) {
        var tab = e.target.closest(".type-tab");
        if (!tab) return;
        e.preventDefault();
        Array.prototype.forEach.call(typeTabs.querySelectorAll(".type-tab"), function (t) {
            t.classList.remove("active");
        });
        tab.classList.add("active");
        currentType = tab.dataset.type;
        resultsBox.innerHTML = "";
        resultsBox.style.display = "none";
    });

    // ── Search ─────────────────────────────────────────────────────────────
    var searchTimer = null;
    searchInput.addEventListener("input", function () {
        var q = searchInput.value.trim();
        clearTimeout(searchTimer);
        if (!q) {
            resultsBox.innerHTML = "";
            resultsBox.style.display = "none";
            return;
        }
        searchTimer = setTimeout(function () { runSearch(q); }, 200);
    });

    function runSearch(q) {
        fetch("/signin/search?type=" + encodeURIComponent(currentType) + "&q=" + encodeURIComponent(q))
            .then(function (r) { return r.json(); })
            .then(function (data) { renderResults(data.results || []); });
    }

    function renderResults(results) {
        resultsBox.innerHTML = "";
        if (!results.length) {
            resultsBox.style.display = "none";
            return;
        }
        results.forEach(function (r) {
            var item = document.createElement("div");
            item.className = "signin-search-result";
            item.textContent = r.name;
            item.addEventListener("click", function () {
                addSelected(r.id, r.name);
                searchInput.value = "";
                resultsBox.innerHTML = "";
                resultsBox.style.display = "none";
                searchInput.focus();
            });
            resultsBox.appendChild(item);
        });
        resultsBox.style.display = "block";
    }

    // ── Selected list ──────────────────────────────────────────────────────
    function addSelected(id, name) {
        selected[id] = name;
        renderSelected();
        fetchAlerts();
    }

    function removeSelected(id) {
        delete selected[id];
        renderSelected();
    }

    function renderSelected() {
        var ids = Object.keys(selected);
        selectedBox.innerHTML = "";
        if (!ids.length) {
            selectedBox.appendChild(selectedEmpty);
            detailsCard.style.display = "none";
            return;
        }
        ids.forEach(function (id) {
            var chip = document.createElement("span");
            chip.className = "signin-chip";
            chip.textContent = selected[id] + " ";
            var remove = document.createElement("a");
            remove.href = "#";
            remove.className = "signin-chip-remove";
            remove.textContent = "✕";
            remove.addEventListener("click", function (e) {
                e.preventDefault();
                removeSelected(id);
            });
            chip.appendChild(remove);
            selectedBox.appendChild(chip);
        });
        detailsCard.style.display = "block";
    }

    function fetchAlerts() {
        var ids = Object.keys(selected);
        if (!ids.length) return;
        var key = ids.slice().sort().join(",");
        if (key === alertsShownFor) return;
        fetch("/signin/alerts?member_ids=" + encodeURIComponent(ids.join(",")))
            .then(function (r) { return r.json(); })
            .then(function (data) {
                var alerts = data.alerts || [];
                if (!alerts.length) return;
                alertsShownFor = key;
                alertMessages.innerHTML = "";
                alerts.forEach(function (a) {
                    var p = document.createElement("p");
                    p.textContent = a.message;
                    alertMessages.appendChild(p);
                });
                alertModal.style.display = "flex";
            });
    }

    alertDismiss.addEventListener("click", function () {
        alertModal.style.display = "none";
    });

    // ── Direction toggle ───────────────────────────────────────────────────
    Array.prototype.forEach.call(document.querySelectorAll(".signin-dir-btn"), function (btn) {
        btn.addEventListener("click", function () {
            direction = btn.dataset.dir;
            Array.prototype.forEach.call(document.querySelectorAll(".signin-dir-btn"), function (b) {
                b.classList.toggle("active", b === btn);
            });
        });
    });

    // ── Signature pad ──────────────────────────────────────────────────────
    var canvas = document.getElementById("signin-signature");
    var ctx = canvas.getContext("2d");
    var strokes = [];
    var drawing = false;
    var lastX = null, lastY = null;

    function pointFromEvent(e) {
        var rect = canvas.getBoundingClientRect();
        var scaleX = canvas.width / rect.width;
        var scaleY = canvas.height / rect.height;
        var clientX = (e.touches ? e.touches[0].clientX : e.clientX);
        var clientY = (e.touches ? e.touches[0].clientY : e.clientY);
        return [
            Math.round((clientX - rect.left) * scaleX),
            Math.round((clientY - rect.top) * scaleY),
        ];
    }

    function startDraw(e) {
        e.preventDefault();
        drawing = true;
        var p = pointFromEvent(e);
        lastX = p[0];
        lastY = p[1];
    }

    function moveDraw(e) {
        if (!drawing) return;
        e.preventDefault();
        var p = pointFromEvent(e);
        var x = p[0], y = p[1];
        ctx.beginPath();
        ctx.moveTo(lastX, lastY);
        ctx.lineTo(x, y);
        ctx.strokeStyle = "black";
        ctx.lineWidth = 2;
        ctx.lineCap = "round";
        ctx.stroke();
        strokes.push([lastX, lastY, x, y]);
        lastX = x;
        lastY = y;
    }

    function endDraw(e) {
        drawing = false;
        lastX = lastY = null;
    }

    canvas.addEventListener("mousedown", startDraw);
    canvas.addEventListener("mousemove", moveDraw);
    window.addEventListener("mouseup", endDraw);
    canvas.addEventListener("touchstart", startDraw, { passive: false });
    canvas.addEventListener("touchmove", moveDraw, { passive: false });
    canvas.addEventListener("touchend", endDraw);

    document.getElementById("signin-clear-sig").addEventListener("click", function () {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        strokes = [];
    });

    // ── Submit ─────────────────────────────────────────────────────────────
    submitBtn.addEventListener("click", function () {
        var ids = Object.keys(selected);
        if (!ids.length) {
            alert("Select at least one person first.");
            return;
        }
        memberIdsFields.innerHTML = "";
        ids.forEach(function (id) {
            var input = document.createElement("input");
            input.type = "hidden";
            input.name = "member_ids";
            input.value = id;
            memberIdsFields.appendChild(input);
        });
        directionField.value = direction;
        notesField.value = notesInput.value;
        sigField.value = strokes.length ? JSON.stringify(strokes) : "";
        form.submit();
    });
})();
