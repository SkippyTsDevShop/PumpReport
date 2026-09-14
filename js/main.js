// FrontierTech.news — small progressive-enhancement script
// Mobile nav toggle + vertical pill filter. Site works fully without JS.

document.addEventListener('DOMContentLoaded', function () {
  var toggle = document.querySelector('.nav-toggle');
  var nav = document.querySelector('.primary-nav');
  if (toggle && nav) {
    toggle.addEventListener('click', function () {
      var open = nav.classList.toggle('open');
      toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
  }

  var pills = document.querySelectorAll('.pill[data-v]');
  var rows = document.querySelectorAll('.article-row[data-v]');
  if (pills.length && rows.length) {
    pills.forEach(function (pill) {
      pill.addEventListener('click', function (e) {
        e.preventDefault();
        pills.forEach(function (p) { p.classList.remove('active'); });
        pill.classList.add('active');
        var v = pill.getAttribute('data-v');
        rows.forEach(function (row) {
          var match = v === 'all' || row.getAttribute('data-v') === v;
          row.style.display = match ? '' : 'none';
        });
      });
    });
  }
});
