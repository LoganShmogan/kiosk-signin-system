// Shared "search for a person, click to add as a chip" widget used by the
// Sign In page and the Run Sheet form. Each caller supplies its own DOM
// elements so multiple pickers can exist on the same page without id
// collisions.
window.PersonPicker = (function () {
    "use strict";

    function init(opts) {
        var searchInput = opts.searchInput;
        var resultsBox = opts.resultsBox;
        var selectedBox = opts.selectedBox;
        var selectedEmpty = opts.selectedEmpty;
        var searchUrl = opts.searchUrl; // function(query) -> fetch URL
        var onChange = opts.onChange || function () {};

        var selected = {}; // id -> name
        if (opts.initial) {
            opts.initial.forEach(function (p) {
                selected[p.id] = p.name;
            });
        }

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
            fetch(searchUrl(q))
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
                    addPerson(r.id, r.name);
                    searchInput.value = "";
                    resultsBox.innerHTML = "";
                    resultsBox.style.display = "none";
                    searchInput.focus();
                });
                resultsBox.appendChild(item);
            });
            resultsBox.style.display = "block";
        }

        function addPerson(id, name) {
            selected[id] = name;
            renderSelected();
        }

        function removePerson(id) {
            delete selected[id];
            renderSelected();
        }

        function renderSelected() {
            var ids = Object.keys(selected);
            selectedBox.innerHTML = "";
            if (!ids.length) {
                if (selectedEmpty) selectedBox.appendChild(selectedEmpty);
                onChange(selected);
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
                    removePerson(id);
                });
                chip.appendChild(remove);
                selectedBox.appendChild(chip);
            });
            onChange(selected);
        }

        renderSelected();

        return {
            addPerson: addPerson,
            removePerson: removePerson,
            getSelectedIds: function () { return Object.keys(selected); },
            clear: function () {
                selected = {};
                renderSelected();
            },
        };
    }

    return { init: init };
})();
