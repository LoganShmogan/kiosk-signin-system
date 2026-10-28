// Shared layout behaviour for every dashboard page:
//  - Burger menu: the nav is collapsed behind the burger by default (mobile
//    first) and only shown as an inline tab bar when every link actually fits,
//    so admins with lots of tabs on a small laptop get the burger too.
//  - Stacked tables: copies each column header into its cells' data-label so
//    tables can render as labelled cards on narrow screens (see style.css).
(function () {
    var header = document.querySelector('.site-header');
    var nav = document.getElementById('site-nav');
    var toggle = header && header.querySelector('.nav-toggle');

    function setOpen(open) {
        nav.classList.toggle('open', open);
        toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
    }

    function fitNav() {
        header.classList.add('nav-wide');
        var fits = nav.scrollWidth <= nav.clientWidth + 1;
        header.classList.toggle('nav-wide', fits);
        if (fits) setOpen(false);
    }

    if (header && nav && toggle) {
        toggle.addEventListener('click', function () {
            setOpen(!nav.classList.contains('open'));
        });
        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape' && nav.classList.contains('open')) {
                setOpen(false);
                toggle.focus();
            }
        });
        var pending = false;
        window.addEventListener('resize', function () {
            if (pending) return;
            pending = true;
            requestAnimationFrame(function () { pending = false; fitNav(); });
        });
        fitNav();
        if (document.fonts && document.fonts.ready) document.fonts.ready.then(fitNav);
    }

    document.querySelectorAll('.table-wrap table').forEach(function (table) {
        var labels = Array.prototype.map.call(
            table.querySelectorAll('thead th'),
            function (th) { return th.textContent.trim(); }
        );
        table.querySelectorAll('tbody tr').forEach(function (tr) {
            Array.prototype.forEach.call(tr.children, function (td, i) {
                if (labels[i] && !td.hasAttribute('colspan')) td.setAttribute('data-label', labels[i]);
            });
        });
    });
})();
