(function () {
    "use strict";

    var currentType = "member";
    var typeTabs = document.getElementById("run-sheet-type-tabs");
    var searchInput = document.getElementById("run-sheet-search");
    var resultsBox = document.getElementById("run-sheet-search-results");
    var selectedBox = document.getElementById("run-sheet-selected");
    var selectedEmpty = document.getElementById("run-sheet-selected-empty");
    var nameInput = document.getElementById("run-sheet-name");
    var submitBtn = document.getElementById("run-sheet-submit-btn");
    var form = document.getElementById("run-sheet-form");
    var nameField = document.getElementById("run-sheet-name-field");
    var memberIdsFields = document.getElementById("run-sheet-member-ids-fields");
    var scriptTag = document.currentScript;
    var initialMembers = JSON.parse(document.getElementById("run-sheet-initial-members").textContent || "[]");

    form.action = scriptTag.getAttribute("data-action");

    var picker = window.PersonPicker.init({
        searchInput: searchInput,
        resultsBox: resultsBox,
        selectedBox: selectedBox,
        selectedEmpty: selectedEmpty,
        searchUrl: function (q) {
            return "/signin/search?type=" + encodeURIComponent(currentType) + "&q=" + encodeURIComponent(q);
        },
        initial: initialMembers,
    });

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

    submitBtn.addEventListener("click", function () {
        var name = nameInput.value.trim();
        if (!name) {
            alert("Enter a run sheet name first.");
            return;
        }
        memberIdsFields.innerHTML = "";
        picker.getSelectedIds().forEach(function (id) {
            var input = document.createElement("input");
            input.type = "hidden";
            input.name = "member_ids";
            input.value = id;
            memberIdsFields.appendChild(input);
        });
        nameField.value = name;
        form.submit();
    });
})();
