// Landing interactions: mobile menu, scroll reveal
(() => {
  const btn = document.getElementById('menuBtn');
  const nav = document.getElementById('mobileNav');
  btn?.addEventListener('click', () => {
    const open = nav.hasAttribute('hidden');
    nav.toggleAttribute('hidden', !open);
    btn.setAttribute('aria-expanded', String(open));
  });
  nav?.querySelectorAll('a').forEach(a => a.addEventListener('click', () => nav.setAttribute('hidden', '')));
  document.getElementById('year').textContent = new Date().getFullYear();

  const io = new IntersectionObserver(entries => entries.forEach(e => {
    if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); }
  }), { threshold: 0.12 });
  document.querySelectorAll('.reveal').forEach((el, i) => { el.style.transitionDelay = (i % 4) * 70 + 'ms'; io.observe(el); });
})();
