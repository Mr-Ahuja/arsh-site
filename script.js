const toggle = document.getElementById('navToggle');
const links  = document.getElementById('navLinks');

toggle.addEventListener('click', () => {
  links.classList.toggle('open');
});

document.querySelectorAll('.nav__links a').forEach(link => {
  link.addEventListener('click', () => links.classList.remove('open'));
});

function handleSubmit(e) {
  e.preventDefault();
  const confirm = document.getElementById('formConfirm');
  confirm.textContent = 'Message sent. We will be in touch within 48h.';
  e.target.reset();
}
