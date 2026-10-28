(function () {
    "use strict";

    var currentType = "member";
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
    var selectAllInBtn = document.getElementById("signin-select-all-in");
    var runSearchInput = document.getElementById("runsheet-load-search");
    var runResultsBox = document.getElementById("runsheet-load-results");

    var direction = "IN";

    var picker = window.PersonPicker.init({
        searchInput: searchInput,
        resultsBox: resultsBox,
        selectedBox: selectedBox,
        selectedEmpty: selectedEmpty,
        searchUrl: function (q) {
            return "/signin/search?type=" + encodeURIComponent(currentType) + "&q=" + encodeURIComponent(q);
        },
        onChange: function (selected) {
            var ids = Object.keys(selected);
            detailsCard.style.display = ids.length ? "block" : "none";
            fetchAlerts(ids);
        },
    });

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

    // ── Alerts ─────────────────────────────────────────────────────────────
    function fetchAlerts(ids) {
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

    // ── Load a Run Sheet ──────────────────────────────────────────────────
    var runSearchTimer = null;
    runSearchInput.addEventListener("input", function () {
        var q = runSearchInput.value.trim();
        clearTimeout(runSearchTimer);
        if (!q) {
            runResultsBox.innerHTML = "";
            runResultsBox.style.display = "none";
            return;
        }
        runSearchTimer = setTimeout(function () { runRunSearch(q); }, 200);
    });

    function runRunSearch(q) {
        fetch("/run-sheets/search?q=" + encodeURIComponent(q))
            .then(function (r) { return r.json(); })
            .then(function (data) { renderRunResults(data.results || []); });
    }

    function renderRunResults(results) {
        runResultsBox.innerHTML = "";
        if (!results.length) {
            runResultsBox.style.display = "none";
            return;
        }
        results.forEach(function (r) {
            var item = document.createElement("div");
            item.className = "signin-search-result";
            item.textContent = r.name;
            item.addEventListener("click", function () {
                loadRunMembers(r.id);
                runSearchInput.value = "";
                runResultsBox.innerHTML = "";
                runResultsBox.style.display = "none";
            });
            runResultsBox.appendChild(item);
        });
        runResultsBox.style.display = "block";
    }

    function loadRunMembers(runId) {
        fetch("/run-sheets/" + encodeURIComponent(runId) + "/members")
            .then(function (r) { return r.json(); })
            .then(function (data) {
                (data.members || []).forEach(function (m) {
                    picker.addPerson(m.id, m.name);
                });
            });
    }

    // ── Select all currently signed in ─────────────────────────────────────
    selectAllInBtn.addEventListener("click", function () {
        fetch("/signin/currently-in")
            .then(function (r) { return r.json(); })
            .then(function (data) {
                (data.members || []).forEach(function (m) {
                    picker.addPerson(m.id, m.name);
                });
                var outBtn = document.querySelector(".signin-dir-out");
                if (outBtn) outBtn.click();
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
        var ids = picker.getSelectedIds();
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
